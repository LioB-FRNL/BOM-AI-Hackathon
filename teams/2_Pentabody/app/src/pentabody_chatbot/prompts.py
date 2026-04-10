"""Prompt configuration for intake extraction."""

from __future__ import annotations

from pathlib import Path

SYSTEM_PROMPT = ""

TEAM_DIR = Path(__file__).resolve().parents[3]
PROMPT_DIR = TEAM_DIR / "Persona_templates"
CONVERSATION_FIELD_EXTRACTOR_PROMPT_PATH = PROMPT_DIR / "conversation_field_extractor.md"


def _load_prompt(path: Path) -> str:
    prompt = path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError(f"Prompt file is empty: {path}")
    return prompt


CONVERSATION_FIELD_EXTRACTOR_PROMPT = _load_prompt(CONVERSATION_FIELD_EXTRACTOR_PROMPT_PATH)

EXTRACTION_INSTRUCTIONS = f"""
Use the following prompt as the authoritative intake policy for this extraction task.

PROMPT SOURCE:
{CONVERSATION_FIELD_EXTRACTOR_PROMPT}

APPLICATION ADAPTER:
- You are not replying directly to the user.
- Your job is to convert the conversation into structured data that follows the policy above.
- Return JSON only. No markdown, no prose, no code fences.
- Output exactly these keys:
  - audience
  - intent
  - topic
  - source_hint
  - age
  - gender
  - missing_fields
  - notes
- Allowed audience values:
  - patient
  - caregiver
  - healthcare_professional
  - policy_maker
  - researcher
  - general_public
  - unknown
- Allowed source_hint values:
  - kanker.nl
  - iknl.nl
  - nkr-cijfers
  - kankeratlas
  - richtlijnendatabase
  - iknl-reports
  - scientific-publications
  - unknown
- Allowed missing_fields items:
  - audience
  - intent
  - topic
  - source_hint
  - age
  - gender
- Map prompt concepts to app fields as follows:
  - user_category -> audience
  - user_goal -> intent
  - disease_type -> topic
- Output age and gender when the conversation provides them or when they can be inferred confidently from a clearly sex-specific cancer type.
- Do not output expertise_level as a top-level key.
- Never invent facts not present in the conversation.
- If uncertain, set the field to "unknown" and include that field name in missing_fields.
- Use the full conversation history, not just the latest user message.
- Preserve clearly answered fields from earlier turns unless the user corrects them later.
- If the latest user message is a short fragment answering the previous assistant question, treat it as a valid answer.
- notes should be a short factual explanation of ambiguity, or an empty string if none.
""".strip()
