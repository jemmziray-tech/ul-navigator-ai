"""Persistent FAISS vector store keyed by chunk id (supports incremental add/remove)."""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

import faiss
import numpy as np

log = logging.getLogger(__name__)


class IndexMismatchError(RuntimeError):
    pass


class FaissStore:
    def __init__(self, directory: Path, dim: int, model_name: str):
        self.dir = directory
        self.dim = dim
        self.model_name = model_name
        self.index_path = directory / "faiss.index"
        self.meta_path = directory / "faiss_meta.json"
        self._lock = threading.RLock()
        self.index = self._load_or_create()

    def _new(self):
        return faiss.IndexIDMap2(faiss.IndexFlatIP(self.dim))

    def _load_or_create(self):
        if self.index_path.exists() and self.meta_path.exists():
            meta = json.loads(self.meta_path.read_text())
            if meta.get("dim") != self.dim or meta.get("model") != self.model_name:
                raise IndexMismatchError(
                    f"Index was built with {meta.get('model')} (dim {meta.get('dim')}) but the "
                    f"configured embedder is {self.model_name} (dim {self.dim}). "
                    "Run `python -m ul_ingest reindex` to rebuild.")
            idx = faiss.read_index(str(self.index_path))
            log.info("faiss index loaded", extra={"extra_fields": {"vectors": idx.ntotal}})
            return idx
        return self._new()

    @property
    def size(self) -> int:
        return int(self.index.ntotal)

    def add(self, ids: list[int], vectors: np.ndarray) -> None:
        if not ids:
            return
        with self._lock:
            arr = np.asarray(ids, dtype="int64")
            self.index.remove_ids(arr)  # make add idempotent
            self.index.add_with_ids(np.ascontiguousarray(vectors, dtype="float32"), arr)

    def remove(self, ids: list[int]) -> int:
        if not ids:
            return 0
        with self._lock:
            return int(self.index.remove_ids(np.asarray(ids, dtype="int64")))

    def ids(self) -> set[int]:
        with self._lock:
            if self.index.ntotal == 0:
                return set()
            return set(faiss.vector_to_array(self.index.id_map).tolist())

    def search(self, query: np.ndarray, k: int) -> list[tuple[int, float]]:
        with self._lock:
            if self.index.ntotal == 0:
                return []
            k = min(k, self.index.ntotal)
            scores, ids = self.index.search(np.ascontiguousarray(query.reshape(1, -1)), k)
        return [(int(i), float(s)) for i, s in zip(ids[0], scores[0]) if i != -1]

    def reset(self) -> None:
        with self._lock:
            self.index = self._new()

    def save(self) -> None:
        with self._lock:
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self.index_path.with_suffix(".tmp")
            faiss.write_index(self.index, str(tmp))
            os.replace(tmp, self.index_path)
            self.meta_path.write_text(json.dumps({"dim": self.dim, "model": self.model_name,
                                                  "vectors": int(self.index.ntotal)}))
