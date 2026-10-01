# 13 — LLM Pipeline

## Dual-LLM Architecture

The system uses two completely separate LLM clients to isolate conversation
from evaluation. This is called the "Quarantined Dual-LLM Architecture".

| LLM | Client | API Key | Model | Purpose |
|-----|--------|---------|-------|---------|
| Alex (Live) | genai.Client(live_voice_api_key) | GEMINI_LIVE_VOICE_API_KEY or GEMINI_API_KEY | gemini-3.8-live | Bidirectional voice interview |
| Shadow Evaluator | genai.Client(evaluator_api_key) | EVALUATOR_API_KEY or GEMINI_API_KEY | gemini-3.1-flash-lite | Rubric evaluation (REST) |
| Report Generator | genai.Client(evaluator_api_key) | EVALUATOR_API_KEY or GEMINI_API_KEY | gemini-2.5-flash (primary), gemini-2.0-flash (fallback) | Report narrative |
| Embeddings | genai.Client(GEMINI_API_KEY) | GEMINI_API_KEY | gemini-embedding-2 | Pillar vector embeddings |

## Alex LLM (Gemini Live)

Protocol: Bidirectional WebSocket (Gemini Live API, v1beta)
Connection: client.aio.live.connect(model, config)
Audio in: PCM 16kHz via session.send_realtime_input(audio=Blob)
Audio out: PCM chunks in model_turn.parts[*].inline_data
STT: Gemini native via input_transcription events
VAD: disabled (browser-managed VAD with server activity_start/end signals)
Session resumption: SessionResumptionConfig(handle=resumption_handle)
Context compression: ContextWindowCompressionConfig(sliding_window=SlidingWindow())

Text injection to Alex: session.send_client_content(turns=[Content(role="user")])
This is how all per-turn prompt payloads are delivered.

## Shadow Evaluator LLM (Gemini REST)

Protocol: async REST via client.aio.models.generate_content()
Model: gemini-3.1-flash-lite
Config: response_mime_type="application/json"
Timeout: 6.5s (asyncio.wait_for)
Rate: one call per candidate turn
Runs as: asyncio.create_task (background, does not block audio)

## Report Generator LLM

Protocol: async REST via client.aio.models.generate_content()
Models: gemini-2.5-flash -> gemini-2.0-flash (fallback on exception)
No structured JSON output required (free-form Markdown)
Called for: generate_student_report() only
Evaluator report is template-only (no separate LLM call needed)

## Token Accounting

Alex tokens: estimated from word count * 1.35 approximation
Shadow evaluator tokens: from response.usage_metadata (real when available, fallback to 320/85/405)
Tracked in llm_metrics dict: total_calls, prompt_tokens, completion_tokens, total_tokens, calls_log
NOTE: Alex token estimates are NOT from real usage_metadata (Gemini Live API does not expose per-turn token counts in the same way)

## Failure Handling

| Failure | Response |
|---------|---------|
| Shadow Evaluator timeout | Fallback heuristic (word count > 15 -> pass) |
| Shadow Evaluator invalid JSON | Exception caught -> fallback |
| Report LLM failure (all models) | Structural fallback template returned |
| Gemini Live disconnect | reconnect_gemini() with saved handle |
| Embedding failure | Zero vector returned (silently degrades to fallback pillars) |

## Environment Variables

| Variable | Default | Usage |
|----------|---------|-------|
| GEMINI_API_KEY | required | Default API key for all clients |
| GEMINI_LIVE_VOICE_API_KEY | falls back to GEMINI_API_KEY | Alex Live voice |
| EVALUATOR_API_KEY | falls back to GEMINI_API_KEY | Shadow Evaluator + Reports |
| GEMINI_LIVE_VOICE_MODEL | gemini-3.8-live | Alex model name |
| TRAILING_STT_WAIT_SEC | 1.0 | Wait time for trailing STT fragments |
| IS_PRODUCTION | false | Switches DynamoDB to production AWS |
| PG_HOST / PG_PORT / PG_DB / PG_USER / PG_PASSWORD | localhost/5432/interview-engine/postgres/0608 | PostgreSQL connection |
| DYNOXIDE_URL | http://localhost:8001 | Vector DB endpoint |
