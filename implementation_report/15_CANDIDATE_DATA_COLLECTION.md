# 15 — Candidate Data Collection

## What the System Collects

### Candidate Profile

| Data | Source | Where Stored |
|------|--------|-------------|
| Name | WebSocket init_data["name"] | interview_sessions.candidate_name |
| Seniority level chosen | WebSocket init_data["level"] (STUDENT/MEDIUM/HARD) | interview_sessions.seniority_tier |
| Introduction text | First spoken turn (STT transcript) | interview_sessions.intro_blueprint.intro_text |
| Claimed projects / technologies | Extracted from introduction via vector matching | intro_blueprint.candidate_topics |
| Detected programming ecosystem | Keyword regex on introduction | intro_blueprint.ecosystem_summary |

No resume, education, employer, or contact information is collected.
No identity verification is performed.

### Interview Evidence

| Data | Source | Where Stored |
|------|--------|-------------|
| Raw audio PCM | Browser AudioWorklet -> forwarded to Gemini Live | NOT persisted (only debug WAV files per turn in debug/) |
| Candidate transcripts (all turns) | Gemini Live input_transcription | turn_telemetry_logs.candidate_transcript |
| Response latency (ms) | Time from Alex finishing to candidate speaking | turn_telemetry_logs.latency_ms |
| Evaluator observation (0/1) | Shadow Evaluator | turn_telemetry_logs.evaluator_observation |
| Depth score | Shadow Evaluator | turn_telemetry_logs.depth_score |
| BKT mastery progression | BKT engine | turn_telemetry_logs.bkt_prior + bkt_posterior |
| BII (behavioral integrity) | Proctor engine | turn_telemetry_logs.proctor_bii |
| Rubric items (pass/fail per criterion) | Shadow Evaluator | In-memory turns_history only (NOT in PostgreSQL) |
| Evaluator summary text | Shadow Evaluator | In-memory turns_history only (NOT in PostgreSQL) |
| Alex's questions | Gemini Live output_transcription | turn_telemetry_logs.interviewer_prompt |

### Skill Evidence per Domain

| Domain | Status | Mechanism |
|--------|--------|-----------|
| Distributed Systems / Caching | IMPLEMENTED | DISTRIBUTED_CACHING pillar BKT |
| Concurrency / Async | IMPLEMENTED | ASYNC_CONCURRENCY pillar BKT |
| Databases / SQL | IMPLEMENTED | DATABASE_MODELING_TRANSACTIONS pillar BKT |
| AI/ML Systems | IMPLEMENTED | AI_INFERENCE_ORCHESTRATION pillar BKT |
| Cloud / DevOps | PARTIALLY | CONTAINER_INFRASTRUCTURE pillar BKT |
| Event Streaming | IMPLEMENTED | EVENT_STREAMING_MESSAGING pillar BKT |
| API Design | IMPLEMENTED | API_DESIGN_PROTOCOLS pillar BKT |
| Security / Auth | PARTIALLY | SECURITY_AUTH_IDENTITY pillar defined; must be vector-matched |
| Data Structures / Algorithms | PARTIALLY | DATA_STRUCTURES_ALGORITHMS pillar; triggered by intro keywords |
| NoSQL Storage | PARTIALLY | NOSQL_SPECIALIZED_STORAGE pillar; triggered by intro keywords |
| Python Backend | PARTIAL | Ecosystem dialect only; no dedicated Python-only pillar |
| Java / JVM | PARTIAL | Ecosystem dialect only; no dedicated Java pillar |
| Mobile / Flutter | NOT IMPLEMENTED | No pillar, no ecosystem |
| Full Stack | NOT IMPLEMENTED | No pillar, no ecosystem |
| System Design | IMPLEMENTED (via multiple pillars) | Covered across DISTRIBUTED_CACHING, ASYNC_CONCURRENCY, etc. |

### Behavioral Evidence

| Signal | Method | Where |
|--------|--------|-------|
| Response latency distribution | Measured per turn (ms) | proctor_engine.py _evaluate_latency_distribution() |
| Type-Token Ratio (TTR) | Lexical diversity of transcript | proctor_engine.py _calculate_lexical_metrics() |
| Shannon entropy | Word frequency distribution | proctor_engine.py _calculate_lexical_metrics() |
| Clarifying questions asked | Regex detection | proctor_engine.py clarification_regex |
| Contradiction probe survival | Passed/failed flag | proctor_engine.py record_turn() |

Copilot signature detected when: mean_latency > 2000ms AND jitter_std < 180ms

### Debug Audio Files

For each candidate turn, a WAV file is saved to debug/turn_{N}.wav
File: 16kHz, 16-bit, mono PCM
This is purely for diagnostic purposes; not used in evaluation.
