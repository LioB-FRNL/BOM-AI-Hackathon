"""Schemas used by orchestrator and UI."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Audience = Literal[
    "patient",
    "caregiver",
    "healthcare_professional",
    "policy_maker",
    "researcher",
    "general_public",
    "unknown",
]

SourceHint = Literal[
    "kanker.nl",
    "iknl.nl",
    "nkr-cijfers",
    "kankeratlas",
    "richtlijnendatabase",
    "iknl-reports",
    "scientific-publications",
    "unknown",
]


class ExtractedQuery(BaseModel):
    audience: Audience
    intent: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    source_hint: SourceHint
    missing_fields: list[Literal["audience", "intent", "topic", "source_hint"]] = Field(
        default_factory=list
    )
    notes: str | None = None


class RouteDecision(BaseModel):
    source_id: str
    source_name: str
    reason: str
    source_url: str


class AssistantTurn(BaseModel):
    kind: Literal["question", "final"]
    message: str
    extracted: ExtractedQuery | None = None
    route: RouteDecision | None = None
    matched_cancer_type: str | None = None
    profile_recap_text: str | None = None
    final_summary: str | None = None
    needs_cancer_clarification: bool = False
