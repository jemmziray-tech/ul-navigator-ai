"""The evaluation harness runs end-to-end and only reports measured values."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dataset_is_large_and_balanced():
    items = [json.loads(l) for l in (ROOT / "evaluation" / "dataset.jsonl").read_text().splitlines()]
    assert len(items) >= 100
    types = {i["type"] for i in items}
    assert {"answerable", "ambiguous", "outdated", "unanswerable", "adversarial"} <= types
    cats = {i["category"] for i in items}
    for c in ["qca_grading", "registration", "accommodation", "international", "fees",
              "scholarships", "calendar", "modules", "library", "student_support"]:
        assert c in cats
    assert len({i["id"] for i in items}) == len(items)


def test_harness_runs_on_index(loaded_index, tmp_path):
    import os
    env = {**os.environ}
    out = tmp_path / "eval"
    r = subprocess.run([sys.executable, str(ROOT / "evaluation" / "run_eval.py"), "--limit", "12",
                        "--out", str(out), "--judge", "lexical"], env=env, capture_output=True,
                       text=True, timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    res = json.loads((out / "results.json").read_text())
    assert res["metrics"]["n_questions"] == 12
    assert res["metrics"]["citation_validity"] in (None, 1.0)
    assert "All numbers below were measured" in (out / "report.md").read_text()


def test_lexical_faithfulness_handles_quotes():
    sys.path.insert(0, str(ROOT / "evaluation"))
    from run_eval import lexical_faithfulness
    ans = "_Generative answers are switched off_\n\n**Fees — EU** [S1]\n> The student contribution charge is paid in two instalments each year."
    assert lexical_faithfulness(ans, ["The student contribution charge is paid in two instalments each year."]) == 1.0


def test_coverage_excludes_disabled_sources(tmp_path):
    import sqlite3
    sys.path.insert(0, str(ROOT / "evaluation"))
    from audit_coverage import audit
    database = tmp_path / "coverage.db"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE documents (url, category, status, chunk_count, collected_at)")
        db.execute("CREATE TABLE chunks (id)")
        db.execute("INSERT INTO documents VALUES ('https://ul.ie/fees', 'fees', 'disabled', 2, '')")
    dataset = tmp_path / "questions.jsonl"
    dataset.write_text(json.dumps({"id": "fee", "should_answer": True,
                                  "expected_sources": ["/fees"]}), encoding="utf-8")
    result = audit(database, dataset)
    assert result["indexed_documents"] == 0
    assert result["questions_without_expected_source"][0]["id"] == "fee"


def test_extractive_rejects_gemini_judge():
    result = subprocess.run([sys.executable, str(ROOT / "evaluation/run_eval.py"),
                             "--extractive", "--judge", "gemini"],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 2
    assert "cannot be combined" in result.stderr
