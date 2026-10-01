# 14 — Data Model and Database Flow

## PostgreSQL Tables (app/db_service.py init_db())

### Table 1: interview_sessions

| Column | Type | Description |
|--------|------|-------------|
| session_id | VARCHAR(64) PK | sess_<12-hex> UUID4 |
| candidate_name | VARCHAR(100) | From WebSocket init_data.name |
| seniority_tier | VARCHAR(20) | STUDENT / MEDIUM / HARD |
| detected_ecosystem | VARCHAR(50) | Primary ecosystem (e.g. PYTHON) |
| status | VARCHAR(20) | IN_PROGRESS / COMPLETED |
| intro_blueprint | JSONB | {intro_text, matched_pillars, candidate_topics, ecosystem_summary, pillar_ecosystem_map} |
| created_at | TIMESTAMP | Session creation time |
| completed_at | TIMESTAMP | Set on save_final_reports() |

### Table 2: turn_telemetry_logs

| Column | Type | Description |
|--------|------|-------------|
| turn_id | VARCHAR(64) PK | turn_<12-hex> |
| session_id | VARCHAR(64) FK | References interview_sessions |
| turn_index | INT | 1-indexed turn number |
| topic | VARCHAR(100) | Active pillar code |
| interviewer_prompt | TEXT | Alex's question (from alex_latest_question) |
| candidate_transcript | TEXT | STT transcript (user_text) |
| latency_ms | INT | Time between Alex finishing and candidate responding |
| evaluator_observation | INT | 0 or 1 (from Shadow Evaluator) |
| depth_score | FLOAT | Normalised depth score [0.0, 1.0] |
| bkt_prior | FLOAT | BKT P(L) before this turn |
| bkt_posterior | FLOAT | BKT P(L) after posterior update |
| proctor_bii | FLOAT | BII after this turn |
| created_at | TIMESTAMP | Turn timestamp |

### Table 3: compacted_topic_cards

| Column | Type | Description |
|--------|------|-------------|
| card_id | VARCHAR(64) PK | card_<12-hex> |
| session_id | VARCHAR(64) FK | References interview_sessions |
| topic_code | VARCHAR(100) | Pillar code |
| turns_spent | INT | Number of turns on this topic |
| final_mastery_p_l | FLOAT | Terminal BKT P(L) for this pillar |
| status | VARCHAR(20) | MASTERED or INCOMPLETE |
| verdict_summary | TEXT | Plain text summary |
| strengths_cited | JSONB | Array of strength strings (currently empty []) |
| gaps_identified | JSONB | Array of gap strings (currently empty []) |
| created_at | TIMESTAMP | Card creation time |

NOTE: strengths_cited and gaps_identified are always saved as empty arrays
in the current implementation. The fields exist but are not populated from
turn data.

### Table 4: final_reports

| Column | Type | Description |
|--------|------|-------------|
| report_id | VARCHAR(64) PK | rep_<12-hex> |
| session_id | VARCHAR(64) UNIQUE FK | References interview_sessions |
| student_compass_markdown | TEXT | Full student report Markdown |
| evaluator_audit_markdown | TEXT | Full evaluator report Markdown |
| hiring_verdict | VARCHAR(50) | STRONG HIRE / HIRE / LEAN HIRE / NO HIRE |
| average_mastery | FLOAT | Mean P(L) across all skills |
| proctor_integrity_score | FLOAT | Final BII |
| generated_at | TIMESTAMP | Report generation time |

UPSERT: ON CONFLICT (session_id) DO UPDATE (later generation overwrites)

---

## DynamoDB / Dynoxide Table: CompetencyPillars

Vector Index: PillarVectorIndex (768-dimensional COSINE distance)

| Attribute | Type | Description |
|-----------|------|-------------|
| pillarId | String (PK) | e.g. DISTRIBUTED_CACHING |
| name | String | Human-readable name |
| domain | String | Domain category |
| criticality | String | HIGH or MEDIUM |
| descriptors | String | Keyword-rich description (used for embedding) |
| probe | String | Canonical probe question |
| embedding | List<Number> | 768D Gemini embedding vector |

Seeded with 10 pillars on startup (seed_competency_pillars()).
Used for cosine similarity search against candidate introduction text.

---

## Data Flow Diagram

```
Candidate connects (name, level)
    -> interview_sessions INSERT

Candidate speaks intro
    -> CompetencyPillars VECTOR SEARCH -> top-3 pillar IDs
    -> interview_sessions UPDATE (intro_blueprint)

Per turn
    -> turn_telemetry_logs INSERT

Topic exit
    -> compacted_topic_cards INSERT

Session end
    -> final_reports INSERT/UPDATE
    -> interview_sessions UPDATE (status=COMPLETED, completed_at)
```

---

## Security Considerations

- PostgreSQL password hardcoded in default (PG_PASSWORD="0608") — should use env only
- No row-level security: any code with DB access can read all sessions
- JSONB intro_blueprint stores candidate intro text verbatim — PII
- turn_telemetry_logs stores full candidate transcripts — PII
- No data retention policy or TTL mechanism implemented
- No encryption at rest (relies on PostgreSQL defaults)
