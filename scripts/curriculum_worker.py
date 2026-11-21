"""Windows scheduled worker entrypoint; no credentials appear in task arguments."""
from pathlib import Path
import os
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "ingestion")]
mode = sys.argv[1]
assert mode in {"collect", "publish"}
(ROOT / "data/curricula").mkdir(parents=True, exist_ok=True)
log = (ROOT / "data/curricula" / (mode + ".log")).open("a", encoding="utf-8", buffering=1)
sys.stdout = sys.stderr = log
try:
    from ul_ingest.site_archive import worker_lock
    # Reuse the OS-held locking implementation to reject duplicate workers.
    with worker_lock(ROOT / "data/curricula", mode):
        if mode == "collect":
            from collect_curricula import collect
            collect(modules=True)
        else:
            from publish_curricula import publish
            publish(watch=True)
except Exception:
    traceback.print_exc(); raise
