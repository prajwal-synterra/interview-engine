# 🎙️ LangGraph Interviewer

An AI-powered technical interview engine built with **LangGraph**, **LangChain**, and **Gemini**.

## Project Structure

```
langgraph-interviewer/
│
├── app/
│   ├── __init__.py       # Package init
│   ├── main.py           # Entry point
│   ├── graph.py          # LangGraph state machine
│   ├── state.py          # Shared state schema
│   ├── nodes.py          # Graph nodes (ask, evaluate)
│   ├── prompts.py        # Prompt templates
│   └── llm.py            # Gemini LLM initialization
│
├── .env                  # API keys (never commit this)
├── requirements.txt      # Python dependencies
└── README.md             # This file
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Add your Google API key to `.env`:

```
GOOGLE_API_KEY=your_key_here
```

### 3. Run Module 0 — Verify Gemini connection

```bash
python -m app.main
```

## Modules

| Module | Status | Description |
|--------|--------|-------------|
| 0 | ✅ Setup | Project setup & Gemini verification |
| 1 | 🔜 | LangGraph interview flow |
| 2 | 🔜 | FastAPI REST endpoints |
| 3 | 🔜 | Frontend integration |
