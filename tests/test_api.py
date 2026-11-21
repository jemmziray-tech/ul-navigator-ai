"""API endpoint tests (FastAPI TestClient)."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from synthetic_corpus import MODULES_CSV

CID = "test-client-0001"


@pytest.fixture()
def client(loaded_index):
    from app.main import create_app
    with TestClient(create_app()) as c:
        yield c


def _admin(client) -> dict:
    r = client.post("/api/admin/login", json={"username": "admin",
                                               "password": "correct-horse-battery"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health_and_ready(client):
    assert client.get("/health").json()["status"] == "ok"
    r = client.get("/health/ready").json()
    assert r["status"] == "ready" and r["index"]["chunks"] > 0
    assert r["llm"]["configured"] is False
    assert "api_key" not in json.dumps(r).lower()


def test_stats_reflect_real_index(client):
    s = client.get("/api/stats").json()
    assert s["documents"] == 7 and s["chunks"] > 7 and s["pdf_documents"] == 1
    assert s["generation"] == "extractive"


def test_sources_explorer(client):
    r = client.get("/api/sources", params={"category": "fees"}).json()
    assert r["total"] == 1 and r["items"][0]["category"] == "fees"
    doc = client.get(f"/api/sources/{r['items'][0]['id']}").json()
    assert doc["sections"] and doc["url"].endswith("/fees")
    assert client.get("/api/sources", params={"q": "library"}).json()["total"] >= 1
    assert client.get("/api/sources/doesnotexist").status_code == 404


def test_chat_sync_and_conversation_flow(client):
    r = client.post("/api/chat/sync", json={"question": "What is the repeat examination fee?",
                                            "client_id": CID})
    assert r.status_code == 200
    body = r.json()
    assert body["citations"] and body["citations"][0]["page"] == 2
    assert body["message_id"] and body["conversation_id"]
    conv = body["conversation_id"]
    r2 = client.post("/api/chat/sync", json={"question": "and when are appeals due?",
                                             "client_id": CID, "conversation_id": conv})
    assert r2.json()["conversation_id"] == conv
    lst = client.get("/api/conversations", params={"client_id": CID}).json()
    assert lst[0]["id"] == conv
    full = client.get(f"/api/conversations/{conv}", params={"client_id": CID}).json()
    assert [m["role"] for m in full["messages"]] == ["user", "assistant", "user", "assistant"]
    # other clients can't read it
    assert client.get(f"/api/conversations/{conv}",
                      params={"client_id": "someone-else-1"}).status_code == 404
    # regenerate replaces the last answer instead of duplicating the question
    client.post("/api/chat/sync", json={"question": "and when are appeals due?",
                                        "client_id": CID, "conversation_id": conv,
                                        "regenerate": True})
    full = client.get(f"/api/conversations/{conv}", params={"client_id": CID}).json()
    assert len(full["messages"]) == 4
    fb = client.post("/api/feedback", json={"message_id": body["message_id"], "rating": 1})
    assert fb.status_code == 200
    assert client.patch(f"/api/conversations/{conv}", params={"client_id": CID},
                        json={"title": "Exams"}).status_code == 200
    assert client.delete(f"/api/conversations/{conv}", params={"client_id": CID}).json()["ok"]


def test_chat_stream_sse(client):
    with client.stream("POST", "/api/chat", json={"question": "Library opening hours?",
                                                  "client_id": CID}) as r:
        assert r.status_code == 200
        raw = "".join(r.iter_text())
    events = [ln.split(":", 1)[1].strip() for ln in raw.splitlines() if ln.startswith("event:")]
    assert events[0] == "meta" and "sources" in events and events[-1] == "done"
    done = [ln for ln in raw.splitlines() if ln.startswith("data:")][-1]
    payload = json.loads(done[5:])
    assert payload["citations"] and payload["follow_ups"]


def test_chat_input_validation(client):
    assert client.post("/api/chat/sync", json={"question": "  ", "client_id": CID}).status_code == 422
    assert client.post("/api/chat/sync", json={"question": "x" * 5000,
                                               "client_id": CID}).status_code == 422
    assert client.post("/api/chat/sync", json={"question": "hi",
                                               "client_id": "bad id!"}).status_code == 422
    assert client.post("/api/chat/sync", json={"question": "hi", "client_id": CID,
                                               "filters": {"academic_year": "2026"}}).status_code == 422


def test_tools(client):
    q = client.post("/api/tools/qca", json={"modules": [
        {"code": "A", "credits": 6, "grade": "A1"}, {"code": "B", "credits": 6, "grade": "b2"},
        {"code": "C", "credits": 6, "grade": "C3", "include": False}]}).json()
    assert q["qca"] == 3.5 and q["credits"] == 12 and q["excluded_modules"] == ["C"]
    assert q["classification"].startswith("First")
    assert client.post("/api/tools/qca", json={"modules": [
        {"credits": 6, "grade": "Z9"}]}).status_code == 422
    assert client.get("/api/tools/qca/rules").json()["grades"][0] == {"grade": "A1", "qpv": 4.0}
    mods = client.get("/api/tools/modules", params={"q": "NB4012"}).json()
    assert mods["results"] and "NB4012" in mods["results"][0]["matched_line"]
    cal = client.get("/api/tools/calendar").json()
    assert cal["items"] and all(i["category"] == "calendar" for i in cal["items"])
    assert client.get("/api/tools/explore", params={"category": "accommodation"}).json()["items"]
    assert client.get("/api/tools/explore", params={"category": "secrets"}).status_code == 422
    assert len(client.get("/api/tools/checklist").json()["items"]) >= 10


def test_admin_requires_auth(client):
    assert client.get("/api/admin/overview").status_code == 401
    assert client.get("/api/admin/overview",
                      headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post("/api/admin/login", json={"username": "admin",
                                                  "password": "wrong"}).status_code == 401


def test_admin_dashboard_and_upload(client):
    h = _admin(client)
    ov = client.get("/api/admin/overview", headers=h).json()
    assert ov["documents"]["indexed"] == 7 and ov["coverage"]
    assert isinstance(client.get("/api/admin/jobs", headers=h).json(), list)
    up = client.post("/api/admin/upload", headers=h, data={"category": "modules"},
                     files={"file": ("more_modules.csv",
                                     MODULES_CSV.replace("NB4012", "NB5000").encode(), "text/csv")})
    assert up.status_code == 200 and up.json()["status"] == "new"
    bad = client.post("/api/admin/upload", headers=h,
                      files={"file": ("evil.pdf", b"not a pdf", "application/pdf")})
    assert bad.status_code == 400
    exe = client.post("/api/admin/upload", headers=h,
                      files={"file": ("run.exe", b"MZ...", "application/octet-stream")})
    assert exe.status_code == 400
    docs = client.get("/api/admin/documents", headers=h, params={"q": "more_modules"}).json()
    doc_id = docs["items"][0]["id"]
    assert client.delete(f"/api/admin/documents/{doc_id}", headers=h).json()["ok"]
    assert client.post("/api/admin/reconcile", headers=h).json()["vectors"] > 0
    assert "lines" in client.get("/api/admin/logs", headers=h).json()
    assert isinstance(client.get("/api/admin/unanswered", headers=h).json(), list)


def test_security_headers_and_cors(client):
    r = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    r2 = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r2.headers


def test_retention_purge(client):
    from datetime import datetime, timedelta, timezone

    from app.db import Conversation, session_scope
    from app.main import purge_expired
    with session_scope() as db:
        db.add(Conversation(client_id=CID, title="old",
                            updated_at=datetime.now(timezone.utc) - timedelta(days=400)))
    assert purge_expired()["conversations"] == 1



def test_module_descriptions_are_separate_from_prerequisite_mentions(client, loaded_index):
    from ul_ingest.pipeline import DocInput, JobReport, upsert_document
    report = JobReport("test")
    upsert_document(loaded_index, DocInput(
        url="https://test.northbridge.example/advanced-biology", kind="txt",
        title="NB6006 - Advanced Biology", category="modules",
        markdown="Prerequisites: NB6005. " + "Advanced cellular research and practical laboratory techniques. " * 10), report)
    upsert_document(loaded_index, DocInput(
        url="https://test.northbridge.example/biology", kind="txt",
        title="NB6005 - Introductory Biology", category="modules",
        markdown="Introductory biology covers cells and organisms. " * 10), report)
    result = client.get("/api/tools/modules", params={"q": "NB6005"}).json()
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "NB6005 - Introductory Biology"
    assert result["results"][0]["match_type"] == "module"
    assert result["references"]
    assert all(item["match_type"] == "reference" for item in result["references"])
    missing = client.get("/api/tools/modules", params={"q": "NB6999"}).json()
    assert missing["results"] == []

def test_clarification_persisted_via_chat_api(client):
    cid = "clarification-test-client"
    a = client.post("/api/chat/sync", json={"client_id": cid, "question": "How much are tuition fees?"}).json()
    assert a["mode"] == "clarification"
    b = client.post("/api/chat/sync", json={"client_id": cid, "conversation_id": a["conversation_id"], "question": "LM174"}).json()
    assert b["clarification"]["missing_field"] == "fee_category"


def test_clarification_does_not_consume_generation_budget(client, monkeypatch):
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "rate_limit_chat", "1/minute")
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    headers = {"X-Forwarded-For": "198.51.100.77"}
    cid, conv = "budget-clarification-client", None
    for question in ["How much are tuition fees?", "LM174", "Non-EU", "2026/27"]:
        payload = {"client_id": cid, "question": question, "conversation_id": conv}
        r = client.post("/api/chat/sync", json=payload, headers=headers)
        assert r.status_code == 200, r.text
        conv = r.json()["conversation_id"]
    # One answered request exhausted the paid-answer allowance, but a clarification
    # is still allowed. A second full answer is blocked before storing its user turn.
    assert client.post("/api/chat/sync", json={"client_id": cid, "question": "How much are tuition fees?"}, headers=headers).status_code == 200
    assert client.post("/api/chat/sync", json={"client_id": cid, "question": "How many books can I borrow?"}, headers=headers).status_code == 429
