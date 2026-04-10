"""Prompt placeholders for the hackathon chatbot."""

# Intentionally blank for teammate ownership.
SYSTEM_PROMPT = ""

# Keep extraction contract isolated from domain/system prompt so prompt changes
# do not break parsable output shape.
EXTRACTION_INSTRUCTIONS = """
You are extracting structured fields from a user conversation.
Return JSON only with keys:
- audience: one of [patient, caregiver, healthcare_professional, policy_maker, researcher, general_public, unknown]
- intent: short label of user goal
- topic: short label of medical/topic focus
- source_hint: one of [kanker.nl, iknl.nl, nkr-cijfers, kankeratlas, richtlijnendatabase, iknl-reports, scientific-publications, unknown]
- missing_fields: list of required fields that are still unclear from [audience, intent, topic, source_hint]
- notes: optional short clarification note

If uncertain, use "unknown" and include missing field names in missing_fields.
""".strip()
