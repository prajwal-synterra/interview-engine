# 01 — System Architecture

## Overview

The system is a single-process Python FastAPI application.
It connects to two external Gemini LLM APIs simultaneously (Live + REST),
a PostgreSQL database, and a DynamoDB-compatible vector database.

## Architecture Topology

```
Browser (WebSocket client)
    |
    | ws://host/ws/interview  (binary audio + JSON control)
    |
FastAPI live_server.py
    |
    +-- Gemini Live API (bidirectional)      <- Alex Interviewer (gemini-3.8-live)
    |       Audio PCM in / Audio PCM out
    |       STT transcription
    |       VAD (native)
    |
    +-- Gemini REST API (async)              <- Shadow Evaluator (gemini-3.1-flash-lite)
    |       Per-turn rubric evaluation
    |
    +-- Gemini REST API (async, report)     <- Report Generator (gemini-2.5-flash)
    |
    +-- Gemini Embedding API               <- Vector Embeddings (gemini-embedding-2)
    |
    +-- DynamoDB / Dynoxide               <- CompetencyPillars vector index (768D)
    |
    +-- PostgreSQL                        <- interview_sessions, turn_telemetry_logs,
                                             compacted_topic_cards, final_reports
```

## Module Dependency Map

```
live_server.py
  -> evaluator_engine.py      (Shadow Evaluator)
  -> policy_router.py         (FSM Orchestrator)
       -> bkt_engine.py       (Bayesian Knowledge Tracing)
       -> graph_engine.py     (Knowledge Graph)
            -> bkt_engine.py
       -> mirt_engine.py      (MIRT 5D Ability)
       -> proctor_engine.py   (Behavioral Proctor)
       -> cpf_engine.py       (Master Scorer)
  -> report_generator.py      (Dual Report Gen)
  -> vector_service.py        (Vector DB)
  -> db_service.py            (PostgreSQL)
  -> ecosystem_service.py     (Ecosystem Detection)
  -> logger.py                (Structured Log)
  -> speech_cleaner.py        (IMPORTED, NOT CALLED)
  -> mirt_engine.get_radar_summary()
```

## Data Flow Summary

1. Browser sends candidate name + level via JSON init
2. Server creates PostgreSQL session, initializes PolicyRouter with seniority-calibrated skills
3. Server connects to Gemini Live, sends greeting prompt
4. Browser streams 16kHz PCM audio bytes via WebSocket binary frames
5. Mic queue forwards PCM to Gemini Live; Gemini transcribes via input_transcription events
6. On mic_stop / end_of_speech: transcript consolidated, Shadow Evaluator fired asynchronously
7. Turn payload injected to Gemini Live -> Alex responds with audio
8. Shadow Evaluator returns observation -> BKT + MIRT + PolicyRouter update
9. Turn telemetry logged to PostgreSQL
10. On topic exhaustion: graph routes to next pillar or concludes
11. On finish: dual reports generated and archived to PostgreSQL + disk
