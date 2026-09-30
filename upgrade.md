# UPGRADE SPECIFICATION: Dynamic Skill Architecture, Real MIRT & Graph Wiring, and Database Strategy
**Document Reference:** AIS-UPGRADE-2026-V1  
**Project:** Autonomous Socratic Technical Assessment Engine  
**Target Branch:** `dev/v3`  
**Purpose:** Actionable blueprint for transitioning from static prototypes to dynamic, database-backed, multi-ecosystem candidate evaluation.

---

## Table of Contents
1. [Executive Assessment: Can We Actually Use Graph & MIRT?](#1-executive-assessment-can-we-actually-use-graph--mirt)
2. [How to Realistically Use the Graph Engine](#2-how-to-realistically-use-the-graph-engine)
3. [How to Realistically Use the MIRT Engine](#3-how-to-realistically-use-the-mirt-engine)
4. [Universal Multi-Ecosystem Adaptation (Python vs. Java vs. Go)](#4-universal-multi-ecosystem-adaptation)
5. [Database Architecture: What Goes into Vector DB vs. Relational DB](#5-database-architecture-what-goes-into-vector-db-vs-relational-db)
6. [Optimal Candidate Progress & Final Report Pipeline](#6-optimal-candidate-progress--final-report-pipeline)
7. [Step-by-Step Implementation Roadmap](#7-step-by-step-implementation-roadmap)

---

## 1. Executive Assessment: Can We Actually Use Graph & MIRT?

### The Honest Reality of the Current Codebase
In the current code:
* **The Graph Engine (`graph_engine.py`)** exists as a data structure with 3 hardcoded nodes (`ML_PIPELINES`, `DATA_STRUCTURES`, `WEB_FUNDAMENTALS`). It does not dynamically build edges or direct conversational pathfinding.
* **The MIRT Engine (`mirt_engine.py`)** computes a latent ability vector $\theta$ in memory during each turn, but **its output is completely ignored by Alex and bypassed in the report generator** (which was substituting a dummy formula `avg_mastery * 1.5 - 0.2`).

### Is it possible to use them?
**YES, but only if they are repurposed properly for real-time conversational streaming rather than static standardized paper tests.**

| Component | Why It Fails in Traditional Setup | How to Make It Truly Work in Our Engine |
|---|---|---|
| **Graph Engine (`HHGKT`)** | Traditional knowledge graphs require thousands of manually authored prerequisite links. Trying to map every micro-function makes the graph explode and freeze. | **Use as a Macro-Topic Dependency Graph (ATDG)**: Track only **3 to 5 Macro Pillars** per interview. Use edges purely for **prerequisite gating** (e.g., don't ask about distributed cache stampedes if basic caching mechanics scored 0) and **breadth pivoting**. |
| **MIRT Engine** | Classic psychometric MIRT requires a fixed bank of 50+ multiple-choice questions with pre-calibrated difficulty parameters ($b$) and discrimination parameters ($\alpha$). In our system, Alex generates questions dynamically. | **Use Dynamic Item Calibration via Shadow LLM**: When the Shadow LLM grades an answer, it estimates the question's difficulty level ($b \in [-2.0, +2.0]$) and dimension weights ($\alpha$). MIRT then updates a real 3-dimensional latent vector ($\theta_{\text{Depth}}$, $\theta_{\text{SystemDesign}}$, $\theta_{\text{TradeOffs}}$) which directly feeds the hiring signal. |

---

## 2. How to Realistically Use the Graph Engine

Instead of trying to represent every programming language keyword as a graph node, the Graph Engine must operate on **Evaluative Competency Clusters**:

```
                       ┌────────────────────────────┐
                       │  DATA_PERSISTENCE (DB)     │
                       └─────────────┬──────────────┘
                                     │ PREREQUISITE (beta = 0.6)
                                     ▼
                       ┌────────────────────────────┐
                       │ DISTRIBUTED_STATE (Cache)  │
                       └─────────────┬──────────────┘
                                     │ CO_REQUISITE (beta = 0.5)
                                     ▼
                       ┌────────────────────────────┐
                       │ REALTIME_STREAMING (Socket)│
                       └────────────────────────────┘
```

### 1. Prerequisite Gating (Preventing Premature Deep Dives)
The graph prevents Alex from grilling a student on complex edge cases when the foundational layer is weak:
* If `DATA_PERSISTENCE` has mastery $P(L) < 0.40$, the graph's `get_prerequisite_readiness("DISTRIBUTED_STATE")` returns `False`.
* **Behavior**: Alex stays on the current level or drops scaffolding to reinforce the core concept, rather than jumping into distributed cache consensus.

### 2. Topological Next-Skill Recommendation
When a candidate finishes demonstrating depth on Topic 1 ($P(L) \ge 0.80$ or 3 turns elapsed):
* The engine calls `graph.get_next_recommended_skill()`.
* The graph inspects the unmastered candidate topics, calculates their Fisher Information (which topic provides the highest measurement leverage), and tells Alex which project to explore next.

---

## 3. How to Realistically Use the MIRT Engine

Traditional psychometrics measures one scalar test score. Modern hiring needs a **multidimensional vector** that shows what kind of engineer the candidate is.

### The 3 Core Latent Dimensions ($\vec{\theta}$)
Instead of hardcoding language-specific dimensions, MIRT should track three universal engineering traits:

1. $\theta_{\text{Arch}}$ — **Architectural First-Principles & Trade-offs**: Does the candidate understand *why* systems are designed this way, or do they just blindly assemble libraries?
2. $\theta_{\text{Edge}}$ — **Edge Case & Failure Resilience**: Do they know what breaks when concurrency spikes, networks partition, or memory fills up?
3. $\theta_{\text{Exec}}$ — **Operational Grounding**: Can they explain real implementation details, debugging steps, and metrics?

### Dynamic Item Parameter Estimation
During each turn:
1. The candidate answers Alex's prompt.
2. The Shadow Evaluator outputs:
   * Observation: $Y_t \in \{0, 1\}$
   * Question Difficulty: $b \in [-2.0, +2.0]$ (Scaffolded beginner vs. Senior production trade-off)
   * Discrimination Vector: $\vec{\alpha} = [\alpha_{\text{Arch}}, \alpha_{\text{Edge}}, \alpha_{\text{Exec}}]$
3. The MIRT engine executes its online gradient update:
   $$\vec{\theta}_{t} = \vec{\theta}_{t-1} + \eta \cdot \vec{\alpha} \cdot (Y_t - P_{\text{predicted}})$$
4. **Hiring Team Output**: The final report renders a genuine **3D Competency Radar** showing whether the candidate is a pure theoretical architect, a hands-on implementer, or a balanced senior engineer.

---

## 4. Universal Multi-Ecosystem Adaptation

### The Problem
* If we hardcode Python, we evaluate `FastAPI`, `Celery`, `GIL`, and `SQLAlchemy`.
* If an elite Java candidate arrives, they talk about `Spring Boot`, `Virtual Threads`, `Netty`, and `Hibernate`.
* If a Go candidate arrives, they talk about `Goroutines`, `Channels`, and `Gin`.

### The Solution: Decouple Architectural Pillars from Ecosystem Manifestations

```
┌────────────────────────────────────────────────────────────────────────┐
│ UNIVERSAL ARCHITECTURAL PILLAR (Language-Agnostic Vector DB Anchor)    │
│ - Concept: Asynchronous Network Concurrency                            │
│ - Core Challenges: Event loop starvation, backpressure, socket leaks   │
│ - Senior Indicators: Connection pooling, non-blocking I/O trade-offs   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
           ┌────────────────────────┼────────────────────────┐
           ▼                        ▼                        ▼
   [Python Ecosystem]        [Java Ecosystem]         [Go Ecosystem]
   - `asyncio` loop         - `Netty` / `WebFlux`    - Goroutines / runtime
   - `FastAPI` / `uvicorn`  - `Spring Boot 3`        - Channels / `select`
   - GIL limitations        - Virtual Threads (Loom) - Zero-overhead stacks
```

### How the Engine Adapts Dynamically:
1. **Turn 1 (Intro Extraction)**: The candidate says: *"I build high-throughput microservices using Java, Spring Boot, and Kafka."*
2. **Ecosystem Tagging**: The system tags the session: `Ecosystem = JAVA_JVM`.
3. **Prompt Injection to Shadow Evaluator & Alex**:
   * The Shadow Evaluator receives the **Universal Concurrency Rubric**, but its contextual prompt adds: *"Evaluate within the Java/Spring ecosystem (expect mentions of reactive streams, thread pools, or Kafka consumer offsets)."*
4. **Result**: The same mathematical BKT/MIRT engine evaluates both the Python candidate and the Java candidate without altering a single line of core logic.

---

## 5. Database Architecture: What Goes into Vector DB vs. Relational DB

To build a production-grade system that scales to thousands of candidates, data must be partitioned cleanly across storage engines.

```
┌─────────────────────────────────────────┐   ┌─────────────────────────────────────────┐
│          VECTOR DATABASE (Search)       │   │        RELATIONAL DATABASE (State)      │
│     (Chroma / Qdrant / pgvector)        │   │     (PostgreSQL / SQLite / Supabase)    │
├─────────────────────────────────────────┤   ├─────────────────────────────────────────┤
│ 1. Competency Pillars & Rubrics         │   │ 1. Candidate Profiles & Auth            │
│ 2. Socratic Probe Templates             │   │ 2. Permanent Intro Blueprints           │
│ 3. Failure Mode & Edge Case Scenarios   │   │ 3. Compacted Topic Verdict Cards        │
│ 4. Ecosystem Keyword Semantic Clusters │   │ 4. Turn-by-Turn Audio & Speech Logs     │
│                                         │   │ 5. BKT & MIRT Time-Series Telemetry     │
│                                         │   │ 6. Final Dual Assessment Reports        │
└─────────────────────────────────────────┘   └─────────────────────────────────────────┘
```

### Vector Database Schema (Knowledge & Rubric Retrieval)
Used exclusively for semantic lookup and prompt guidance:
* **Collection `competency_pillars`**:
  * `id`: e.g., `pillar_distributed_caching`
  * `embedding`: Semantic embedding of the domain concepts, synonyms, and architectural terms.
  * `metadata`:
    * `category`: `DISTRIBUTED_SYSTEMS`
    * `importance_weight`: `0.9` (Tier A)
    * `core_rubric`: What constitutes a Pass vs. Fail on this topic.
    * `socratic_probes`: Suggested follow-up directions (Rationale $\to$ Failure Mode $\to$ Scalability).
* **Collection `ecosystem_mappings`**:
  * Semantic embeddings of tools, frameworks, and packages mapped to their canonical architectural concepts.

### Relational / Document Database Schema (Session State & Audit Trail)
Used for state persistence, progress tracking, and report retrieval:

#### Table 1: `interview_sessions`
```sql
CREATE TABLE interview_sessions (
    session_id UUID PRIMARY KEY,
    candidate_name VARCHAR(100) NOT NULL,
    seniority_tier VARCHAR(20) NOT NULL,       -- STUDENT, MID, SENIOR
    detected_ecosystem VARCHAR(50),            -- PYTHON, JAVA, GO, NODEJS
    status VARCHAR(20) NOT NULL,               -- IN_PROGRESS, COMPLETED, ABORTED
    intro_blueprint JSONB,                     -- Permanent parsed projects & skills
    current_topic VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

#### Table 2: `compacted_topic_cards`
```sql
CREATE TABLE compacted_topic_cards (
    card_id UUID PRIMARY KEY,
    session_id UUID REFERENCES interview_sessions(session_id),
    topic_code VARCHAR(100) NOT NULL,
    turns_spent INT NOT NULL,
    final_mastery_p_l FLOAT NOT NULL,
    status VARCHAR(20) NOT NULL,               -- MASTERED, INCOMPLETE, SKIPPED
    verdict_summary TEXT NOT NULL,             -- 2-line summary of demonstrated depth
    strengths_cited JSONB,                     -- Exact candidate quotes of strong reasoning
    gaps_identified JSONB,                     -- Specific edge cases missed
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### Table 3: `turn_telemetry_logs`
```sql
CREATE TABLE turn_telemetry_logs (
    turn_id UUID PRIMARY KEY,
    session_id UUID REFERENCES interview_sessions(session_id),
    turn_index INT NOT NULL,
    topic VARCHAR(100) NOT NULL,
    interviewer_prompt TEXT NOT NULL,
    candidate_transcript TEXT NOT NULL,
    latency_ms INT NOT NULL,
    evaluator_observation INT NOT NULL,        -- 1 or 0
    depth_score FLOAT NOT NULL,
    bkt_prior FLOAT NOT NULL,
    bkt_posterior FLOAT NOT NULL,
    mirt_theta_snapshot JSONB NOT NULL,
    proctor_bii FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### Table 4: `final_reports`
```sql
CREATE TABLE final_reports (
    report_id UUID PRIMARY KEY,
    session_id UUID REFERENCES interview_sessions(session_id) UNIQUE,
    student_compass_markdown TEXT NOT NULL,
    evaluator_audit_markdown TEXT NOT NULL,
    hiring_verdict VARCHAR(20) NOT NULL,       -- STRONG_HIRE, HIRE, LEAN_HIRE, NO_HIRE
    average_mastery FLOAT NOT NULL,
    proctor_integrity_score FLOAT NOT NULL,
    generated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 6. Optimal Candidate Progress & Final Report Pipeline

To guarantee that sessions never crash, context never overflows, and candidate progress is continuously preserved, the engine implements the **Epistemic Compaction Pipeline**:

```
[Turn 1: Candidate Speaks Intro]
             │
             ▼
   Parse & Save to DB:
   `interview_sessions.intro_blueprint`
   (Permanent unalterable baseline)
             │
             ▼
   Select Topic 1 from Blueprint
             │
 ┌───────────┴─────────────────────────────────────────────┐
 │ ACTIVE WORKING BUBBLE (Max 3 Turns in Gemini Context)    │
 │ - Turn 1: Surface Mechanics & Architecture              │
 │ - Turn 2: Failure Modes & Edge Cases                    │
 │ - Turn 3: Scale & Trade-offs                            │
 └───────────┬─────────────────────────────────────────────┘
             │
      Depth Condition Met:
      P(L) >= 0.80 OR Turns >= 3
             │
             ▼
   [EPISTEMIC COMPACTION STEP]
   1. Summarize the 3 turns into a 2-line "Compacted Topic Card".
   2. Insert into `compacted_topic_cards` DB table.
   3. FLUSH active chat turns from Gemini Live memory.
   4. RETAIN only: Intro Blueprint + Compacted Cards.
             │
             ▼
   Select Topic 2 from Intro Blueprint
             │
    (Repeat until all topics explored)
             │
             ▼
   [FINAL REPORT COMPILATION]
   Report generator queries `compacted_topic_cards` directly.
   Zero raw transcript parsing required.
   Saves to `final_reports` DB table & streams to UI.
```

### Benefits of this Pipeline:
1. **Zero Token Bloat / No 1008 Aborts**: The working memory never exceeds 3 turns of audio/text.
2. **Crash Resilience**: If a network disconnect occurs at Turn 7, the database already has the finalized Topic Cards for Topics 1 and 2. Reconnecting resumes directly at Topic 3 without repeating prior topics.
3. **Instant, High-Fidelity Reports**: Final reports are generated from vetted fact cards rather than hallucinating over a messy 2,000-line chat log.

---

## 7. Step-by-Step Implementation Roadmap

| Milestone | Deliverables | Verification Metric | Status |
|---|---|---|---|
| **Phase 1: DB & Compaction Engine** | 1. Implement PostgreSQL schema (`interview_sessions`, `compacted_topic_cards`, `turn_telemetry_logs`, `final_reports`).<br>2. Implement Turn 1 Intro Blueprint persistent storage.<br>3. Implement Topic Compaction and context flushing after depth completion. | Gemini Live context stays $< 4$ turns throughout a 10-turn interview without 1008 errors; state preserved in PostgreSQL. | ✅ **COMPLETED** |
| **Phase 2: Vector DB Pillar Matching** | 1. Launch Dynoxide container on port 8001 with native vector index.<br>2. Generate 768-dim embeddings via `gemini-embedding-2`.<br>3. Replace static regex topic extractor with DynamoDB-compatible `boto3` vector search.<br>4. Rank pillars by cosine distance and criticality. | Candidate mentioning custom projects automatically matches core engineering pillars in real time. | ✅ **COMPLETED** |
| **Phase 3: Real MIRT & Graph Pathfinding** | 1. Wire Shadow LLM difficulty ($b$) and discrimination ($\vec{\alpha}$) matrix into `MIRTEngine`.<br>2. Hook `KnowledgeGraph.get_next_recommended_skill()` with prerequisite gating and entropy to drive Topic transitions.<br>3. Embed genuine 5D MIRT $\vec{\theta}$ vector and industry percentiles into dual reports. | MIRT $\vec{\theta}$ updates in real-time on 5 canonical dimensions; report shows verified 5D ability radar. | ✅ **COMPLETED** |
| **Phase 4: Multi-Ecosystem Adaptation** | 1. Implement project-scoped runtime ecosystem parser (Java, Python, Go, Node.js, C++/Rust).<br>2. Bind pillars to project ecosystems and inject dynamic dialect directives into Alex's live system prompt.<br>3. Contextualize Shadow Evaluator rubrics based on active runtime ecosystem. | Java candidate mentioning Spring/Netty receives idiomatic JVM questions (GC/event loops/thread pools); Python ML projects receive GIL/asyncio probes. | ✅ **COMPLETED** |

---

*Authored for Interview Engine Architecture V3.*  
*Status: All V3 Architecture Upgrades Live & Verified on branch `dev/v3`.*
