"""Read-only SQLite coverage audit; no crawling, model loading or API calls."""
import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def audit(database, dataset):
    # URI read-only mode also prevents accidentally creating an empty database.
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        docs = [dict(row) for row in db.execute(
            "SELECT url, category, status, chunk_count, collected_at FROM documents")]
        chunks = db.execute("SELECT count(*) FROM chunks").fetchone()[0]
    indexed = [d for d in docs if d["status"] == "indexed" and d["chunk_count"] > 0]
    items = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    missing = [item for item in items if item["should_answer"] and not any(
        pattern.lower() in doc["url"].lower()
        for pattern in item["expected_sources"] for doc in indexed)]
    return {"timestamp": datetime.now(timezone.utc).isoformat(),
            "documents": len(docs), "indexed_documents": len(indexed), "chunks": chunks,
            "categories": dict(sorted(Counter(d["category"] for d in indexed).items())),
            "statuses": dict(Counter(d["status"] for d in docs)),
            "questions_without_expected_source": missing}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "data/ul_navigator.db")
    parser.add_argument("--dataset", type=Path, default=ROOT / "evaluation/dataset.jsonl")
    parser.add_argument("--out", type=Path, default=ROOT / "evaluation/results/coverage.json")
    args = parser.parse_args()
    result = audit(args.database, args.dataset)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
