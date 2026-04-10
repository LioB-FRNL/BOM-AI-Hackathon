from pentabody_chatbot.routing import SOURCES, route_extracted_query
from pentabody_chatbot.schemas import ExtractedQuery


def _base(**kwargs):
    payload = {
        "audience": "general_public",
        "intent": "learn",
        "topic": "general info",
        "source_hint": "unknown",
        "missing_fields": [],
    }
    payload.update(kwargs)
    return ExtractedQuery.model_validate(payload)


def test_route_uses_source_hint_when_present() -> None:
    route = route_extracted_query(_base(source_hint="nkr-cijfers"))
    assert route.source_id == "nkr-cijfers"


def test_route_guidelines_goes_to_richtlijnen() -> None:
    route = route_extracted_query(_base(topic="guideline for lung cancer"))
    assert route.source_id == "richtlijnendatabase"


def test_route_statistics_goes_to_nkr() -> None:
    route = route_extracted_query(_base(intent="need incidence statistics"))
    assert route.source_id == "nkr-cijfers"


def test_route_map_goes_to_atlas() -> None:
    route = route_extracted_query(_base(topic="regional map variation"))
    assert route.source_id == "kankeratlas"


def test_route_covers_all_registered_sources() -> None:
    required = {
        "kanker.nl",
        "iknl.nl",
        "nkr-cijfers",
        "kankeratlas",
        "richtlijnendatabase",
        "iknl-reports",
        "scientific-publications",
    }
    assert required.issubset(set(SOURCES.keys()))
