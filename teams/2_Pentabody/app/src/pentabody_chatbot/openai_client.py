"""OpenAI Responses API adapter."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openai import BadRequestError, OpenAI

from pentabody_chatbot.prompts import EXTRACTION_INSTRUCTIONS, SYSTEM_PROMPT
from pentabody_chatbot.schemas import ExtractedQuery

TEAM_DIR = Path(__file__).resolve().parents[3]
PROMPT_DIR = TEAM_DIR / "Persona_templates"
CANCER_MATCHER_PROMPT_PATH = PROMPT_DIR / "cancer_matcher.md"
SUMMARY_MAKER_PROMPT_PATH = PROMPT_DIR / "summary_maker.md"


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

    def match_cancer_type(self, extracted: ExtractedQuery, cancer_types: list[str]) -> str | None:
        if not cancer_types:
            return None

        base_prompt = self._sanitize_cancer_matcher_prompt(
            CANCER_MATCHER_PROMPT_PATH.read_text(encoding="utf-8")
        )
        matcher_prompt = (
            f"{base_prompt}\n\n"
            "Rules:\n"
            "- Reply with exactly one item from the allowed list below.\n"
            "- If unclear, reply exactly with: unknown\n"
            f"Allowed cancer types: {json.dumps(cancer_types, ensure_ascii=False)}"
        )

        user_input = (
            "Extracted user profile JSON:\n"
            f"{extracted.model_dump_json(indent=2)}\n\n"
            "Return only the matched cancer type slug or 'unknown'."
        )
        result = self._run_text_completion(system_prompt=matcher_prompt, user_prompt=user_input)
        normalized = self._normalize_cancer_slug(result)

        if normalized in set(cancer_types):
            return normalized
        return None

    def generate_summary(
        self,
        extracted: ExtractedQuery,
        matched_cancer_type: str,
        source_texts: list[str],
        history: list[dict[str, str]],
    ) -> str:
        summary_prompt_template = SUMMARY_MAKER_PROMPT_PATH.read_text(encoding="utf-8")
        profile = self._build_profile(extracted=extracted, matched_cancer_type=matched_cancer_type)
        summary_prompt = self._render_summary_prompt(summary_prompt_template, profile)
        discussion_log = self._format_discussion_log(history)
        raw_context = self._format_source_context(source_texts)

        user_payload = self._build_summary_user_payload(
            profile=profile,
            discussion_log=discussion_log,
            source_context=raw_context,
        )

        try:
            return self._run_text_completion(system_prompt=summary_prompt, user_prompt=user_payload)
        except BadRequestError as exc:
            if not self._is_context_limit_error(exc):
                raise

        return self._generate_summary_chunked(
            summary_prompt=summary_prompt,
            profile=profile,
            discussion_log=discussion_log,
            source_texts=source_texts,
        )

    def _generate_summary_chunked(
        self,
        summary_prompt: str,
        profile: dict[str, str],
        discussion_log: str,
        source_texts: list[str],
    ) -> str:
        chunks = self._chunk_source_texts(source_texts, max_chars=28000)
        chunk_summaries: list[str] = []

        for idx, chunk in enumerate(chunks, start=1):
            chunk_payload = self._build_summary_user_payload(
                profile=profile,
                discussion_log=discussion_log,
                source_context=chunk,
            )
            chunk_payload += (
                "\n\nCHUNK MODE:\n"
                f"You are processing chunk {idx}/{len(chunks)}. "
                "Provide a concise factual evidence digest grounded only in this chunk."
            )
            chunk_summaries.append(
                self._run_text_completion(system_prompt=summary_prompt, user_prompt=chunk_payload)
            )

        merged_context = "\n\n".join(
            f"Chunk digest {i + 1}:\n{summary}" for i, summary in enumerate(chunk_summaries)
        )
        final_payload = self._build_summary_user_payload(
            profile=profile,
            discussion_log=discussion_log,
            source_context=merged_context,
        )
        final_payload += "\n\nFINAL MODE:\nSynthesize the final answer from these chunk digests."
        return self._run_text_completion(system_prompt=summary_prompt, user_prompt=final_payload)

    def _run_text_completion(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.responses.create(
            model=self._model,
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_prompt}],
                },
            ],
        )
        output_text = (response.output_text or "").strip()
        if not output_text:
            raise ValueError("Model returned empty output.")
        return output_text

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

    def _sanitize_cancer_matcher_prompt(self, prompt: str) -> str:
        cleaned = prompt.replace("fthe", "the")
        cleaned = cleaned.replace("Reply only with one answerYou", "Reply only with one answer\nYou")
        marker = "Reply only with one answer"
        if marker in cleaned:
            cleaned = cleaned[: cleaned.index(marker) + len(marker)]
        return cleaned.strip()

    def _normalize_cancer_slug(self, raw: str) -> str:
        value = raw.strip().lower().strip("`\"' ")
        value = re.sub(r"[^a-z0-9\-]", "", value)
        return value

    def _is_context_limit_error(self, exc: BadRequestError) -> bool:
        message = str(exc).lower()
        if "context" in message and "length" in message:
            return True
        if "maximum" in message and "token" in message:
            return True
        return False

    def _build_profile(self, extracted: ExtractedQuery, matched_cancer_type: str) -> dict[str, str]:
        category = extracted.audience
        mapped_category = "medical_practitioner" if category == "healthcare_professional" else category
        expertise = {
            "patient": "beginner",
            "caregiver": "beginner",
            "general_public": "beginner",
            "policy_maker": "intermediate",
            "researcher": "expert",
            "medical_practitioner": "expert",
        }.get(mapped_category, "intermediate")
        return {
            "user_category": mapped_category,
            "expertise_level": expertise,
            "user_goal": extracted.intent,
            "age": "unknown",
            "gender": "unknown",
            "disease_type": matched_cancer_type,
        }

    def _format_discussion_log(self, history: list[dict[str, str]]) -> str:
        lines: list[str] = []
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _format_source_context(self, source_texts: list[str]) -> str:
        return "\n\n".join(f"Source excerpt {idx + 1}:\n{text}" for idx, text in enumerate(source_texts))

    def _build_summary_user_payload(
        self,
        profile: dict[str, str],
        discussion_log: str,
        source_context: str,
    ) -> str:
        return (
            "PROFILE:\n"
            f"- user_category: {profile['user_category']}\n"
            f"- expertise_level: {profile['expertise_level']}\n"
            f"- user_goal: {profile['user_goal']}\n"
            f"- age: {profile['age']}\n"
            f"- gender: {profile['gender']}\n"
            f"- disease_type: {profile['disease_type']}\n\n"
            "DISCUSSION LOG:\n"
            f"{discussion_log}\n\n"
            "STRUCTURED DATA / SOURCE TEXT:\n"
            f"{source_context}"
        )

    def _chunk_source_texts(self, source_texts: list[str], max_chars: int) -> list[str]:
        chunks: list[str] = []
        current: list[str] = []
        current_size = 0

        for text in source_texts:
            entry = text if len(text) <= max_chars else text[:max_chars]
            if current_size + len(entry) > max_chars and current:
                chunks.append("\n\n".join(current))
                current = [entry]
                current_size = len(entry)
            else:
                current.append(entry)
                current_size += len(entry)

        if current:
            chunks.append("\n\n".join(current))

        return chunks

    def _render_summary_prompt(self, template: str, profile: dict[str, str]) -> str:
        rendered = template
        for key, value in profile.items():
            rendered = rendered.replace(f"<{key}>", value)
        return rendered
