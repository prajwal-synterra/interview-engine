# REPORT 7: Dynamic Skill Ontology Sprouting (DSOS) & Voice Session Resilience
**Document Reference:** AIS-DSOS-2026-V1  
**Subtitle:** Transitioning from Static Predefined Skills to Dynamic Knowledge Graph Sprouting, Real-Time Voice Continuity, and Universal Multi-Domain Candidate Evaluation  
**Audience:** Core Engineering Team, ML Architects, System Designers, Product Leadership  

---

## Executive Summary

During live candidate trials on the Socratic Assessment Engine, real-world conversational dynamics exposed three architectural bottlenecks that must be resolved to evaluate diverse student engineering cohorts:

1. **The Static Skill Taxonomy Bottleneck**: The initial prototype evaluated candidates against a small set of hardcoded technical skills (`ML_PIPELINES`, `DATA_STRUCTURES`, `WEB_FUNDAMENTALS`, `AI_SYSTEMS`). In reality, candidate backgrounds are radically heterogeneous: one candidate builds real-time distributed interview engines using WebSockets, Redis caching, AWS load balancers, and Docker containerization; another builds mobile apps in Flutter; another works on embedded firmware, robotics, or computer vision. Forcing every student into predefined, static categories distorts the Bayesian Knowledge Tracing (BKT) engine and leads to repetitive, unrepresentative questions.
2. **Audio Sentence Cut-Offs Mid-Thought**: Candidates speaking long, complex technical explanations experienced cut-offs mid-sentence. When pausing for 1.5–2 seconds to structure a thought, browser-based Web Speech API instances or client-side silence threshold detectors prematurely finalized the turn, clipping critical context and creating fragmented, incomplete transcripts.
3. **Session Lifecycle & Socket Aborts (Gemini Live 1008)**: After extended multi-turn exchanges, conversational input stopped being ingested. Root cause investigation revealed a combination of Gemini Live WebSocket lifecycle timeouts (error `1008: Operation Aborted` after prolonged socket duration) and an unhandled type collision (`str` vs `float`) in the graph engine's dynamic node registration.

This report specifies the comprehensive architecture, mathematical models, graph traversal algorithms, and voice streaming protocols to eliminate hardcoded skills, enable **Dynamic Skill Ontology Sprouting (DSOS)**, ensure bulletproof voice resilience, and generate bespoke, multi-domain evaluation reports for every student.

---

## Table of Contents
1. [Forensic Audit & Root Cause Analysis](#1-forensic-audit--root-cause-analysis)
2. [Dynamic Skill Ontology Sprouting (DSOS) Architecture](#2-dynamic-skill-ontology-sprouting-dsos-architecture)
3. [Mathematical Engine: Dynamic BKT & Adaptive MIRT](#3-mathematical-engine-dynamic-bkt--adaptive-mirt)
4. [Socratic Pathfinding: Graph-Guided Depth & Breadth Traversal](#4-socratic-pathfinding-graph-guided-depth--breadth-traversal)
5. [Voice Streaming Resilience & Connection Continuity](#5-voice-streaming-resilience--connection-continuity)
6. [Dynamic Dual Report Generation Engine](#6-dynamic-dual-report-generation-engine)
7. [Implementation Blueprint & Migration Plan](#7-implementation-blueprint--migration-plan)

---

## 1. Forensic Audit & Root Cause Analysis

### 1.1 The Static Taxonomy Problem
In the initial system, skill discovery was constrained to a regex-based lookup table:
```python
# PREVIOUS STATIC APPROACH (Antipattern)
FIXED_SKILLS = [
    "AI_SYSTEMS", "WEBSOCKETS_STREAMING", "API_DESIGN", 
    "DATA_STRUCTURES", "DATABASES", "SYSTEM_DESIGN", "CONCURRENCY"
]
```
When candidate Prajwal answered:
> *"Sabhi will be having a primary data centre with the help of database or any post grasis 12 but when it comes to the casing memories... we are storing it in the case memory so that we can have that use multiple times without waiting along duration..."*

The system recognized generic keywords like "database", but missed the deeper architectural entities:
- `DISTRIBUTED_CACHING_REDIS`
- `CACHE_INVALIDATION_STRATEGIES`
- `DATABASE_REPLICATION_POSTGRES`
- `CONTAINERIZATION_DOCKER`
- `CLOUD_INFRASTRUCTURE_AWS`

Because these skills did not exist in the initial static knowledge graph, the BKT engine could not trace mastery on them, the Policy Router could not systematically explore their prerequisites, and the final report defaulted to generic templates.

### 1.2 The Sentence Truncation Mechanism
In browser environments, `window.SpeechRecognition` (Web Speech API) employs client-side voice activity detection (VAD). If a candidate pauses for more than 1200ms while formulating a complex answer:
1. The browser's native recognizer fires an internal `onend` or prematurely marks `isFinal = true`.
2. The partial text is committed to the buffer.
3. If the candidate continues speaking, the new speech either begins in a new, disconnected turn or is completely dropped if the audio buffer was reset.
4. **Log Proof**:
   ```
   [2026-09-29 17:48:42] [SPEECH] [Candidate]: ...handling the red and NC and load balancing to use Germany the people are many person at the same
   [2026-09-29 17:49:35] [SPEECH] [Candidate]: ...and one that the use of that particular
   [2026-09-29 17:50:15] [SPEECH] [Candidate]: ...using doctor and using a w switches so that we can have a proper
   ```
   *Observations*: "redundancy" was transcribed as "red and NC", "AWS features" as "a w switches", and the tail end of each sentence was cut off before the complete thought was finalized.

### 1.3 The Gemini Live 1008 Abort & Type Collision
When the candidate continued past 5–6 turns:
1. In `app/live_server.py`, the call `policy_router.graph.add_skill(current_skill, f"Domain: {current_skill}")` passed a string description into a slot expecting a float `custom_prior`.
2. In `app/graph_engine.py`, `node.p_l = max(0.01, min(0.99, custom_prior))` triggered:
   `TypeError: '<' not supported between instances of 'str' and 'float'`
3. This unhandled exception silently broke the background evaluator pipeline.
4. Concurrently, Gemini Live's WebSocket connection closed with status `1008: None. The operation was aborted` (a standard server-side session timeout on long-lived connections).
5. The unhandled exception loop caused `gemini_receive_loop` to spin infinitely, re-entering a closed generator and preventing any further user input from reaching Alex.

---

## 2. Dynamic Skill Ontology Sprouting (DSOS) Architecture

Rather than evaluating every student on a fixed checklist of questions, the engine must act as an **Autonomous Ontological Cartographer**. It begins with zero predefined skills, listens to what the student actually works on, and sprouts a directed knowledge graph in real time.

```
                      ┌─────────────────────────────────────────┐
                      │        Candidate Spoken Input           │
                      └────────────────────┬────────────────────┘
                                           │
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │    Shadow Entity & Skill Extractor      │
                      │       (Gemini 2.5 Flash Async)          │
                      └────────────────────┬────────────────────┘
                                           │
                        ┌──────────────────┴──────────────────┐
                        │ Sprouted Entities & Hierarchies     │
                        ▼                                     ▼
        ┌───────────────────────────────┐     ┌───────────────────────────────┐
        │   New Skill Node Sprouting    │     │   Topological Edge Synthesis  │
        │ - Code: REDIS_CACHE_SYNC      │     │ - Type: PREREQUISITE          │
        │ - Domain: DISTRIBUTED_SYSTEMS │     │ - From: DISTRIBUTED_CACHING   │
        │ - Abstraction: IMPLEMENTATION │     │ - To:   REDIS_CACHE_SYNC      │
        │ - Prior P(L): Dynamic Calib   │     │ - Beta Weight: 0.65           │
        └───────────────┬───────────────┘     └───────────────┬───────────────┘
                        │                                     │
                        └──────────────────┬──────────────────┘
                                           │
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │  Hierarchical Heterogeneous Graph (HHG) │
                      │  - Dynamic BKT Engine Propagation       │
                      │  - Multidimensional IRT Coordinate Mpg │
                      └────────────────────┬────────────────────┘
                                           │
                                           ▼
                      ┌─────────────────────────────────────────┐
                      │    Socratic Graph Traversal Router      │
                      │    (Depth Drilldown vs. Breadth Pivot)  │
                      └─────────────────────────────────────────┘
```

### 2.1 The Four Abstraction Tiers
Every dynamically discovered skill is classified into one of four hierarchical abstraction tiers:

| Tier | Abstraction Level | Description | Example Sprouted Nodes |
|---|---|---|---|
| **Tier 1** | `FOUNDATIONAL_CORE` | Fundamental programming primitives, CS concepts, protocol specs | `HTTP_PROTOCOL`, `TCP_SOCKETS`, `ARRAY_BUFFER_PCM` |
| **Tier 2** | `FRAMEWORK_TOOL` | Concrete libraries, cloud vendors, databases, runtimes | `REDIS_CACHE`, `POSTGRESQL`, `DOCKER_ENGINE`, `FASTAPI` |
| **Tier 3** | `SYSTEM_MECHANISM` | Interaction patterns, concurrency, synchronization, caching | `CACHE_INVALIDATION`, `LOAD_BALANCING`, `DATA_CONSISTENCY` |
| **Tier 4** | `ARCHITECTURAL_PARADIGM` | High-level system design, trade-offs, fault tolerance | `EVENT_DRIVEN_STREAMING`, `CQRS`, `ZERO_DOWNTIME_DEPLOYMENT` |

### 2.2 Dynamic Node Schema
When an entity is extracted, it is instantiated as a rich node in the graph:

```python
@dataclass
class SproutedSkillNode:
    skill_code: str                     # e.g., "REDIS_CACHE_CONSISTENCY"
    display_name: str                   # e.g., "Redis Cache Consistency & Invalidation"
    domain: str                         # e.g., "DISTRIBUTED_SYSTEMS"
    abstraction_tier: AbstractionTier   # SYSTEM_MECHANISM
    first_mentioned_turn: int           # Turn when candidate introduced concept
    status: MasteryStatus               # DISCOVERED, IN_PROGRESS, MASTERED, DEFICIENT
    bkt_engine: BKTNode                 # Individual Bayesian engine
    mirt_dimension: str                 # Latent trait cluster
```

### 2.3 Topological Edge Synthesis
When a node is sprouted, the engine determines its topological relationship with existing nodes:
- **`PREREQUISITE` (Directed)**: Concept $A$ must be understood before Concept $B$ can be sensibly defended.  
  *Example*: `HTTP_PROTOCOL` $\to$ `WEBSOCKETS_STREAMING`  
  *Example*: `DATA_CONSISTENCY` $\to$ `CACHE_INVALIDATION_STRATEGIES`
- **`CO_REQUISITE` (Bidirectional)**: Concepts that mutually reinforce each other.  
  *Example*: `DOCKER_CONTAINERIZATION` $\leftrightarrow$ `KUBERNETES_ORCHESTRATION`
- **`ABSTRACTION_PARENT` (Hierarchical)**: Parent category linking concrete implementations to abstract design.  
  *Example*: `DISTRIBUTED_SYSTEMS` $\to$ `LOAD_BALANCING_AWS`

---

## 3. Mathematical Engine: Dynamic BKT & Adaptive MIRT

### 3.1 Dynamic Prior Calibration ($P(L_0)$)
In a static system, priors are fixed ($0.35$ for Mid, $0.20$ for Student). In DSOS, because the candidate *self-selected* the project and proactively mentioned the skill, the initial prior must reflect both:
1. The **Seniority Tier** chosen for the interview.
2. The **Proactivity Weight** (skills introduced unprompted by the candidate have higher initial credibility than skills introduced by the interviewer).
3. The **Abstraction Tier** of the concept.

$$\begin{aligned}
P(L_0) = \text{clip}\Big( P_{\text{tier\_base}} + \Delta_{\text{proactive}} - \Delta_{\text{abstract}}, 0.05, 0.75 \Big)
\end{aligned}$$

Where:
- $P_{\text{tier\_base}}$: $0.25$ (Student), $0.40$ (Mid), $0.55$ (Hard)
- $\Delta_{\text{proactive}} = +0.10$ if candidate introduced the topic; $0.00$ if interviewer introduced it.
- $\Delta_{\text{abstract}} = 0.00$ (Tier 1/2), $0.08$ (Tier 3), $0.15$ (Tier 4).

### 3.2 Graph Message-Passing Formulation
When the candidate answers an inquiry on a sprouted skill node $S_i$, the Shadow Evaluator outputs binary observation $Y_t \in \{0, 1\}$. Node $S_i$ updates its posterior $P(L_t)$:

$$\begin{aligned}
P(L_t \mid Y_t=1) &= \frac{P(L_{t-1}) \cdot (1 - P(S))}{P(L_{t-1}) \cdot (1 - P(S)) + (1 - P(L_{t-1})) \cdot P(G)} \\
P(L_t \mid Y_t=0) &= \frac{P(L_{t-1}) \cdot P(S)}{P(L_{t-1}) \cdot P(S) + (1 - P(L_{t-1})) \cdot (1 - P(G))}
\end{aligned}$$

Next, the updated mastery propagates across the sprouted DAG edges via message passing:

$$\begin{aligned}
\Delta P(L_{\text{neighbor}}) = \big( P(L_t(S_i)) - 0.50 \big) \cdot \beta_{i,j} \cdot \alpha_{\text{edge}}
\end{aligned}$$

Where:
- $\beta_{i,j} \in [0.1, 0.8]$ is the learned semantic affinity between the two concepts.
- $\alpha_{\text{edge}} = 0.50$ for `PREREQUISITE`, $0.35$ for `CO_REQUISITE`, $0.25$ for `ABSTRACTION`.

This ensures that demonstrating deep understanding of Redis cache invalidation automatically confers Bayesian credibility to parent distributed systems concepts without requiring redundant questioning.

### 3.3 Dynamic Multidimensional Item Response Theory (MIRT)
As skills sprout across different domains (e.g., $D_1: \text{Cloud/Infra}$, $D_2: \text{Backend/Concur}$, $D_3: \text{Data Engineering}$), the latent ability vector $\vec{\theta}$ expands dynamically:

$$\begin{aligned}
P(Y_{ij} = 1 \mid \vec{\theta}) = \frac{1}{1 + \exp\left( - \left( \sum_{d \in \mathcal{D}} a_{jd} \cdot \theta_d - b_j \right) \right)}
\end{aligned}$$

Where:
- $\vec{\theta} = (\theta_{\text{Cloud}}, \theta_{\text{Backend}}, \dots)$ represents candidate latent competence per discovered cluster.
- $a_{jd}$ is the discrimination parameter of question $j$ along dimension $d$.
- $b_j$ is the difficulty threshold of the question.

---

## 4. Socratic Pathfinding: Graph-Guided Depth & Breadth Traversal

The conversation flow must follow a rigorous, non-linear state machine guided by the sprouted graph:

```
[INTRO] ──► (Sprout initial nodes: S1, S2, S3) ──► Pick S1
                                                      │
                                                      ▼
                                       ┌──► [DEPTH_DRILLDOWN on S1] ◄──┐
                                       │              │                │
                        Observation = 0│   Depth < 80%│                │ Observation = 1
                       (Scaffold Hint) │     Turns < 3│                │ (Probe Trade-off)
                                       └──────────────┴────────────────┘
                                                      │
                                    Depth >= 80% OR Turns >= 3
                                                      │
                                                      ▼
                                           [TOPOLOGICAL PIVOT]
                                           Is there backlog?
                                          /                 \
                                    YES  /                   \ NO
                                        ▼                     ▼
                             Pick S2 from backlog       [DEVIL'S ADVOCATE]
                             (Transition dialogue)      (Cross-cutting stress test)
                                        │                     │
                                        ▼                     ▼
                             [DEPTH_DRILLDOWN on S2]    [FINAL SYNTHESIS & REPORT]
```

### 4.1 Depth Drilldown Rule
While on active skill $S_{\text{active}}$:
- **Turn 1 (Surface Mechanics)**: How is it configured? What data format is used?
- **Turn 2 (Edge Cases & Failure Modes)**: What happens when the network partitions? How do you handle cache stampedes?
- **Turn 3 (Architectural Trade-offs)**: Why Redis over Memcached or in-memory LRU? What is the cost-performance trade-off?

*Depth Reached Condition*:
$$\text{DepthReached}(S_i) \iff \Big( P(L(S_i)) \ge 0.80 \Big) \lor \Big( \text{Turns}(S_i) \ge 3 \Big)$$

### 4.2 Dynamic Discovery During Dialogue (Spontaneous Sprouting)
If a candidate mentions a new technology or architecture during their answer (e.g., *"we used Redis, but we also put Nginx in front for SSL termination and rate limiting"*):
1. The Shadow Evaluator detects new entities: `NGINX_PROXY`, `RATE_LIMITING`.
2. The Graph Sprouter adds these nodes to the **Backlog Queue**.
3. It creates an edge: `NGINX_PROXY` $\to$ `RATE_LIMITING` (`SYSTEM_MECHANISM`).
4. Alex does not interrupt immediately, but stores this branch for the subsequent breadth pivot.

---

## 5. Voice Streaming Resilience & Connection Continuity

### 5.1 Dual-Buffer Continuous Speech Pipeline
To prevent candidate sentences from being cut off during natural mid-sentence pauses, the client-side audio capture is redesigned from fragile single-stream recognizers into a **Dual-Buffer Pipeline**:

```
                       [Candidate Microphone Stream]
                                     │
                 ┌───────────────────┴───────────────────┐
                 │                                       │
                 ▼                                       ▼
       [AudioWorklet Processor]              [Web Speech API Loop]
       - 16,000 Hz Little-Endian PCM         - Continuous = true
       - Encodes into 4096-sample chunks     - Dynamic auto-restart on 'end'
       - Appends to FullTurnAudioBuffer      - Live UI visual transcript
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     │
                             User hits Space / 
                           Taps 'Done Speaking'
                                     │
                                     ▼
                      [Finalize Turn Dispatcher]
                 - Combines client transcript stream
                 - Transcribes FullTurnAudioBuffer via 
                   Gemini 2.5 Flash STT fallback if needed
                 - Emits complete, unclipped text to server
```

#### Client Speech Watchdog Algorithm (JavaScript):
```javascript
let recognition = null;
let fullTurnTranscript = "";

function startContinuousRecognition() {
    recognition = new webkitSpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    
    recognition.onresult = (event) => {
        let currentInterim = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                fullTurnTranscript += event.results[i][0].transcript + " ";
            } else {
                currentInterim += event.results[i][0].transcript;
            }
        }
        updateLiveTranscriptUI(fullTurnTranscript + currentInterim);
    };

    // Watchdog: If browser cuts off speech recognition while candidate is recording, auto-restart instantly
    recognition.onend = () => {
        if (isRecording) {
            console.log("[Watchdog] Speech recognition auto-restarting to prevent cut-off...");
            try { recognition.start(); } catch (e) {}
        }
    };
    recognition.start();
}
```

### 5.2 Gemini Live Connection Lifecycle Manager (1008 Abort Recovery)
Gemini Live WebSocket sessions are subject to timeout boundaries. The server must manage the session lifecycle with transparent token renewal:

1. **Keepalive Ping**: The server sends a heartbeat frame every 20 seconds during idle conversation turns.
2. **Session Context Snapshotting**: Every turn's completed conversation history (`user_prompt` and `alex_response`) is stored in an in-memory session history list.
3. **Transparent 1008 Reconnection**: If Gemini Live raises `1008 None. The operation was aborted`:
   ```python
   async def ensure_live_session():
       nonlocal session, live_client
       try:
           # Ping session or check active
           pass
       except (websockets.exceptions.ConnectionClosedError, Exception) as e:
           log_event("SESSION_RECOVERY", f"Re-establishing Gemini Live session after abort: {e}")
           session = await live_client.connect(model=MODEL_NAME, config=CONFIG)
           # Replay recent conversation context turns so Alex maintains continuity
           await session.send_client_content(turns=historical_turns, turn_complete=False)
   ```

---

## 6. Dynamic Dual Report Generation Engine

Reports must no longer rely on fixed skill tables. Instead, the report generator dynamically queries the **sprouted Knowledge Graph** and groups findings into the candidate's discovered ecosystem.

### 6.1 Candidate Career Compass & Growth Report Structure
- **Discovered Tech Stack Matrix**: Formatted as a dynamically generated markdown table of all tools, languages, and paradigms the candidate demonstrated.
- **Topological Strengths with Conversational Proof**: Pulls exact quotes from turns where $P(L) \ge 0.80$.
- **High-Impact Blind Spots**: Pinpoints nodes where the candidate struggled with failure modes or edge cases (e.g., Redis data loss on sudden power-off).
- **Customized 30-60-90 Day Roadmap**: Generated specifically for the sprouted tools (e.g., if Docker and Redis were sprouted, roadmap gives specific books like *Redis in Action* and *Docker Deep Dive*, rather than generic algorithms).

### 6.2 Hiring Team Forensic Audit Report Structure
- **Hiring Signal & Verdict**: `STRONG HIRE`, `HIRE`, `LEAN HIRE`, `NO HIRE` based on average mastery across sprouted nodes weighted by tier.
- **Topological Knowledge DAG Table**:
  | Sprouted Skill | Abstraction Tier | Prior $P(L_0)$ | Posterior $P(L_t)$ | Mastery Status | Slip / Guess |
  |---|---|:---:|:---:|:---:|:---:|
  | `REDIS_CACHE_CONSISTENCY` | `SYSTEM_MECHANISM` | 0.35 | 0.88 | MASTERED | 0.08 / 0.12 |
  | `LOAD_BALANCING_AWS` | `SYSTEM_MECHANISM` | 0.40 | 0.82 | MASTERED | 0.10 / 0.15 |
  | `DOCKER_CONTAINERIZATION` | `FRAMEWORK_TOOL` | 0.45 | 0.74 | IN_PROGRESS | 0.12 / 0.18 |
- **Multidimensional Ability Radar ($\vec{\theta}$)**: Visual breakdown across all sprouted domains.
- **Behavioral Integrity & Anti-Cheat Audit**: Proctor BII score, latency variation, and authenticity metric.

---

## 7. Implementation Blueprint & Migration Plan

### Phase 1: Core Type Safety & Voice Resilience (Completed / Immediate)
- [x] Fix unhandled `str` vs `float` type error in `app/graph_engine.py` and `app/live_server.py`.
- [x] Implement browser SpeechRecognition watchdog auto-restart to prevent mid-thought silence cut-offs.
- [x] Add guard in client audio receiver to prevent audio overlap while candidate is speaking.
- [x] Create `.gitignore` to protect API keys and untrack binary artifacts.

### Phase 2: Dynamic Skill Discovery & Graph Sprouter (Next Step)
- [ ] Upgrade `extract_topics_from_text` to use Gemini Flash entity extraction returning structured JSON (`skill_code`, `display_name`, `domain`, `abstraction_tier`).
- [ ] Implement `KnowledgeGraph.sprout_node()` and `KnowledgeGraph.sprout_edge()` to dynamically build DAGs during runtime.
- [ ] Integrate proactivity-weighted dynamic prior calibration $P(L_0)$.

### Phase 3: Socratic Dynamic Graph Traversal
- [ ] Update `PolicyRouter` to traverse sprouted graph neighbors based on prerequisite satisfaction and uncertainty boundaries.
- [ ] Implement seamless breadth pivoting across candidate-discovered backlog topics.

### Phase 4: Gemini Live Session Resumption Protocol
- [ ] Wrap Gemini Live connection with automatic session recovery and conversation state snapshot replay to guarantee indefinite session duration without 1008 aborts.

### Phase 5: Dynamic Dual Reports Pipeline
- [ ] Refactor `app/report_generator.py` to ingest sprouted graph topology and generate fully custom learning paths and hiring rubrics for any technical stack.

---

*Authored and Approved for Architecture Version AIS-DSOS-2026-V1 on branch `dev/v3`.*
