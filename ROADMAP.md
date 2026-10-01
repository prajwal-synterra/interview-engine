# Interview Engine — Build Roadmap
**Branch:** dev/v4
**Philosophy:** Build one engine at a time. Test it. Understand it. Then move forward.

---

## HOW WE WORK

For every step below:
1. Read the relevant implementation_report doc first
2. Build or fix the specific component
3. Write a simple standalone test / demo script
4. Run it and verify the output manually
5. Commit and push
6. Only then move to the next step

We never touch the next step until the current one is understood and working.

---

## PHASE 0 — Project Setup and Dev Environment

### Step 0.1 — Understand the project structure
- [ ] Read 00_CURRENT_IMPLEMENTATION_AUDIT.md
- [ ] Read 01_SYSTEM_ARCHITECTURE.md
- [ ] Confirm which files exist in app/
- Goal: Know the full file tree and what each file does

### Step 0.2 — Environment Setup
- [ ] Create .env file with correct API keys and DB credentials
- [ ] Install dependencies (pip install -r requirements.txt)
- [ ] Verify PostgreSQL is running
- [ ] Verify Dynoxide (DynamoDB local vector DB) is running
- Goal: All services reachable before writing any code

### Step 0.3 — Run the existing system
- [ ] Start the server: uvicorn app.live_server:app --reload
- [ ] Open browser at http://localhost:8000
- [ ] Verify the landing page loads
- Goal: Confirm the base system boots without errors

---

## PHASE 1 — Understand and Test BKT Engine (Core of Scoring)

**Files:** app/bkt_engine.py
**Report:** 05_SCORING_ENGINE.md, 18_SCORING_AND_MASTERY_MODEL.md

### Step 1.1 — Read and understand BKT math
- [ ] Read 18_SCORING_AND_MASTERY_MODEL.md Layer 1 section
- [ ] Understand: P(T), P(S), P(G), slip floor, decay, surge detection
- Goal: Be able to explain the 4-step BKT update without looking at code

### Step 1.2 — Write a BKT demo script
- [ ] Create: test/demo_bkt.py
- [ ] Manually create a BKTNode for skill "ASYNC_CONCURRENCY"
- [ ] Simulate 5 turns: correct, incorrect, incorrect, correct, correct
- [ ] Print P(L) after each turn and check surge detection
- Goal: See the numbers change and understand why

### Step 1.3 — Test scaffolding decay
- [ ] Same demo but set scaffolding_level = 1, 2, 3
- [ ] Observe how the same correct answer gains less mastery at higher scaffold levels
- Goal: Confirm anti-coaching math works

### Step 1.4 — Test SeniorityTier initial priors
- [ ] Create BKTNode for STUDENT, JUNIOR, MID, SENIOR_STAFF
- [ ] Print initial P(L0) for each
- Goal: Confirm tier calibration is correct

---

## PHASE 2 — Understand and Test Knowledge Graph (HHGKT)

**Files:** app/graph_engine.py, app/bkt_engine.py
**Report:** 07_SKILL_TRACKING_ENGINE.md

### Step 2.1 — Read graph architecture
- [ ] Read 07_SKILL_TRACKING_ENGINE.md
- [ ] Understand: PREREQUISITE vs CO_REQUISITE edges
- [ ] Understand: get_next_recommended_skill() uncertainty formula
- [ ] Understand: propagate_mastery() influence delta calculation

### Step 2.2 — Write a graph demo script
- [ ] Create: test/demo_graph.py
- [ ] Build a graph with 4 pillars manually (no vector DB needed yet)
- [ ] Add prerequisite and co-requisite edges
- [ ] Call get_next_recommended_skill() — verify it picks the closest to P(L)=0.50
- Goal: See which skill gets recommended and why

### Step 2.3 — Test mastery propagation
- [ ] Set DATA_STRUCTURES_ALGORITHMS to P(L) = 0.90 (mastered)
- [ ] Call propagate_mastery("DATA_STRUCTURES_ALGORITHMS")
- [ ] Print DISTRIBUTED_CACHING P(L) before and after
- Goal: Confirm downstream skills receive positive boost

### Step 2.4 — Test prerequisite gate
- [ ] Set DATA_STRUCTURES_ALGORITHMS P(L) = 0.30 (unmastered)
- [ ] Confirm DISTRIBUTED_CACHING is excluded from recommendation
- Goal: Confirm prerequisite gate blocks advanced topics correctly

---

## PHASE 3 — Understand and Test Policy Router (FSM)

**Files:** app/policy_router.py
**Report:** 09_SESSION_STATE_ENGINE.md, 08_ADAPTIVE_DIFFICULTY_ENGINE.md

### Step 3.1 — Read the FSM
- [ ] Read 09_SESSION_STATE_ENGINE.md
- [ ] Map out all state transitions on paper/whiteboard
- Goal: Draw the FSM yourself from memory

### Step 3.2 — Write a policy router demo
- [ ] Create: test/demo_policy_router.py
- [ ] Initialize PolicyRouter(SeniorityTier.MID)
- [ ] Call initialize_session()
- [ ] Simulate 6 turns: observation=1, 0, 0, 1, 1, surge
- [ ] Print PolicyDirective after each turn
- Goal: Confirm SCAFFOLD/DEEPEN/DEVILS_ADVOCATE/NEXT_SKILL transitions work

### Step 3.3 — Test Devil's Advocate trigger
- [ ] Force a mastery surge (delta >= 0.40)
- [ ] Confirm state transitions to DEVILS_ADVOCATE
- [ ] Simulate DA pass (observation=1): confirm mastery boosted to >= 0.90
- [ ] Simulate DA fail (observation=0): confirm mastery collapsed to <= 0.20
- Goal: Understand the adversarial challenge mechanism

---

## PHASE 4 — Understand and Test MIRT Engine

**Files:** app/mirt_engine.py
**Report:** 05_SCORING_ENGINE.md (Layer 2), 18_SCORING_AND_MASTERY_MODEL.md

### Step 4.1 — Read MIRT math
- [ ] Read MIRT section in 18_SCORING_AND_MASTERY_MODEL.md
- [ ] Understand: 5 dimensions, theta, alpha, sigmoid prediction, gradient update

### Step 4.2 — Write a MIRT demo
- [ ] Create: test/demo_mirt.py
- [ ] Initialize MIRTEngine(SeniorityTier.MID)
- [ ] Simulate 6 items with varying difficulty (-1.0, 0.0, 0.5, 1.0, 1.5, 2.0)
- [ ] Print theta for all 5 dimensions after each turn
- [ ] Print percentile and tier from get_radar_summary()
- Goal: See ability estimates converge over multiple turns

---

## PHASE 5 — Understand and Test Behavioral Proctor (BII)

**Files:** app/proctor_engine.py
**Report:** 17_SECURITY_AND_TRUST_BOUNDARIES.md, 18_SCORING_AND_MASTERY_MODEL.md (Layer 3)

### Step 5.1 — Read BII calculation
- [ ] Read BII section in 18_SCORING_AND_MASTERY_MODEL.md
- [ ] Understand: TTR flag, latency jitter flag, contradiction probe flag, passive compliance flag

### Step 5.2 — Write a proctor demo
- [ ] Create: test/demo_proctor.py
- [ ] Simulate normal candidate: 6 turns, varied latency, moderate TTR -> BII stays near 1.0
- [ ] Simulate copilot candidate: uniform latency 2500ms, jitter < 180ms -> BII drops
- [ ] Simulate high TTR candidate: > 35 words, TTR > 0.88 -> lexical flag triggers
- [ ] Print BII after each turn
- Goal: Understand how cheating signals compound into BII penalty

---

## PHASE 6 — Understand and Test Shadow Evaluator

**Files:** app/evaluator_engine.py
**Report:** 04_CANDIDATE_EVALUATION_ENGINE.md, 06_RUBRIC_ENGINE.md

### Step 6.1 — Read evaluator flow
- [ ] Read 04_CANDIDATE_EVALUATION_ENGINE.md fully
- [ ] Understand: rubric dimensions, JSON schema, timeout, fallback

### Step 6.2 — Write a live evaluator test
- [ ] Create: test/demo_evaluator.py
- [ ] Call evaluate_candidate_response() with a real technical question and a good answer
- [ ] Print full JSON response: observation, depth_score, rubric_items
- [ ] Call again with a bad/off-topic answer
- Goal: See what the Shadow Evaluator actually returns

### Step 6.3 — Test the timeout fallback
- [ ] Simulate timeout by setting a very short timeout (0.001s) in a test wrapper
- [ ] Confirm fallback heuristic runs (word count > 15 -> observation=1)
- Goal: Confirm the system degrades gracefully

---

## PHASE 7 — Understand Vector Service and Pillar Matching

**Files:** app/vector_service.py
**Report:** 11_DOMAIN_EVALUATION_ENGINE.md

### Step 7.1 — Read vector matching flow
- [ ] Read 11_DOMAIN_EVALUATION_ENGINE.md
- [ ] Understand: 10 seed pillars, 768D embeddings, cosine similarity, fallback

### Step 7.2 — Write a vector match demo
- [ ] Create: test/demo_vector.py
- [ ] Ensure Dynoxide is running
- [ ] Call seed_competency_pillars() to seed the DB
- [ ] Call match_candidate_topics() with a sample intro text (e.g. "I built a Python FastAPI service with Redis caching")
- [ ] Print matched pillars with similarity scores
- Goal: Confirm vector search returns semantically relevant pillars

---

## PHASE 8 — Understand Ecosystem Detection

**Files:** app/ecosystem_service.py
**Report:** 11_DOMAIN_EVALUATION_ENGINE.md

### Step 8.1 — Write an ecosystem demo
- [ ] Create: test/demo_ecosystem.py
- [ ] Run detect_ecosystems_from_intro() with different intro texts:
  - Python ML: "I built a PyTorch model with FastAPI"
  - Java: "I worked on Spring Boot microservices with Kafka"
  - Go: "I wrote Goroutines for a high-throughput service"
  - Polyglot: "I use Python for ML and Golang for the API layer"
- [ ] Print primary_ecosystem, all_ecosystems, is_polyglot
- [ ] Run bind_pillars_to_ecosystems() and print the pillar->ecosystem map
- Goal: Verify correct ecosystem detection per intro text

---

## PHASE 9 — Understand Report Generation

**Files:** app/report_generator.py
**Report:** 12_REPORT_GENERATION_ENGINE.md

### Step 9.1 — Write a report generation demo
- [ ] Create: test/demo_reports.py
- [ ] Create mock session data (skills_mastery, turns_history, mirt_theta, bii)
- [ ] Call generate_student_report() with mock data
- [ ] Call generate_evaluator_report() with mock data
- [ ] Print both reports to terminal / save to reports/ folder
- Goal: See what real report output looks like

---

## PHASE 10 — Understand Database Layer

**Files:** app/db_service.py
**Report:** 14_DATA_MODEL_AND_DATABASE_FLOW.md

### Step 10.1 — Run db init
- [ ] Call init_db() and confirm all 4 tables created in PostgreSQL
- [ ] Verify with: SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';

### Step 10.2 — Write a db demo
- [ ] Create: test/demo_db.py
- [ ] Create a session, log 3 turns, save a compacted card, save final reports
- [ ] Read back with get_all_sessions() and get_session_turns()
- Goal: Confirm full read/write cycle works

---

## PHASE 11 — First Full Integration Run

### Step 11.1 — Start all services
- [ ] PostgreSQL running
- [ ] Dynoxide running
- [ ] FastAPI server: uvicorn app.live_server:app --reload

### Step 11.2 — Do a real interview
- [ ] Open browser, enter name + level
- [ ] Complete INTRO + at least 2 DEEP_DIVE turns
- [ ] Click "Finish Interview"
- [ ] Check: reports generated and displayed
- [ ] Check PostgreSQL: session + turns + report all saved
- Goal: Full end-to-end confirmed working

---

## PHASE 12 — Fix Critical Gaps (from 20_IMPLEMENTATION_GAPS.md)

Only start this phase after Phases 0-11 are fully complete and working.

### Step 12.1 — GAP-03: Sanitise candidate text [CRITICAL]
### Step 12.2 — GAP-07: Apply speech_cleaner.py to transcripts [HIGH]
### Step 12.3 — GAP-04: Wire generate_cpf() into live pipeline [HIGH]
### Step 12.4 — GAP-05: Auto-trigger contradiction probes [HIGH]
### Step 12.5 — GAP-01: Pre-locked rubric (2-step evaluation) [CRITICAL]
### Step 12.6 — GAP-02: Add JWT authentication [CRITICAL]
### Step 12.7 — GAP-06: Add Mobile/Flutter/Full Stack pillars [HIGH]

---

## CURRENT STATUS

- [x] Phase 0.1 — Implementation report written (22 files)
- [x] Phase 0.2 — Branch dev/v4 created with report only
- [ ] Phase 0.2 — Environment setup (next step)
- [ ] Everything else

---

## RULES WE FOLLOW

1. Never skip a phase
2. Always test before moving forward
3. If something is not working, fix it before continuing
4. Code is the source of truth, not assumptions
5. Never mark a step done until we can show the actual output
