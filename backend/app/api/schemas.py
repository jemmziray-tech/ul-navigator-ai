from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from ..config import get_settings

_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_YEAR_RE = re.compile(r"^20\d{2}/\d{2}$")


class ChatFilters(BaseModel):
    categories: list[str] | None = Field(default=None, max_length=10)
    academic_year: str | None = None

    @field_validator("academic_year")
    @classmethod
    def _year(cls, v):
        if v and not _YEAR_RE.match(v):
            raise ValueError("academic_year must look like 2026/27")
        return v or None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    client_id: str
    conversation_id: str | None = Field(default=None, max_length=32)
    filters: ChatFilters | None = None
    regenerate: bool = False

    @field_validator("question")
    @classmethod
    def _q(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question is empty")
        if len(v) > get_settings().max_question_chars:
            raise ValueError("question is too long")
        return v

    @field_validator("client_id")
    @classmethod
    def _cid(cls, v: str) -> str:
        if not _CLIENT_ID_RE.match(v):
            raise ValueError("invalid client_id")
        return v


class FeedbackRequest(BaseModel):
    message_id: str = Field(max_length=32)
    rating: int = Field(ge=-1, le=1)
    comment: str | None = Field(default=None, max_length=1000)


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=200)


class CrawlRequest(BaseModel):
    max_pages: int | None = Field(default=None, ge=1, le=5000)
    max_depth: int | None = Field(default=None, ge=0, le=5)
    seeds_only: bool = False
    urls: list[str] | None = Field(default=None, max_length=200)
