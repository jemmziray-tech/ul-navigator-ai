"""Developer utilities.

    python -m app.cli doctor        # check GPU/CUDA, models, Gemini key, index, DB
    python -m app.cli models        # list Gemini models available to your API key
    python -m app.cli ask "How is QCA calculated?"
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_ING = Path(__file__).resolve().parents[2] / "ingestion"
if str(_ING) not in sys.path:
    sys.path.insert(0, str(_ING))

from .config import get_settings  # noqa: E402
from .db import init_db  # noqa: E402
from .logging_conf import setup_logging  # noqa: E402


def doctor() -> int:
    s = get_settings()
    ok = True
    print(f"Data dir          : {s.data_dir}")
    print(f"Database          : {s.sqlalchemy_url.split('@')[-1]}")
    try:
        import torch
        cuda = torch.cuda.is_available()
        print(f"PyTorch           : {torch.__version__} | CUDA available: {cuda}")
        if cuda:
            p = torch.cuda.get_device_properties(0)
            print(f"GPU               : {p.name} ({p.total_memory / 1e9:.1f} GB, sm_{p.major}{p.minor})")
            torch.zeros(1, device="cuda")  # fails fast if the wheel lacks kernels for this GPU
            print("CUDA kernel test  : OK")
    except ImportError:
        print("PyTorch           : NOT INSTALLED (see requirements-ml.txt)")
        ok = s.embedding_backend == "hash"
    except Exception as exc:  # e.g. 'no kernel image is available' on RTX 50xx with old torch
        print(f"CUDA kernel test  : FAILED - {exc}\n  -> install a CUDA 12.8+ build: "
              "pip install torch --index-url https://download.pytorch.org/whl/cu128")
        ok = False
    print(f"Embedding backend : {s.embedding_backend} ({s.embedding_model})")
    try:
        t = time.perf_counter()
        from .rag.embeddings import get_embedder
        e = get_embedder()
        e.encode(["warm-up"], is_query=True)
        print(f"Embedder          : OK on {e.device}, dim {e.dim} ({time.perf_counter() - t:.1f}s)")
    except Exception as exc:
        print(f"Embedder          : FAILED - {exc}")
        ok = False
    from .rag.reranker import get_reranker
    print(f"Reranker          : {'OK' if get_reranker() else 'disabled/unavailable (fused ranking used)'}")
    print(f"Gemini            : {'key configured, model ' + s.gemini_model if s.gemini_enabled else 'NOT configured (extractive mode)'}")
    try:
        init_db()
        from .rag.knowledge_index import get_index
        print(f"Index             : {json.dumps(get_index().stats)}")
    except Exception as exc:
        print(f"Index             : FAILED - {exc}")
        ok = False
    from .security import admin_configured
    print(f"Admin auth        : {'configured' if admin_configured() else 'NOT configured (admin disabled)'}")
    print("\nAll good." if ok else "\nSome checks failed - see above.")
    return 0 if ok else 1


def models() -> int:
    from .rag.llm import get_llm
    llm = get_llm()
    if llm is None:
        print("GEMINI_API_KEY is not configured.")
        return 1
    for name in llm.list_models():
        print(name)
    return 0


def ask(question: str) -> int:
    init_db()
    from .rag.pipeline import run
    r = run(question)
    print(r.answer)
    print("\nSources:")
    for c in r.citations:
        print(f"  [{c['id']}] {c['title']} — {c['url']}" + (f" (p.{c['page']})" if c["page"] else ""))
    print(f"\nmode={r.mode} category={r.analysis.category} flags={r.flags} "
          f"latency={r.total_ms:.0f}ms")
    return 0


if __name__ == "__main__":
    setup_logging("WARNING", False)
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "doctor":
        sys.exit(doctor())
    if cmd == "models":
        sys.exit(models())
    if cmd == "ask" and len(sys.argv) > 2:
        sys.exit(ask(" ".join(sys.argv[2:])))
    print(__doc__)
