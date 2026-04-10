"""Chat orchestration: follow-up loop + routing."""

from __future__ import annotations

import json
import re

from parser.parse_kanker_nl import extract, grab_by_type
from parser.parse_nkr_cijfers import get_survival_data

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
        missing = _required_missing(extracted, history)
        if missing:
            return AssistantTurn(
                kind="question",
                message=_followup_question(missing),
                extracted=extracted,
            )

        route = self.route(extracted)
        cancer_types = extract()
        matched_cancer_type = self._extractor.match_cancer_type(extracted, cancer_types)
        if not matched_cancer_type:
            return AssistantTurn(
                kind="question",
                message=(
                    "I can summarize once I know the cancer type. "
                    "Which cancer type are you asking about?"
                ),
                extracted=extracted,
                route=route,
                needs_cancer_clarification=True,
            )

        source_texts = grab_by_type(matched_cancer_type)
        if not source_texts:
            return AssistantTurn(
                kind="question",
                message=(
                    f"I could not find kanker.nl text for '{matched_cancer_type}'. "
                    "Can you clarify the cancer type?"
                ),
                extracted=extracted,
                route=route,
                needs_cancer_clarification=True,
            )

        structured_data = _build_structured_data_blocks(matched_cancer_type)
        final_summary = self._extractor.generate_summary(
            extracted=extracted,
            matched_cancer_type=matched_cancer_type,
            source_texts=source_texts,
            history=history,
            structured_data=structured_data,
        )
        recap = _build_profile_recap(extracted, matched_cancer_type)
        final_message = f"{recap}\n\n{final_summary}"
        return AssistantTurn(
            kind="final",
            message=final_message,
            extracted=extracted,
            route=route,
            matched_cancer_type=matched_cancer_type,
            profile_recap_text=recap,
            final_summary=final_summary,
        )

    def route(self, extracted: ExtractedQuery) -> RouteDecision:
        return route_extracted_query(extracted)


def _required_missing(extracted: ExtractedQuery, history: list[dict[str, str]]) -> list[str]:
    missing = set(extracted.missing_fields)
    if extracted.audience == "unknown":
        missing.add("audience")
    if extracted.source_hint == "unknown":
        missing.add("source_hint")
    if not extracted.intent.strip():
        missing.add("intent")
    if not extracted.topic.strip():
        missing.add("topic")

    user_text = _joined_user_text(history)
    # Force explicit persona confirmation: diagnosis wording alone is not enough.
    if "audience" not in missing and not _has_explicit_audience_signal(user_text):
        missing.add("audience")
    # Force explicit information need/goal before continuing to downstream summary.
    if "intent" not in missing and not _has_explicit_goal_signal(user_text):
        missing.add("intent")

    return sorted(missing)


def _followup_question(missing_fields: list[str]) -> str:
    priority = ["audience", "intent", "topic", "source_hint"]
    for field in priority:
        if field in missing_fields:
            return _question_for_field(field)
    return "Could you clarify your question a bit more?"


def _question_for_field(field: str) -> str:
    if field == "audience":
        return (
            "To tailor this correctly, are you asking for yourself, for someone close to you, "
            "or as a healthcare/policy professional?"
        )
    if field == "intent":
        return (
            "What would you like help with first: understanding diagnosis, treatment options, "
            "side effects, prognosis, or statistics?"
        )
    if field == "topic":
        return "Which cancer type is this about?"
    if field == "source_hint":
        return (
            "Do you prefer patient information, clinical guidelines, or statistics as the primary source?"
        )
    return "Could you clarify your question a bit more?"


def _joined_user_text(history: list[dict[str, str]]) -> str:
    return " ".join(msg.get("content", "") for msg in history if msg.get("role") == "user").lower()


def _has_explicit_audience_signal(text: str) -> bool:
    patterns = [
        r"\bi am\b",
        r"\bi'm\b",
        r"\bfor myself\b",
        r"\bfor my\b",
        r"\bas a\b",
        r"\bik ben\b",
        r"\bvoor mezelf\b",
        r"\bvoor mijn\b",
        r"\bals\b",
    ]
    return any(re.search(p, text) for p in patterns)


def _has_explicit_goal_signal(text: str) -> bool:
    patterns = [
        r"\?$",
        r"\b(i want|i need|can you|could you|help me)\b",
        r"\b(what|how|which|when|why)\b",
        r"\b(ik wil|ik heb nodig|kun je|kunt u|help me)\b",
        r"\b(wat|hoe|welke|wanneer|waarom)\b",
    ]
    return any(re.search(p, text) for p in patterns)


def _build_profile_recap(extracted: ExtractedQuery, matched_cancer_type: str) -> str:
    audience = extracted.audience.replace("_", " ")
    return (
        "What I understood:\n"
        f"- Audience: {audience}\n"
        f"- Goal: {extracted.intent}\n"
        f"- Topic: {extracted.topic}\n"
        f"- Matched cancer type: {matched_cancer_type}"
    )


def _build_structured_data_blocks(matched_cancer_type: str) -> list[str]:
    try:
        survival_data = get_survival_data(matched_cancer_type)
    except Exception:
        return []

    if not survival_data:
        return []

    return [json.dumps(survival_data, ensure_ascii=False, indent=2)]
