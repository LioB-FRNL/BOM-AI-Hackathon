# Pentabody Chatbot App

Barebones Streamlit chatbot for the BOM AI Hackathon.

## Quick start

```bash
uv sync
cp .env.example .env
# fill OPENAI_API_KEY in .env
uv run streamlit run streamlit_app.py
```

## What this scaffold does

- Accepts user questions in chat
- Uses OpenAI Responses API to extract a structured JSON payload
- Runs follow-up questions when required fields are missing
- Routes to one trusted source using placeholder heuristics

## Notes

- `SYSTEM_PROMPT` is intentionally blank in `src/pentabody_chatbot/prompts.py`.
- Replace routing heuristics with retrieval/RAG in later iterations.
