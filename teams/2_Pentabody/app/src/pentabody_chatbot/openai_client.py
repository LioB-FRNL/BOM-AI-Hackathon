"""OpenAI Responses API adapter."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from pentabody_chatbot.prompts import EXTRACTION_INSTRUCTIONS, SYSTEM_PROMPT
from pentabody_chatbot.schemas import ExtractedQuery


class OpenAIExtractor:
    def __init__(self, api_key: str, model: str, timeout_seconds: float = 30) -> None:
        self._model = model
        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds)

    def extract_query(self, history: list[dict[str, str]]) -> ExtractedQuery:
        prompt_input = self._build_input(history)

        response = self._client.responses.create(
            model=self._model,
            input=prompt_input,
            text={"format": {"type": "json_object"}},
        )

        output_text = (response.output_text or "").strip()
        if not output_text:
            raise ValueError("Model returned empty output; expected JSON payload.")

        payload = json.loads(output_text)
        return ExtractedQuery.model_validate(payload)

    def _build_input(self, history: list[dict[str, str]]) -> list[dict[str, Any]]:
        input_messages: list[dict[str, Any]] = []
        if SYSTEM_PROMPT:
            input_messages.append(
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
                }
            )

        input_messages.append(
            {
                "role": "system",
                "content": [{"type": "input_text", "text": EXTRACTION_INSTRUCTIONS}],
            }
        )

        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            content_type = "output_text" if role == "assistant" else "input_text"
            input_messages.append(
                {"role": role, "content": [{"type": content_type, "text": content}]}
            )

        return input_messages
