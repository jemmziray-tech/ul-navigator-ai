"""Chat endpoints: streaming answers (SSE), conversations and feedback."""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool

from ..config import get_settings
from ..db import Conversation, Feedback, Message, QueryLog, get_db, session_scope, utcnow
from ..rag.pipeline import PipelineResult, run, run_stream
from ..rag.classifier import analyse
from ..rag.clarification import clarify
from ..security import limiter
from .schemas import ChatRequest, FeedbackRequest, RenameRequest

router = APIRouter(prefix="/api", tags=["chat"])
log = logging.getLogger(__name__)


def _budget_cost(request: Request, req: ChatRequest):
    """Count only answer requests against the paid-generation cap, before mutation.

    FastAPI resolves this dependency before the rate-limit wrapper. Clarification
    still has a separate 20-request/minute abuse limit and performs no model call.
    """
    request.state.generation_cost = 1
    analysis = analyse(req.question)
    if analysis.intent in {"empty", "smalltalk", "injection", "social"}:
        request.state.generation_cost = 0
        return
    history = []
    if req.conversation_id and get_settings().store_conversations:
        with session_scope() as db:
            conv = db.get(Conversation, req.conversation_id)
            if conv is None or conv.client_id != req.client_id:
                raise HTTPException(404, "Conversation not found")
            msgs = list(conv.messages)
            if req.regenerate and msgs and msgs[-1].role == "assistant":
                msgs = msgs[:-1]
            if req.regenerate and msgs and msgs[-1].role == "user":
                msgs = msgs[:-1]
            history = [{"role": m.role, "content": m.content, "clarification": (m.meta or {}).get("clarification")} for m in msgs]
    year = req.filters.academic_year if req.filters else None
    if clarify(req.question, history, year).state:
        request.state.generation_cost = 0


def _result_payload(r: PipelineResult, message_id: str | None, conversation_id: str | None) -> dict:
    return {
        "message_id": message_id, "conversation_id": conversation_id, "answer": r.answer,
        "citations": r.citations, "sources": r.sources, "follow_ups": r.follow_ups,
        "mode": r.mode, "answered": r.answered, "flags": r.flags,
        "clarification": r.clarification,
        "category": r.analysis.category, "high_stakes": r.analysis.high_stakes,
        "academic_year": r.analysis.academic_year, "retrieval_query": r.retrieval_query,
        "timings": {"retrieval_ms": round(r.retrieval_ms, 1), "total_ms": round(r.total_ms, 1)},
    }


def _prepare(req: ChatRequest) -> tuple[str | None, list[dict]]:
    """Create/load the conversation, store the user turn, return prior history."""
    s = get_settings()
    if not s.store_conversations:
        return None, []
    with session_scope() as db:
        conv = None
        if req.conversation_id:
            conv = db.get(Conversation, req.conversation_id)
            if conv is None or conv.client_id != req.client_id:
                raise HTTPException(404, "Conversation not found")
        if conv is None:
            conv = Conversation(client_id=req.client_id, title=req.question[:80])
            db.add(conv)
            db.flush()
        msgs = list(conv.messages)
        if req.regenerate and msgs and msgs[-1].role == "assistant":
            db.delete(msgs[-1])
            msgs = msgs[:-1]
        if req.regenerate and msgs and msgs[-1].role == "user":
            history_msgs = msgs[:-1]
        else:
            db.add(Message(conversation_id=conv.id, role="user", content=req.question))
            history_msgs = msgs
        conv.updated_at = utcnow()
        history = [{"role": m.role, "content": m.content,
                    "clarification": (m.meta or {}).get("clarification")} for m in history_msgs]
        return conv.id, history


def _persist(conv_id: str | None, question: str, r: PipelineResult) -> str | None:
    msg_id = None
    with session_scope() as db:
        if conv_id:
            msg = Message(conversation_id=conv_id, role="assistant", content=r.answer,
                          citations=r.citations,
                          meta={"follow_ups": r.follow_ups, "mode": r.mode, "flags": r.flags,
                                "category": r.analysis.category, "answered": r.answered,
                                "clarification": r.clarification})
            db.add(msg)
            db.flush()
            msg_id = msg.id
        db.add(QueryLog(question=question[:2000], category=r.analysis.category,
                        answered=r.answered, mode=r.mode, top_score=r.top_score,
                        n_citations=len(r.citations), retrieval_ms=r.retrieval_ms,
                        total_ms=r.total_ms, flags=r.flags))
    return msg_id


@router.post("/chat")
@limiter.limit("20/minute")
@limiter.shared_limit(lambda: get_settings().rate_limit_chat, scope="chat-generation",
                      cost=lambda request: getattr(request.state, "generation_cost", 1))
async def chat_stream(request: Request, req: ChatRequest, _budget=Depends(_budget_cost)):
    conv_id, history = _prepare(req)
    f = req.filters

    def events():
        yield {"event": "meta", "data": json.dumps({"conversation_id": conv_id})}
        try:
            for ev in run_stream(req.question, history,
                                 categories=f.categories if f else None,
                                 academic_year=f.academic_year if f else None):
                t = ev["type"]
                if t == "done":
                    r: PipelineResult = ev["result"]
                    msg_id = _persist(conv_id, req.question, r)
                    yield {"event": "done",
                           "data": json.dumps(_result_payload(r, msg_id, conv_id), default=str)}
                else:
                    payload = {k: v for k, v in ev.items() if k != "type"}
                    yield {"event": t, "data": json.dumps(payload, default=str)}
        except Exception:  # noqa: BLE001
            log.exception("chat pipeline failed")
            yield {"event": "error", "data": json.dumps(
                {"message": "Something went wrong while answering. Please try again."})}

    async def agen() -> AsyncIterator[dict]:
        async for item in iterate_in_threadpool(events()):
            if await request.is_disconnected():
                break
            yield item

    return EventSourceResponse(agen(), ping=15)


@router.post("/chat/sync")
@limiter.limit("20/minute")
@limiter.shared_limit(lambda: get_settings().rate_limit_chat, scope="chat-generation",
                      cost=lambda request: getattr(request.state, "generation_cost", 1))
def chat_sync(request: Request, req: ChatRequest, _budget=Depends(_budget_cost)):
    conv_id, history = _prepare(req)
    f = req.filters
    r = run(req.question, history, categories=f.categories if f else None,
            academic_year=f.academic_year if f else None)
    msg_id = _persist(conv_id, req.question, r)
    return _result_payload(r, msg_id, conv_id)


@router.get("/conversations")
def list_conversations(client_id: str = Query(min_length=8, max_length=64),
                       db: Session = Depends(get_db)):
    rows = db.scalars(select(Conversation).where(Conversation.client_id == client_id)
                      .order_by(Conversation.updated_at.desc()).limit(100)).all()
    return [{"id": c.id, "title": c.title, "updated_at": c.updated_at} for c in rows]


def _owned(db: Session, conv_id: str, client_id: str) -> Conversation:
    conv = db.get(Conversation, conv_id)
    if conv is None or conv.client_id != client_id:
        raise HTTPException(404, "Conversation not found")
    return conv


@router.get("/conversations/{conv_id}")
def get_conversation(conv_id: str, client_id: str = Query(min_length=8, max_length=64),
                     db: Session = Depends(get_db)):
    conv = _owned(db, conv_id, client_id)
    return {"id": conv.id, "title": conv.title,
            "messages": [{"id": m.id, "role": m.role, "content": m.content,
                          "citations": m.citations, "meta": m.meta, "created_at": m.created_at}
                         for m in conv.messages]}


@router.patch("/conversations/{conv_id}")
def rename_conversation(conv_id: str, body: RenameRequest,
                        client_id: str = Query(min_length=8, max_length=64),
                        db: Session = Depends(get_db)):
    conv = _owned(db, conv_id, client_id)
    conv.title = body.title.strip()
    return {"ok": True}


@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str, client_id: str = Query(min_length=8, max_length=64),
                        db: Session = Depends(get_db)):
    db.delete(_owned(db, conv_id, client_id))
    return {"ok": True}


@router.post("/feedback")
@limiter.limit("30/minute")
def feedback(request: Request, body: FeedbackRequest, db: Session = Depends(get_db)):
    if body.rating == 0:
        raise HTTPException(422, "rating must be +1 or -1")
    if db.get(Message, body.message_id) is None:
        raise HTTPException(404, "Message not found")
    db.add(Feedback(message_id=body.message_id, rating=body.rating, comment=body.comment))
    return {"ok": True}
