import pentabody_chatbot.orchestrator as orchestrator_mod
from pentabody_chatbot.config import Settings
from pentabody_chatbot.orchestrator import ChatService
from pentabody_chatbot.schemas import ExtractedQuery


class FakeExtractor:
    def __init__(
        self,
        extracted: ExtractedQuery,
        matched_cancer_type: str | None = "prostaatkanker",
        summary: str = "Summary output",
    ):
        self.extracted = extracted
        self.matched_cancer_type = matched_cancer_type
        self.summary = summary
        self.summary_inputs = None

    def extract_query(self, history):
        return self.extracted

    def match_cancer_type(self, extracted, cancer_types):
        return self.matched_cancer_type

    def generate_summary(
        self, extracted, matched_cancer_type, source_texts, history, structured_data=None
    ):
        self.summary_inputs = {
            "matched_cancer_type": matched_cancer_type,
            "source_texts": source_texts,
            "history": history,
            "structured_data": structured_data,
        }
        return self.summary


def _valid_extracted() -> ExtractedQuery:
    return ExtractedQuery.model_validate(
        {
            "audience": "patient",
            "intent": "understand options",
            "topic": "colon cancer",
            "source_hint": "kanker.nl",
            "missing_fields": [],
        }
    )


def test_missing_api_key_returns_question() -> None:
    service = ChatService(
        Settings(openai_api_key=None, openai_model="gpt-4.1-mini", openai_timeout_seconds=30)
    )
    turn = service.next_assistant_turn([{"role": "user", "content": "help"}])
    assert turn.kind == "question"
    assert "OPENAI_API_KEY" in turn.message


def test_missing_fields_triggers_followup() -> None:
    service = ChatService(
        Settings(openai_api_key="fake", openai_model="gpt-4.1-mini", openai_timeout_seconds=30)
    )
    service._extractor = FakeExtractor(
        ExtractedQuery.model_validate(
            {
                "audience": "unknown",
                "intent": "find information",
                "topic": "breast cancer",
                "source_hint": "unknown",
                "missing_fields": ["audience", "source_hint"],
            }
        )
    )
    turn = service.next_assistant_turn([{"role": "user", "content": "I need help"}])
    assert turn.kind == "question"
    assert "tailor" in turn.message.lower()


def test_implicit_role_and_goal_trigger_followup_even_if_extractor_fills_fields() -> None:
    service = ChatService(
        Settings(openai_api_key="fake", openai_model="gpt-4.1-mini", openai_timeout_seconds=30)
    )
    service._extractor = FakeExtractor(
        ExtractedQuery.model_validate(
            {
                "audience": "patient",
                "intent": "understand diagnosis",
                "topic": "leukemia",
                "source_hint": "kanker.nl",
                "missing_fields": [],
            }
        )
    )
    turn = service.next_assistant_turn(
        [{"role": "user", "content": "My doctor said I might have leukemia"}]
    )
    assert turn.kind == "question"
    assert "yourself" in turn.message.lower() or "someone close" in turn.message.lower()


def test_no_match_triggers_targeted_followup(monkeypatch) -> None:
    service = ChatService(
        Settings(openai_api_key="fake", openai_model="gpt-4.1-mini", openai_timeout_seconds=30)
    )
    service._extractor = FakeExtractor(_valid_extracted(), matched_cancer_type=None)

    monkeypatch.setattr(orchestrator_mod, "extract", lambda: ["prostaatkanker", "longkanker"])

    turn = service.next_assistant_turn(
        [
            {
                "role": "user",
                "content": "I am asking for myself and I need treatment options for leukemia.",
            }
        ]
    )
    assert turn.kind == "question"
    assert turn.needs_cancer_clarification is True
    assert "cancer type" in turn.message.lower()


def test_complete_fields_returns_final_with_summary(monkeypatch) -> None:
    service = ChatService(
        Settings(openai_api_key="fake", openai_model="gpt-4.1-mini", openai_timeout_seconds=30)
    )
    fake_extractor = FakeExtractor(_valid_extracted(), matched_cancer_type="prostaatkanker")
    service._extractor = fake_extractor

    monkeypatch.setattr(orchestrator_mod, "extract", lambda: ["prostaatkanker", "longkanker"])
    monkeypatch.setattr(
        orchestrator_mod,
        "grab_by_type",
        lambda kind: [f"text-for-{kind}", "second-page"],
    )
    monkeypatch.setattr(
        orchestrator_mod,
        "get_survival_data",
        lambda kind: {"source": "nkr-cijfers", "matched_kankersoort": {"code": kind}},
    )

    turn = service.next_assistant_turn(
        [
            {
                "role": "user",
                "content": "I am asking for myself and I need treatment options for leukemia.",
            }
        ]
    )
    assert turn.kind == "final"
    assert turn.route is not None
    assert turn.matched_cancer_type == "prostaatkanker"
    assert turn.final_summary == "Summary output"
    assert "What I understood" in turn.message
    assert fake_extractor.summary_inputs is not None
    assert fake_extractor.summary_inputs["source_texts"] == [
        "text-for-prostaatkanker",
        "second-page",
    ]
    assert fake_extractor.summary_inputs["structured_data"] is not None
    assert '"source": "nkr-cijfers"' in fake_extractor.summary_inputs["structured_data"][0]
