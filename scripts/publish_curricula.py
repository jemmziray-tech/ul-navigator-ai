"""Bounded, resumable import of public curriculum/module documents; no Gemini calls."""
from pathlib import Path
import argparse
import os
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "ingestion")]
from ul_ingest.curricula import curriculum_markdown
from ul_ingest.chunking import chunk_markdown

BASE = ROOT / "data/curricula"
API = os.environ.get("UL_PUBLISH_API", "http://localhost:8000").rstrip("/")


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2), encoding="utf-8"); temp.replace(path)


def publish(watch=False):
    journal_path = BASE / "published.json"
    journal = json.loads(journal_path.read_text(encoding="utf-8")) if journal_path.exists() else {}
    session = requests.Session()
    credentials = (ROOT / "data/ADMIN_PASSWORD.txt").read_text(encoding="utf-8")
    password = re.search(r"ULNav-[A-Za-z0-9_-]+", credentials)
    if password is None: raise RuntimeError("Maintainer credential not available")

    def login():
        r = session.post(API + "/api/admin/login", json={"username": "admin", "password": password.group()}, timeout=(10, 240))
        r.raise_for_status(); session.headers["Authorization"] = "Bearer " + r.json()["access_token"]

    features = session.get(API + "/api/curricula", timeout=(10, 240)); features.raise_for_status()
    if features.json().get("section_preserving_ingestion") != 1: raise RuntimeError("Curriculum backend is not ready")
    login(); imported = failures = 0
    while True:
        if (BASE / "STOP").exists(): return
        candidates = []
        for p in sorted((BASE / "courses").glob("*.json"), key=lambda p: (p.stem != "1a76c7edc7e7", p.name)):
            d = json.loads(p.read_text(encoding="utf-8"))
            if d.get("sections"):
                candidates.append((d["url"], "Curriculum | " + (d.get("code") or "") + " | " + d["title"], curriculum_markdown(d), True))
        pilot_file = BASE / "courses/1a76c7edc7e7.json"
        pilot = json.loads(pilot_file.read_text(encoding="utf-8")) if pilot_file.exists() else {"sections":[]}
        pilot_codes = {m["code"] for section in pilot["sections"] for m in section["modules"]}
        for p in sorted((BASE / "modules").glob("*.json"), key=lambda p: (p.stem not in pilot_codes, p.name)):
            d = json.loads(p.read_text(encoding="utf-8"))
            candidates.append((d["url"], d["code"] + " — " + d.get("title", "Official Book of Modules descriptor"), d["markdown"], False))
        pending = [(u, title, md, preserve, hashlib.sha256(md.encode()).hexdigest()) for u, title, md, preserve in candidates
                   if journal.get(u, {}).get("hash") != hashlib.sha256(md.encode()).hexdigest()]
        state = {"updatedAt": datetime.now(timezone.utc).isoformat(), "state": "running", "importedThisRun": imported,
                 "publishedDocuments": len(journal), "pendingDocuments": len(pending), "maxChunks": 24000, "maxImports": 2500}
        save(BASE / "publish-progress.json", state)
        for position, (url, title, markdown, preserve, digest) in enumerate(pending):
            if (BASE / "STOP").exists(): return
            try:
                stats = session.get(API + "/api/stats", timeout=(10, 240)); stats.raise_for_status()
                estimated = len(chunk_markdown(markdown, 260, 50, 40, preserve))
                if stats.json()["chunks"] + estimated > 24000 or imported >= 2500:
                    save(BASE / "publish-progress.json", {**state, "state": "capacity_reached", "importedThisRun": imported,
                                                          "publishedDocuments": len(journal), "chunks": stats.json()["chunks"]})
                    print("Existing live capacity ceiling reached; remaining documents stay collected locally", flush=True); return
                if estimated > 200: continue
                def upload():
                    return session.post(API + "/api/admin/upload", data={"category": "modules", "title": title,
                         "source_url": url, "preserve_sections": str(preserve).lower()},
                         files={"file": (hashlib.sha1(url.encode()).hexdigest() + ".md", markdown.encode(), "text/markdown")}, timeout=(10, 240))
                r = upload()
                if r.status_code == 401: login(); r = upload()
                r.raise_for_status()
                journal[url] = {"hash": digest, "publishedAt": datetime.now(timezone.utc).isoformat()}
                save(journal_path, journal); imported += 1; failures = 0
                print(json.dumps({"imported": imported, "title": title, "status": r.json().get("status")}), flush=True)
                save(BASE / "publish-progress.json", {**state, "importedThisRun": imported, "publishedDocuments": len(journal), "pendingDocuments": len(pending) - position - 1})
            except requests.RequestException as exc:
                failures += 1
                print(json.dumps({"source": url, "error": type(exc).__name__, "consecutiveFailures": failures}), flush=True)
                if failures >= 3:
                    save(BASE / "publish-progress.json", {**state, "state": "paused_after_errors", "publishedDocuments": len(journal)}); return
            time.sleep(3)
        complete = BASE / "module-progress.json"
        if not pending and complete.exists() and json.loads(complete.read_text(encoding="utf-8")).get("state") == "complete":
            save(BASE / "publish-progress.json", {**state, "state":"complete"})
            # Restore the pre-existing broader collection after the priority queue finishes.
            import subprocess
            r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "UL_RESOURCE_CRAWL.ps1")], capture_output=True, text=True)
            print("Broader resource workers resumed" if r.returncode == 0 else "Broader workers can be resumed with UL_RESOURCE_RESUME.bat", flush=True)
            return
        if not watch: return
        time.sleep(15)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--watch", action="store_true"); args = parser.parse_args(); publish(args.watch)
