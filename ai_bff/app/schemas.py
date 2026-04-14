from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HostContext(BaseModel):
    version: str = Field(default="1.0")
    timestamp: str | None = None
    route: dict[str, Any] = Field(default_factory=dict)
    page: dict[str, Any] = Field(default_factory=dict)
    user: dict[str, Any] = Field(default_factory=dict)
    permissions: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    message: str
    context: HostContext | dict[str, Any] = Field(default_factory=dict)
    mode: Literal["local", "iframe"] = "local"


class ChatResponse(BaseModel):
    answer: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    route: dict[str, Any] | None = None
    ai_generated: bool = True
    source: str = "bff"


class KeywordRequest(BaseModel):
    text: str
    context: HostContext | dict[str, Any] = Field(default_factory=dict)


class KeywordResponse(BaseModel):
    keywords: list[str]
    explain: str
    ai_generated: bool = True


class SimilarQuestionRequest(BaseModel):
    question: str
    context: HostContext | dict[str, Any] = Field(default_factory=dict)
    limit: int = 3


class SimilarQuestionItem(BaseModel):
    questionId: int
    title: str
    link: str


class SimilarQuestionResponse(BaseModel):
    items: list[SimilarQuestionItem]
    ai_generated: bool = True


class NoteSummaryRequest(BaseModel):
    note_id: int
    keyword: str | None = None
    context: HostContext | dict[str, Any] = Field(default_factory=dict)


class NoteSummaryResponse(BaseModel):
    note: dict[str, Any]
    summary: str
    related_notes: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    ai_generated: bool = True


class QuestionReferenceRequest(BaseModel):
    question_id: str
    context: HostContext | dict[str, Any] = Field(default_factory=dict)


class QuestionReferenceResponse(BaseModel):
    question: dict[str, Any]
    references: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    summary: str
    ai_generated: bool = True
