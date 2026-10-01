# Socratic Interview Engine — Implementation Report
**Document Ref:** AIS-ARCH-2026-V3-MASTER
**Audit Date:** 2026-09-30
**Source Root:** `c:\Users\Prajwal\Desktop\projects\interview-engine\`

---

## Report Index

| # | File | Contents |
|---|------|---------|
| 00 | 00_CURRENT_IMPLEMENTATION_AUDIT.md | Full truth map |
| 01 | 01_SYSTEM_ARCHITECTURE.md | Component map, data-flow |
| 02 | 02_INTERVIEW_ENGINE.md | WebSocket orchestration |
| 03 | 03_QUESTION_GENERATION_ENGINE.md | Adaptive Socratic questions |
| 04 | 04_CANDIDATE_EVALUATION_ENGINE.md | Shadow Evaluator |
| 05 | 05_SCORING_ENGINE.md | BKT math, CPF, Master Score |
| 06 | 06_RUBRIC_ENGINE.md | Rubric generation, isolation |
| 07 | 07_SKILL_TRACKING_ENGINE.md | HHGKT graph, propagation |
| 08 | 08_ADAPTIVE_DIFFICULTY_ENGINE.md | MIRT 5D, scaffolding |
| 09 | 09_SESSION_STATE_ENGINE.md | FSM states, lifecycle |
| 10 | 10_PROMPT_ARCHITECTURE_AND_GOVERNANCE.md | Prompt security |
| 11 | 11_DOMAIN_EVALUATION_ENGINE.md | Domain coverage |
| 12 | 12_REPORT_GENERATION_ENGINE.md | Dual report pipeline |
| 13 | 13_LLM_PIPELINE.md | Dual-LLM architecture |
| 14 | 14_DATA_MODEL_AND_DATABASE_FLOW.md | PostgreSQL + DynamoDB |
| 15 | 15_CANDIDATE_DATA_COLLECTION.md | Data collected |
| 16 | 16_COMPLETE_INTERVIEW_WORKFLOW.md | End-to-end flow |
| 17 | 17_SECURITY_AND_TRUST_BOUNDARIES.md | Trust surfaces, vulnerabilities |
| 18 | 18_SCORING_AND_MASTERY_MODEL.md | Full math derivation |
| 19 | 19_RUBRIC_AND_EVIDENCE_MODEL.md | Rubric lifecycle |
| 20 | 20_IMPLEMENTATION_GAPS.md | Gap analysis |

---

## 1. Current Architecture Summary

A real-time voice interview engine with two LLM roles:

| LLM | Model | Role |
|-----|-------|------|
| Alex (Interviewer) | gemini-3.8-live (Gemini Live bidirectional API) | Voice conversation, question generation |
| Shadow Evaluator | gemini-3.1-flash-lite (REST) | Async answer evaluation, rubric scoring |
| Report Generator | gemini-2.5-flash / 2.0-flash (REST) | Dual assessment report generation |

Backend: single FastAPI app (app/live_server.py) + 14 supporting modules.
Storage: PostgreSQL (sessions, turns, reports) + DynamoDB-compatible vector DB (pillar embeddings).

---

## 2. Current Evaluation Pipeline

```
Candidate Audio (16kHz PCM)
   -> WebSocket Binary frames
Mic Queue -> Gemini Live (STT + VAD)
   -> Transcript string
Off-topic Guard -> Prompt Payload -> Gemini Live (Alex voice response)
   -> background asyncio.create_task
Shadow Evaluator (Gemini REST, 6.5s timeout)
   -> observation: 0 or 1, depth_score, estimated_difficulty
BKT Node.update() -> MIRT.update_ability() -> PolicyRouter FSM
   -> PolicyDirective: SCAFFOLD / DEEPEN / NEXT_SKILL / DEVILS_ADVOCATE / CONCLUDE
```

---

## 3. Current Scoring Pipeline

```
observation (0/1)
 -> BKTNode.update()             # Bayesian posterior + anti-coaching decay
 -> MIRTEngine.update_ability()  # 5D online gradient update
 -> PolicyRouter.process_candidate_turn()
 -> (on session end) MasterScorer.calculate_final_score()
 -> save_final_reports() -> PostgreSQL final_reports
```

Master Formula:
  FinalScore = (Sum(w_k * P(L_k))) * ScaffoldMultiplier * BII * AdversarialMultiplier

Hiring thresholds:
  STRONG HIRE: avg P(L) >= 0.80
  HIRE:        avg P(L) >= 0.60
  LEAN HIRE:   avg P(L) >= 0.45
  NO HIRE:     avg P(L) <  0.45

---

## 4. Current Session-Control Model

- Session ID: `sess_<12-hex>` (uuid4), generated at WebSocket connect
- FSM states: READY -> ACTIVE -> SCAFFOLDING_L1/L2/L3 -> DEVILS_ADVOCATE -> COMPLETED
- Phases (live_server.py): INTRO -> DEEP_DIVE -> WRAPPING_UP
- Persisted in: PostgreSQL interview_sessions + in-memory ACTIVE_SESSIONS dict
- Auth: NONE — session ownership = WebSocket connection ownership

---

## 5. Current Prompt Architecture

- Alex system prompt: injected once at Gemini Live session open; immutable thereafter
- Per-turn payloads: server-constructed strings; candidate text embedded as quoted data
- Ecosystem directives: ecosystem-specific idioms injected per active pillar
- Off-topic guard: regex pattern check prepended to every turn payload
- Shadow Evaluator prompt: fully deterministic; candidate answer is a labelled JSON field

---

## 6. Current Security Posture

| Threat | Current Mitigation | Gap |
|--------|-------------------|-----|
| Prompt injection | Off-topic guard + fixed system prompt | Candidate text NOT sanitised before string embed |
| Score manipulation via API | Scores stored server-side only | No API authentication |
| Session hijacking | WS connection = session | No token/auth |
| AI copilot detection | Latency jitter + TTR entropy | Not auto-enforced |
| Contradiction probe | BII penalty -0.35 on fail | Never auto-triggered |

---

## 7. Current Role/Domain Coverage

| Role | Status |
|------|--------|
| General Systems / AI/ML Systems | IMPLEMENTED |
| Python Backend | PARTIAL - ecosystem keyword detection only |
| Java / JVM | PARTIAL - ecosystem directive injected |
| SDE / DSA | PARTIAL - DATA_STRUCTURES_ALGORITHMS pillar |
| Mobile / Flutter / Android | NOT IMPLEMENTED |
| Full Stack | NOT IMPLEMENTED |
| DevOps / Cloud-only | NOT IMPLEMENTED |

---

## 8. Current Report-Generation Capability

- Report 1: Student Career Compass (LLM-generated Markdown, MIRT radar, growth roadmap)
- Report 2: Evaluator Forensic Audit (template + LLM, BKT table, turn audit trail, hiring verdict)
- Both: saved to reports/ disk AND PostgreSQL final_reports
- Triggers: WebSocket finish_interview event, REST POST /api/session/{id}/finish, auto on disconnect

---

## 9. Major Missing Components

1. Authentication / Authorization (no JWT, no identity)
2. Pre-locked rubrics (rubric generated after seeing candidate answer - not isolated)
3. Question bank (all questions LLM-generated ad-hoc)
4. Mobile / Flutter / Full Stack domain pillars
5. Contradiction probe auto-trigger
6. CPF full integration (generate_cpf() never called in live pipeline)
7. whisper_engine.py exists but unused
8. speech_cleaner.py imported but not applied to live transcripts
9. Role-specific report scoping
10. Rate limiting / concurrent session limits

---

## 10. Recommended Implementation Order

1. [CRITICAL] Pre-lock rubric before candidate answers
2. [CRITICAL] Add JWT authentication
3. [CRITICAL] Sanitise candidate text before prompt embedding
4. [HIGH] Wire MasterScorer.generate_cpf() into live pipeline
5. [HIGH] Auto-trigger contradiction probes via PolicyRouter
6. [HIGH] Add Mobile / Flutter / Full Stack pillar definitions
7. [HIGH] Apply speech_cleaner.py to candidate transcripts
8. [MEDIUM] Real token usage (replace estimated accounting)
9. [MEDIUM] Question deduplication registry
10. [FUTURE] Pre-rated question bank with difficulty calibration
