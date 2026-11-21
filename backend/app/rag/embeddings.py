"""Embedding backends.

* SentenceTransformerEmbedder - production backend (default BAAI/bge-small-en-v1.5,
  384-d, ~130 MB). Uses CUDA automatically when available (fp16), otherwise CPU.
* HashingEmbedder - dependency-free, deterministic feature-hashing embedder used for
  tests and for fully offline smoke runs. It is NOT a semantic model; the API reports
  which backend is active so results are never misrepresented.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
import threading
from functools import lru_cache
from typing import Protocol

import numpy as np

from ..config import get_settings

log = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[/.'-][a-z0-9]+)*")


class Embedder(Protocol):
    name: str
    dim: int
    device: str

    def encode(self, texts: list[str], is_query: bool = False) -> np.ndarray: ...


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (m / norms).astype("float32")


class HashingEmbedder:
    def __init__(self, dim: int = 768):
        self.dim = dim
        self.name = f"hash-{dim}"
        self.device = "cpu"

    def _features(self, text: str) -> list[str]:
        toks = _TOKEN_RE.findall(text.lower())
        feats = list(toks)
        feats += [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        for t in toks:  # char trigrams give a little fuzzy matching
            if len(t) > 4:
                feats += [f"#{t[i:i + 3]}" for i in range(len(t) - 2)]
        return feats

    def encode(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype="float32")
        for i, text in enumerate(texts):
            counts: dict[int, float] = {}
            for f in self._features(text):
                h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "little")
                idx = h % self.dim
                sign = 1.0 if (h >> 63) & 1 else -1.0
                w = 0.5 if f.startswith("#") else 1.0
                counts[idx] = counts.get(idx, 0.0) + sign * w
            for idx, c in counts.items():
                out[i, idx] = math.copysign(math.log1p(abs(c)), c)
        return _normalize(out)


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, device: str = "auto", batch_size: int = 64,
                 query_instruction: str = "", cache_dir: str | None = None):
        import torch  # noqa: WPS433 (deferred heavy import)
        from sentence_transformers import SentenceTransformer

        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.batch_size = batch_size
        self.query_instruction = query_instruction
        self.model = SentenceTransformer(model_name, device=device, cache_folder=cache_dir)
        if device == "cuda":
            self.model.half()  # halves VRAM use on the RTX GPU
        get_dim = getattr(self.model, "get_embedding_dimension", None) or \
            self.model.get_sentence_embedding_dimension
        self.dim = int(get_dim())
        self.name = model_name
        self._lock = threading.Lock()
        log.info("embedder loaded", extra={"extra_fields": {"model": model_name, "device": device,
                                                            "dim": self.dim}})

    def encode(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        if is_query and self.query_instruction:
            texts = [self.query_instruction + t for t in texts]
        with self._lock:
            vecs = self.model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True,
                                     convert_to_numpy=True, show_progress_bar=len(texts) > 500)
        return np.asarray(vecs, dtype="float32")


_embedder_lock = threading.Lock()


@lru_cache
def get_embedder() -> Embedder:
    s = get_settings()
    with _embedder_lock:
        if s.embedding_backend == "hash":
            return HashingEmbedder()
        return SentenceTransformerEmbedder(
            s.embedding_model, s.embedding_device, s.embedding_batch_size,
            s.embedding_query_instruction,
            str(s.model_cache_dir) if s.model_cache_dir else None)
