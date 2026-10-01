# 00 — Current Implementation Audit (Truth Map)

## What the System Currently Does

The Socratic Interview Engine is a real-time AI voice interview platform.
A candidate connects via browser WebSocket, speaks to "Alex" (an LLM-powered voice interviewer),
and is simultaneously evaluated by a shadow LLM that runs rubric scoring in the background.
Mathematical engines (BKT, MIRT, Graph) track competency across multiple skill dimensions.
Final assessment reports are generated and archived to PostgreSQL.

---

## Major Components

| Component | File | Status |
|-----------|------|--------|
| WebSocket Interview Orchestrator | app/live_server.py | IMPLEMENTED |
| Shadow Evaluator (REST) | app/evaluator_engine.py | IMPLEMENTED |
| Bayesian Knowledge Tracing | app/bkt_engine.py | IMPLEMENTED |
| Policy Router / FSM | app/policy_router.py | IMPLEMENTED |
| Knowledge Graph (HHGKT) | app/graph_engine.py | IMPLEMENTED |
| MIRT 5D Engine | app/mirt_engine.py | IMPLEMENTED |
| Behavioral Proctor | app/proctor_engine.py | IMPLEMENTED |
| CPF / Master Scorer | app/cpf_engine.py | IMPLEMENTED (not fully wired) |
| Dual Report Generator | app/report_generator.py | IMPLEMENTED |
| Vector DB Service | app/vector_service.py | IMPLEMENTED |
| PostgreSQL DB Service | app/db_service.py | IMPLEMENTED |
| Ecosystem Detector | app/ecosystem_service.py | IMPLEMENTED |
| Logger | app/logger.py | IMPLEMENTED |
| Speech Cleaner | app/speech_cleaner.py | IMPORTED, NOT USED |
| Whisper Engine | app/whisper_engine.py | NOT USED |

---

## Implementation Status per Feature

### IMPLEMENTED
- Real-time bidirectional audio via Gemini Live API
- Native VAD and STT via Gemini Live
- Async shadow evaluation via Gemini REST
- BKT Bayesian posterior update with slip floor
- 4-level scaffolding ladder (L0-L3) with anti-coaching decay
- Devil's Advocate protocol triggered on mastery surge
- MIRT 5-dimensional ability tracking with gradient updates
- HHGKT knowledge graph with prerequisite + co-requisite edges
- Graph message-passing mastery propagation
- Behavioral proctoring: TTR entropy, latency jitter, contradiction probe
- BII (Behavioral Integrity Index) scoring
- Vector similarity search for pillar matching (DynamoDB / Dynoxide)
- Ecosystem detection (JAVA_JVM, PYTHON, GOLANG, NODE_TS, CPP_RUST)
- Polyglot project binding per pillar
- Dual-report generation (Student + Evaluator)
- PostgreSQL persistence (sessions, turns, reports, topic cards)
- Session resumption via Gemini Live handle
- Context window compression (sliding window)
- Real-time telemetry WebSocket broadcast
- Multi-page frontend (/, /telemetry, /reports, /logs, /architecture)
- REST API for session control (pause, resume, finish, state, turns)
- Auto-report generation on disconnect
- Session cache for telemetry resilience across reconnects

### PARTIALLY IMPLEMENTED
- CPF (Cognitive Potential Fingerprint): cpf_engine.py fully coded but generate_cpf() not called in pipeline
- Speech cleaning: speech_cleaner.py exists; not applied to live transcripts
- Contradiction probe: infrastructure exists; not auto-triggered by PolicyRouter
- Role-specific pillar taxonomy: Python/Java detected via keywords but no dedicated pillar set

### REFERENCED BUT NOT IMPLEMENTED
- whisper_engine.py: present in app/ but no import in live_server.py
- Pre-locked rubric: rubric is generated in same LLM call as evaluation (answer-aware)
- Question bank / registry: all questions generated ad-hoc by Gemini Live

### NOT IMPLEMENTED
- Authentication / JWT / candidate identity verification
- Mobile / Flutter / Android pillar definitions
- Full Stack pillar definitions
- DevOps-specific pillar
- Role-specific report (Report 2 per target role)
- Question deduplication
- Concurrent session limits / rate limiting

---

## Answers to the 20 Core Questions

1. **What does the system do?** Real-time Socratic voice interview with async LLM evaluation, BKT tracking, adaptive scaffolding, and dual-report generation.

2. **Major components?** Alex (Gemini Live), Shadow Evaluator, BKT, MIRT, Graph, Proctor, CPF, ReportGen, VectorDB, PostgreSQL, EcosystemService.

3. **Responsibility of each?** See table above.

4. **Which file implements each?** See table above.

5. **API calls involved?**
   - WebSocket /ws/interview (main)
   - GET /api/session/{id}/state
   - POST /api/session/{id}/pause|resume|finish
   - GET /api/session/{id}/intermediate-report
   - GET /api/session/{id}/turns
   - GET /api/reports, GET /api/reports/{id}
   - GET /api/db/overview, GET /api/vector/status

6. **Data entering each component?** Documented per engine in individual engine files.

7. **Data leaving each component?** Documented per engine in individual engine files.

8. **DB tables?** interview_sessions, compacted_topic_cards, turn_telemetry_logs, final_reports + DynamoDB CompetencyPillars.

9. **LLM used and where?**
   - Gemini Live gemini-3.8-live: Alex interviewer
   - gemini-3.1-flash-lite: Shadow Evaluator
   - gemini-2.5-flash / gemini-2.0-flash: Report generator
   - gemini-embedding-2: Vector embeddings

10. **Prompts used?** Alex system prompt (per level), per-turn payloads, Shadow Evaluator rubric prompt, Report prompts. See 10_PROMPT_ARCHITECTURE.md.

11. **State maintained?** In-memory ACTIVE_SESSIONS dict + SESSION_CACHE dict + PostgreSQL (persistent).

12. **Candidate identified?** By name string from WebSocket init_data["name"]. No auth.

13. **Session identified?** UUID4 hex: sess_<12 chars>, stored in ACTIVE_SESSIONS and PostgreSQL.

14. **Questions selected?** Alex (Gemini Live) generates questions based on server-injected context (topic, ecosystem directive, scaffolding directive). Not from a question bank.

15. **Answers evaluated?** Shadow Evaluator (Gemini REST) returns JSON: observation, depth_score, estimated_difficulty, rubric_items, summary.

16. **Scores calculated?** BKT Bayesian update -> effective mastery P(L). Master Scorer: weighted sum * scaffold multiplier * BII * adversarial multiplier.

17. **Scores persisted?** bkt_prior + bkt_posterior stored per turn in turn_telemetry_logs. Final mastery in final_reports.average_mastery.

18. **Next question determined?** PolicyDirective.next_action: DEEPEN_EXPLORATION, SCAFFOLD L1-L3, DEVILS_ADVOCATE, NEXT_SKILL, CONCLUDE_SESSION. Topic selected by graph.get_next_recommended_skill().

19. **Interview terminated?** When graph returns no next skill, or after max 3 turns per topic with mastery threshold met, or explicit finish_interview event.

20. **Final report generated?** generate_student_report() + generate_evaluator_report() called with full session data, saved to disk and PostgreSQL final_reports.
