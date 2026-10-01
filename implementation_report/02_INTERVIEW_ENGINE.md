# 02 — Interview Engine

## Purpose

Coordinates the full real-time voice interview lifecycle:
audio streaming, transcript consolidation, session phases,
topic management, and injection of Socratic directives to Alex.

## Location

File: app/live_server.py
Function: websocket_interview() (line ~753)
Endpoint: WebSocket /ws/interview

## Session Phases

| Phase | Trigger | Behavior |
|-------|---------|---------|
| INTRO | session start | Collect candidate introduction; run vector search |
| DEEP_DIVE | after first candidate turn | Socratic drill-down on active pillar; max 3 turns or until P(L)>=0.80 |
| WRAPPING_UP | graph exhausted | Warm conclusion; report generation |

## Audio Pipeline

```
Browser AudioWorklet (16kHz, Int16 LE)
    -> WebSocket binary frame
    -> _mic_queue (asyncio.Queue, maxsize=256)
    -> mic_forward_loop() task
    -> session.send_realtime_input(audio=Blob(mime_type="audio/pcm;rate=16000"))
    -> Gemini Live (STT + VAD)
    -> input_transcription events -> candidate_transcript_buffer
```

## Speech Detection

- Browser sends mic_start (-> ActivityStart to Gemini)
- Browser sends mic_stop + end_of_speech (-> ActivityEnd + audio_stream_end)
- Server waits up to 1.0s (TRAILING_STT_WAIT_SEC env var) for trailing STT fragments
- Gemini STT is primary source; Web Speech API transcript is fallback
- Rejection criteria: duration >= 3s AND (chars < 15 OR predominantly non-English)

## Topic Management (DEEP_DIVE)

- After INTRO turn: match_candidate_topics() -> top-3 pillars
- build_dynamic_pillar_graph() constructs knowledge graph for session
- Active topic = policy_router.current_skill (graph-recommended)
- turns_on_active_topic increments per turn; resets on topic transition
- Topic advance when: P(L) >= 0.80 OR turns_on_active_topic >= 3
- Compacted topic card saved to PostgreSQL on topic exit

## Prompt Payload Construction

Each turn payload contains:
1. Candidate answer (quoted as data)
2. Off-topic deflection guard directive (always included)
3. Pedagogical directive (deepen / scaffold / transition)
4. Ecosystem directive (language-specific idioms for active pillar)

No candidate text is ever injected as unquoted system instructions.

## Failure Handling

| Scenario | Response |
|---------|---------|
| No speech detected | send "no_speech_detected" event |
| Non-English / garbled | Alex asks candidate to repeat |
| Gemini Live GoAway | Reconnect using stored resumption_handle |
| Shadow Evaluator timeout (6.5s) | Fallback: pass if answer > 15 words, else fail |
| Gemini Live disconnection | Rebuild session with context_window_compression |
| WebSocket disconnect | Auto-generate reports if turns exist |

## Actual Code Trace (per turn)

```
Browser sends PCM bytes
    -> _mic_queue -> mic_forward_loop -> Gemini Live
Browser sends end_of_speech
    -> trailing wait 1.0s for STT
    -> candidate_transcript_buffer consolidated -> user_text
    -> asyncio.create_task(run_shadow_pipeline(user_text, question))  [background]
    -> server constructs prompt_payload
    -> session.send_client_content(prompt_payload)
    -> Alex (Gemini Live) generates voice response
    -> gemini_receive_loop() streams audio bytes + transcript to browser
    -> alex_turn_complete_event.set()
    -> run_shadow_pipeline() completes:
        -> evaluate_candidate_response() -> observation
        -> policy_router.process_candidate_turn() -> directive
        -> log_turn_telemetry() -> PostgreSQL
        -> broadcast_telemetry() -> browser telemetry UI
```
