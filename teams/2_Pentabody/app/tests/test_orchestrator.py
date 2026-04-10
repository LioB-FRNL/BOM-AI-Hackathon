from pentabody_chatbot.config import Settings
from pentabody_chatbot.orchestrator import ChatService
from pentabody_chatbot.schemas import ExtractedQuery


class FakeExtractor:
    def __init__(self, extracted: ExtractedQuery):
        self.extracted = extracted

    def extract_query(self, history):
        return self.extracted


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
    assert "clarify" in turn.message


def test_complete_fields_returns_final() -> None:
    service = ChatService(
        Settings(openai_api_key="fake", openai_model="gpt-4.1-mini", openai_timeout_seconds=30)
    )
    service._extractor = FakeExtractor(
        ExtractedQuery.model_validate(
            {
                "audience": "patient",
                "intent": "understand options",
                "topic": "colon cancer",
                "source_hint": "kanker.nl",
                "missing_fields": [],
            }
        )
    )
    turn = service.next_assistant_turn([{"role": "user", "content": "I need info"}])
    assert turn.kind == "final"
    assert turn.route is not None
