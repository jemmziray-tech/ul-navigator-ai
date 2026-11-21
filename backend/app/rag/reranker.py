"""Cross-encoder reranking (ms-marco-MiniLM-L-6-v2 by default, ~90 MB).

If the model cannot be loaded (offline, hash test mode, missing torch) reranking is
skipped and the fused hybrid ranking is used instead; the pipeline reports this.
"""
from __future__ import annotations

import logging
import math
import threading
from functools import lru_cache

from ..config import get_settings

log = logging.getLogger(__name__)


class CrossEncoderReranker:
    def __init__(self, model_name: str, device: str):
        import torch
        from sentence_transformers import CrossEncoder

        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        # Identity activation => predict() returns raw logits; we apply the sigmoid once below
        # (sentence-transformers >= 4 otherwise applies a sigmoid itself).
        self.model = CrossEncoder(model_name, device=device, max_length=512,
                                  activation_fn=torch.nn.Identity())
        self.name = model_name
        self._lock = threading.Lock()

    def score(self, query: str, passages: list[str]) -> list[float]:
        """Returns probabilities in [0, 1] (sigmoid of the relevance logit)."""
        if not passages:
            return []
        with self._lock:
            logits = self.model.predict([(query, p) for p in passages], batch_size=32,
                                        show_progress_bar=False)
        return [1.0 / (1.0 + math.exp(-float(x))) for x in logits]


@lru_cache
def get_reranker() -> CrossEncoderReranker | None:
    s = get_settings()
    if not s.reranker_enabled or s.embedding_backend == "hash":
        return None
    try:
        return CrossEncoderReranker(s.reranker_model, s.embedding_device)
    except Exception as exc:  # pragma: no cover - depends on environment
        log.warning("reranker unavailable, using fused ranking",
                    extra={"extra_fields": {"error": str(exc)}})
        return None
