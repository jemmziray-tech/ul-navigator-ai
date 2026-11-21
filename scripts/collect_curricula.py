"""Resumable curriculum snapshot and optional official module-content collection."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "ingestion")]
from ul_ingest.crawler import PoliteFetcher
from ul_ingest.site_archive import safe_fetch
from ul_ingest.curricula import content_link, parse_curriculum, parse_module, curriculum_markdown, module_url

BASE = ROOT / "data/curricula"


def now(): return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def cached(url):
    key = hashlib.sha1(url.encode()).hexdigest()
    for directory in [ROOT / "data/curriculum_raw", ROOT / "data/raw", ROOT / "data/site_archive/raw"]:
        p = directory / (key + ".bin")
        if p.exists():
            meta = p.with_suffix(".json")
            date = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat()
            if meta.exists():
                try:
                    stamp = json.loads(meta.read_text(encoding="utf-8")).get("fetched_at")
                    if isinstance(stamp, (int, float)): date = datetime.fromtimestamp(stamp, timezone.utc).isoformat()
                except (ValueError, OSError): pass
            return p.read_bytes(), date
    return None


def collect(modules=False, limit=None):
    courses = json.loads((ROOT / "frontend/src/data/courses.json").read_text(encoding="utf-8"))["courses"]
    courses.sort(key=lambda c: (c.get("code") != "LM174", c["level"] != "Undergraduate", c["title"]))
    f = PoliteFetcher("ULNavigatorAI/1.3 (+https://ul-navigator-ai.vercel.app; public course and module index)", ROOT / "data/curriculum_raw", delay_s=3, max_retries=1, timeout_s=25, cache_ttl_s=7 * 86400)
    f.client.event_hooks["response"].append(lambda r: setattr(f, "redirect_location", r.headers.get("location", "")))
    out = []
    try:
        for course in courses[:limit]:
            if (BASE / "STOP").exists(): return
            dest = BASE / "courses" / (course["id"] + ".json")
            if dest.exists():
                item = json.loads(dest.read_text(encoding="utf-8"))
            else:
                overview = cached(course["url"])
                url = course["links"].get("course content") or (content_link(overview[0], course["url"]) if overview else None)
                if not url:
                    item = {"id": course["id"], "title": course["title"], "code": course.get("code"), "url": course["url"], "checkedAt": now(), "academicYear": None, "sections": [], "status": "no_content_link_found"}
                else:
                    hit = cached(url)
                    if hit: body, date = hit
                    else:
                        result = safe_fetch(f, url)
                        if not result.ok:
                            item = {"id": course["id"], "title": course["title"], "code": course.get("code"), "url": url, "checkedAt": now(), "academicYear": None, "sections": [], "status": "fetch_failed", "error": result.error}
                            save(dest, item); out.append(item); continue
                        body, date = result.content, now()
                    item = parse_curriculum(body, course, url, date)
                save(dest, item)
            out.append(item)
            snapshot = {"generatedAt": now(), "scope": "Published content pages linked from the collected UL course directory; not a complete audit of every UL programme.", "courses": out,
                        "coverage": {"catalogueCourses": len(courses), "checkedCourses": len(out), "structuredCourses": sum(bool(c["sections"]) for c in out), "semesterSections": sum(len(c["sections"]) for c in out), "moduleListings": sum(len(s["modules"]) for c in out for s in c["sections"])}}
            save(BASE / "snapshot.json", snapshot)
            print(json.dumps({"checked": len(out), "programme": item.get("code") or item["title"], "sections": len(item["sections"]), "status": item["status"]}), flush=True)
        save(ROOT / "backend/app/data/curricula.json", snapshot)
        save(ROOT / "frontend/src/data/curricula.json", snapshot)
        if modules:
            found = {}
            for course in out:
                for section in course["sections"]:
                    for m in section["modules"]: found.setdefault(m["code"], m)
            for i, code in enumerate(found):
                if (BASE / "STOP").exists():
                    save(BASE / "module-progress.json", {"state":"paused", "updatedAt":now(), "uniqueModuleCodes":len(found), "collected":len(list((BASE / "modules").glob("*.json")))}); return
                dest = BASE / "modules" / (code + ".json")
                if dest.exists(): continue
                url = module_url(code); hit = cached(url)
                if hit: body, date = hit
                else:
                    f.client.follow_redirects = False
                    r = f.fetch(url)
                    for _ in range(4):
                        if r.status not in (301,302,303,307,308): break
                        from urllib.parse import urljoin, urlsplit
                        target = urljoin(url, getattr(f, "redirect_location", ""))
                        parsed_url = urlsplit(target)
                        if parsed_url.hostname not in {"bookofmodules.ul.ie", "www.bookofmodules.ul.ie"} or parsed_url.path.lower() != "/default.aspx":
                            r.error = "redirect outside the public Book of Modules scope"; break
                        url = target; r = f.fetch(url)
                    if not r.ok:
                        save(BASE / "module_failures" / (code + ".json"), {"code": code, "url": url, "error": r.error}); continue
                    # Never accept a redirect to an unrelated host.
                    from urllib.parse import urlsplit
                    if urlsplit(r.final_url).hostname not in {"bookofmodules.ul.ie", "www.bookofmodules.ul.ie"}: continue
                    body, date = r.content, now()
                parsed = parse_module(body, code, date)
                if parsed:
                    save(dest, parsed)
                    (BASE / "module_failures" / (code + ".json")).unlink(missing_ok=True)
                else: save(BASE / "module_failures" / (code + ".json"), {"code": code, "url": url, "error": "No exact module descriptor found"})
                save(BASE / "module-progress.json", {"updatedAt": now(), "attempted": i + 1, "uniqueModuleCodes": len(found), "collected": len(list((BASE / "modules").glob("*.json")))})
                print(json.dumps({"module": code, "found": bool(parsed), "of": len(found)}), flush=True)
            save(BASE / "module-progress.json", {"state":"complete", "updatedAt":now(), "uniqueModuleCodes":len(found), "collected":len(list((BASE / "modules").glob("*.json"))), "failed":len(list((BASE / "module_failures").glob("*.json")))})
    finally: f.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--modules", action="store_true"); parser.add_argument("--limit", type=int)
    args = parser.parse_args(); collect(args.modules, args.limit)
