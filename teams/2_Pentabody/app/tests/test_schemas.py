from pydantic import ValidationError

from pentabody_chatbot.schemas import ExtractedQuery, RouteDecision


def test_extracted_query_valid() -> None:
    payload = {
        "audience": "patient",
        "intent": "understand treatment options",
        "topic": "breast cancer",
        "source_hint": "kanker.nl",
        "missing_fields": [],
    }
    parsed = ExtractedQuery.model_validate(payload)
    assert parsed.audience == "patient"


def test_extracted_query_invalid_missing_intent() -> None:
    payload = {
        "audience": "patient",
        "intent": "",
        "topic": "breast cancer",
        "source_hint": "kanker.nl",
        "missing_fields": [],
    }
    try:
        ExtractedQuery.model_validate(payload)
    except ValidationError:
        pass
    else:
        raise AssertionError("Expected validation error for empty intent")


def test_route_decision_valid() -> None:
    route = RouteDecision(
        source_id="kanker.nl",
        source_name="kanker.nl",
        reason="Patient information",
        source_url="https://www.kanker.nl/",
    )
    assert route.source_id == "kanker.nl"
