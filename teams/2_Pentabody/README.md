# Team 2 (+3)
# Team Name: Pentabody

Team members:
Sakis Lagopoulos
Raymond Pauszek
Remon Dulos
Linda Sudmale
Lionel Blanchet

## Problem statement:

## Proposed AI solution

## Expected impact

## Optional links (demo, slides, video)

## Prototype: chatbot barebones

A minimal Python + Streamlit app is available at `teams/2_Pentabody/app`.

### Run locally

```bash
cd teams/2_Pentabody/app
uv sync
cp .env.example .env
# set OPENAI_API_KEY in .env
uv run streamlit run streamlit_app.py
```

### Current scope

- free-text chatbot UI
- structured follow-up loop to narrow audience and intent
- JSON extraction contract (`audience`, `intent`, `topic`, `source_hint`)
- placeholder routing to trusted hackathon sources
- OpenAI Responses API integration (system prompt intentionally blank placeholder)
