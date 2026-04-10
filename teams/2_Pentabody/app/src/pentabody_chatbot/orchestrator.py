"""Chat orchestration: follow-up loop + routing."""

from __future__ import annotations

from pentabody_chatbot.config import Settings
from pentabody_chatbot.openai_client import OpenAIExtractor
from pentabody_chatbot.routing import route_extracted_query
from pentabody_chatbot.schemas import AssistantTurn, ExtractedQuery, RouteDecision


class ChatService:
    def __init__(self, settings: Settings) -> None:
        self._extractor = None
        if settings.openai_api_key:
            self._extractor = OpenAIExtractor(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                timeout_seconds=settings.openai_timeout_seconds,
            )

    def next_assistant_turn(self, history: list[dict[str, str]]) -> AssistantTurn:
        if not history:
            return AssistantTurn(
                kind="question",
                message="What is your question and who is it for (patient, professional, policymaker, etc.)?",
            )

        if not self._extractor:
            return AssistantTurn(
                kind="question",
                message=(
                    "OPENAI_API_KEY is not configured yet. Add it to your .env to enable extraction. "
                    "In the meantime, please tell me your audience and topic."
                ),
            )

        extracted = self._extractor.extract_query(history)
        missing = _required_missing(extracted)
        if missing:
            return AssistantTurn(
                kind="question",
                message=_followup_question(missing),
                extracted=extracted,
            )

        route = self.route(extracted)
        return AssistantTurn(
            kind="final",
            message="Thanks. I have enough context and selected a trusted source.",
            extracted=extracted,
            route=route,
        )

    def route(self, extracted: ExtractedQuery) -> RouteDecision:
        return route_extracted_query(extracted)


def _required_missing(extracted: ExtractedQuery) -> list[str]:
    missing = set(extracted.missing_fields)
    if extracted.audience == "unknown":
        missing.add("audience")
    if extracted.source_hint == "unknown":
        missing.add("source_hint")
    if not extracted.intent.strip():
        missing.add("intent")
    if not extracted.topic.strip():
        missing.add("topic")
    return sorted(missing)


def _followup_question(missing_fields: list[str]) -> str:
    parts: list[str] = []
    if "audience" in missing_fields:
        parts.append("Who is the target audience")
    if "intent" in missing_fields:
        parts.append("what you want to achieve")
    if "topic" in missing_fields:
        parts.append("which cancer topic or question area")
    if "source_hint" in missing_fields:
        parts.append("if you prefer a source type (guidelines, statistics, patient info, research)")

    joined = ", ".join(parts)
    return f"To narrow this down, please clarify: {joined}?"
