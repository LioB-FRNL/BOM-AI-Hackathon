import httpx
from openai import BadRequestError

from pentabody_chatbot.openai_client import OpenAIExtractor
from pentabody_chatbot.schemas import ExtractedQuery


def _extracted(audience: str = "patient") -> ExtractedQuery:
    return ExtractedQuery.model_validate(
        {
            "audience": audience,
            "intent": "understand options",
            "topic": "colon cancer",
            "source_hint": "kanker.nl",
            "missing_fields": [],
        }
    )


def test_match_cancer_type_returns_valid_slug(monkeypatch) -> None:
    extractor = OpenAIExtractor(api_key="fake", model="gpt-4.1-mini", timeout_seconds=1)

    monkeypatch.setattr(
        extractor,
        "_run_text_completion",
        lambda system_prompt, user_prompt: " Prostaatkanker. ",
    )

    match = extractor.match_cancer_type(_extracted(), ["prostaatkanker", "longkanker"])
    assert match == "prostaatkanker"


def test_normalize_extraction_payload_fills_empty_object() -> None:
    extractor = OpenAIExtractor(api_key="fake", model="gpt-4.1-mini", timeout_seconds=1)

    payload = extractor._normalize_extraction_payload({})

    assert payload["audience"] == "unknown"
    assert payload["intent"] == "unknown"
    assert payload["topic"] == "unknown"
    assert payload["source_hint"] == "unknown"
    assert payload["missing_fields"] == ["audience", "intent", "topic", "source_hint"]


def test_audience_mapping_healthcare_professional_to_medical_practitioner() -> None:
    extractor = OpenAIExtractor(api_key="fake", model="gpt-4.1-mini", timeout_seconds=1)
    profile = extractor._build_profile(
        extracted=_extracted(audience="healthcare_professional"),
        matched_cancer_type="prostaatkanker",
    )
    assert profile["user_category"] == "medical_practitioner"
    assert profile["expertise_level"] == "expert"


def test_summary_prompt_template_values_are_rendered() -> None:
    extractor = OpenAIExtractor(api_key="fake", model="gpt-4.1-mini", timeout_seconds=1)
    profile = extractor._build_profile(
        extracted=_extracted(audience="healthcare_professional"),
        matched_cancer_type="prostaatkanker",
    )
    rendered = extractor._render_summary_prompt(
        "Category=<user_category> Expertise=<expertise_level> Disease=<disease_type>",
        profile,
    )
    assert "medical_practitioner" in rendered
    assert "expert" in rendered
    assert "prostaatkanker" in rendered


def test_generate_summary_context_overflow_falls_back_to_chunked(monkeypatch) -> None:
    extractor = OpenAIExtractor(api_key="fake", model="gpt-4.1-mini", timeout_seconds=1)

    req = httpx.Request("POST", "https://api.openai.com/v1/responses")
    resp = httpx.Response(400, request=req)

    calls = {"count": 0}

    def fake_run(system_prompt: str, user_prompt: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise BadRequestError(
                "context length exceeded",
                response=resp,
                body={"error": {"message": "context length exceeded"}},
            )
        if "FINAL MODE" in user_prompt:
            return "final-summary"
        return "chunk-digest"

    monkeypatch.setattr(extractor, "_run_text_completion", fake_run)

    source_texts = ["a" * 30000, "b" * 30000]
    output = extractor.generate_summary(
        extracted=_extracted(),
        matched_cancer_type="prostaatkanker",
        source_texts=source_texts,
        history=[{"role": "user", "content": "help me"}],
        structured_data=['{"source":"nkr-cijfers"}'],
    )

    assert output == "final-summary"
    assert calls["count"] >= 4
