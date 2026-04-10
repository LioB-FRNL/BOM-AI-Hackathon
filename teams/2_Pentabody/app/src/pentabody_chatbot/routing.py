"""Placeholder routing logic for trusted sources.

TODO: replace deterministic rules with retrieval/RAG + citation scoring.
"""

from __future__ import annotations

from dataclasses import dataclass

from pentabody_chatbot.schemas import ExtractedQuery, RouteDecision


@dataclass(frozen=True)
class SourceEntry:
    source_id: str
    source_name: str
    source_url: str


SOURCES: dict[str, SourceEntry] = {
    "kanker.nl": SourceEntry("kanker.nl", "kanker.nl", "https://www.kanker.nl/"),
    "iknl.nl": SourceEntry("iknl.nl", "iknl.nl", "https://www.iknl.nl/"),
    "nkr-cijfers": SourceEntry(
        "nkr-cijfers", "nkr-cijfers", "https://nkr-cijfers.iknl.nl/"
    ),
    "kankeratlas": SourceEntry(
        "kankeratlas", "kankeratlas", "https://kankeratlas.iknl.nl/"
    ),
    "richtlijnendatabase": SourceEntry(
        "richtlijnendatabase",
        "richtlijnendatabase",
        "https://richtlijnendatabase.nl/",
    ),
    "iknl-reports": SourceEntry(
        "iknl-reports", "IKNL reports", "https://iknl.nl/onderzoek/publicaties"
    ),
    "scientific-publications": SourceEntry(
        "scientific-publications",
        "scientific publications",
        "https://iknl.nl/onderzoek/publicaties",
    ),
}


def route_extracted_query(extracted: ExtractedQuery) -> RouteDecision:
    hint = extracted.source_hint
    if hint in SOURCES:
        source = SOURCES[hint]
        return RouteDecision(
            source_id=source.source_id,
            source_name=source.source_name,
            source_url=source.source_url,
            reason=f"Using model source_hint '{hint}'.",
        )

    topic = extracted.topic.lower()
    intent = extracted.intent.lower()

    if any(token in topic for token in ["guideline", "protocol", "treatment guidance"]):
        source = SOURCES["richtlijnendatabase"]
    elif any(token in intent for token in ["statistics", "incidence", "trend", "numbers"]):
        source = SOURCES["nkr-cijfers"]
    elif any(token in topic for token in ["regional", "region", "geography", "map"]):
        source = SOURCES["kankeratlas"]
    elif extracted.audience in {"patient", "caregiver", "general_public"}:
        source = SOURCES["kanker.nl"]
    elif extracted.audience in {"healthcare_professional"}:
        source = SOURCES["richtlijnendatabase"]
    elif extracted.audience in {"researcher", "policy_maker"}:
        source = SOURCES["iknl.nl"]
    else:
        source = SOURCES["iknl.nl"]

    return RouteDecision(
        source_id=source.source_id,
        source_name=source.source_name,
        source_url=source.source_url,
        reason="Fallback heuristic based on audience/intent/topic.",
    )
