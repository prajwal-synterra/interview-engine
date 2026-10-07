# Socratic Interview Engine — Visual Architectural Guide
**Phases 1 to 5: Mathematical Foundations & Core Routing Engines**

---

## 1. Master System Flow: What Happens on Every Turn?

In a live interview, when the candidate speaks, five engines work together in milliseconds to evaluate, score, proctor, and route the conversation.

```mermaid
sequenceDiagram
    autonumber
    actor Candidate
    participant Alex as AI Interviewer (Alex)
    participant Evaluator as Shadow Evaluator
    participant Router as PolicyRouter (FSM)
    participant Proctor as ProctorEngine (BII)
    participant BKT as BKTNode (Mastery)
    participant Graph as KnowledgeGraph (HHGKT)
    participant MIRT as MIRTEngine (5D Radar)

    Alex->>Candidate: "How would you handle cache stampedes in a distributed cache?"
    Candidate->>Alex: (Speaks answer over audio...)
    
    par Parallel Turn Analysis
        Candidate->>Evaluator: Transcript & Acoustic Audio
        Candidate->>Proctor: Latency (ms) & Lexical Content
    end

    Proctor->>Proctor: Check TTR, Jitter & Contradiction
    Proctor-->>Router: Updated BII (1.0 -> 0.0)

    Evaluator->>Evaluator: Rubric Grading (Observation: 0 or 1)
    Evaluator-->>Router: Observation (0 or 1) + Depth Score

    critical Policy State Machine Update
        Router->>BKT: update(observation, scaffolding_level)
        BKT-->>Router: New P(L), Delta, is_surge flag
        Router->>MIRT: update_ability(skill, observation, difficulty)
        MIRT-->>Router: Updated 5D Theta Vector

        alt Surge Detected (Delta >= 0.35)
            Router->>Router: State -> DEVILS_ADVOCATE
            Router-->>Alex: "Deploy Devil's Advocate: Challenge with extreme edge case!"
        else Candidate Answered Correctly (Observation = 1)
            alt Skill Mastered (P(L) >= 0.85)
                Router->>Graph: propagate_mastery(skill)
                Graph-->>Router: Downstream Skills Boosted
                Router->>Graph: get_next_recommended_skill()
                Graph-->>Router: Next Optimal Topic
                Router-->>Alex: "Skill Mastered. Transition to Next Topic."
            else Still In Progress
                Router-->>Alex: "Deepen Exploration: Ask about failure modes."
            end
        else Candidate Struggled (Observation = 0)
            alt Scaffolding < Level 3
                Router->>Router: Increment Scaffolding (L1 -> L2 -> L3)
                Router-->>Alex: "Provide Socratic Hint / Trade-off Choice"
            else Scaffolding Exhausted (Failed L3)
                Router->>Graph: get_next_recommended_skill()
                Graph-->>Router: Next Optimal Topic
                Router-->>Alex: "Topic Conceded. Move to Next Topic."
            end
        end
    end

    Alex->>Candidate: Next Question / Socratic Follow-up
```

---

## 2. Engine 1: Bayesian Knowledge Tracing (BKT) — `app/bkt_engine.py`

### Why do we need it?
In classical tests, an answer is either 100% correct or 0% wrong. But in an interview:
- A candidate might get a question right by a lucky guess or memorized buzzword (**Guess rate $P(G)$**).
- A great senior engineer might stumble on a small syntax detail (**Slip rate $P(S)$**).
- Interviews are dialogues where people learn as they speak (**Transit rate $P(T)$**).

BKT maintains a continuous belief probability $P(L) \in [0.001, 0.999]$ representing the true probability that the candidate has mastered the concept.

```mermaid
flowchart TD
    Start(["Candidate Response: Observation (0 or 1)"]) --> Step1

    subgraph Step1 ["Step 1: Dynamic Slip Floor Protection"]
        ObsCheck{"Is Answer Wrong? (O = 0)"}
        ObsCheck -->|Yes| IncSlip["consecutive_slips += 1<br/>P(S) = min(0.25, 0.10 + 0.05 * errors)"]
        ObsCheck -->|No| ResetSlip["consecutive_slips = 0<br/>P(S) = 0.10 (Baseline)"]
    end

    Step1 --> Step2

    subgraph Step2 ["Step 2: Closed-form Bayesian Posterior P(L | O)"]
        BayesCorrect["If O=1:<br/>Numerator = P_prev * (1 - P(S))<br/>Denominator = Num + (1 - P_prev) * P(G)"]
        BayesWrong["If O=0:<br/>Numerator = P_prev * P(S)<br/>Denominator = Num + (1 - P_prev) * (1 - P(G))"]
    end

    Step2 --> Step3

    subgraph Step3 ["Step 3: Forward State Transition P(T)"]
        TransitCheck{"Was answer Correct?"}
        TransitCheck -->|Yes| AddTransit["P_trans = Posterior + (1 - Posterior) * P(T)<br/>Candidate demonstrated learning!"]
        TransitCheck -->|No| NoTransit["P_trans = Posterior<br/>No transit added on failures!"]
    end

    Step3 --> Step4

    subgraph Step4 ["Step 4: Anti-Coaching Scaffolding Decay"]
        ScaffoldCheck{"Did they use Hints? (Level > 0)"}
        ScaffoldCheck -->|Yes| ApplyDecay["effective_delta = delta * (0.85 ^ level)<br/>Penalty for needing hand-holding!"]
        ScaffoldCheck -->|No| KeepDelta["effective_delta = delta (Full Credit)"]
    end

    Step4 --> Step5

    subgraph Step5 ["Step 5: Surge Detection & Status Check"]
        SurgeCheck{"Is Delta >= 0.35?"}
        SurgeCheck -->|Yes| FlagSurge["Flag is_surge = True<br/>Triggers Devil's Advocate!"]
        SurgeCheck -->|No| CheckMastery{"Is P(L) >= 0.85?"}
        CheckMastery -->|Yes| Mastered["Status = MASTERED"]
        CheckMastery -->|No| InProg["Status = IN_PROGRESS"]
    end
```

### The Key Calibrations We Made:
| Parameter | Classroom BKT | Our Interview Engine | Why We Changed It |
|---|---|---|---|
| **$P(G)$ (Guess)** | `0.05` | `0.20` | Candidates can bluff or recite buzzwords. $0.05$ caused 1 correct answer to give instant 95% mastery. |
| **$P(T)$ (Transit)** | `0.15` (unconditional) | `0.05` (conditional on $O=1$) | Failing a question in an interview does not magically teach the candidate distributed systems. |
| **Slip Floor** | Fixed `0.10` | Dynamic `0.10 -> 0.25` | Consecutive failures cannot be excused as "accidental slips". |

---

## 3. Engine 2: Hierarchical Heterogeneous Knowledge Graph (HHGKT) — `app/graph_engine.py`

### Why do we need it?
An engineer's knowledge is not a flat list of independent questions. Skills depend on each other hierarchically.

The Knowledge Graph manages two key relationships:
1. **`PREREQUISITE` (Directed $A \to B$):** Skill A must have $P(L) \ge 0.50$ before the interviewer is allowed to ask about Skill B.
2. **`CO_REQUISITE` (Bidirectional $A \leftrightarrow B$):** Synergistic skills that reinforce each other.

```mermaid
graph TD
    classDef foundation fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef advanced fill:#14532d,stroke:#22c55e,stroke-width:2px,color:#fff;
    classDef locked fill:#450a0a,stroke:#ef4444,stroke-width:2px,color:#fff;

    DSA["DATA_STRUCTURES_ALGORITHMS<br/>(P(L) = 0.85 - Mastered)"]:::foundation
    API["API_DESIGN_PROTOCOLS<br/>(P(L) = 0.50 - In Progress)"]:::foundation

    CACHE["DISTRIBUTED_CACHING<br/>(Prereq Unlocked! Ready)"]:::advanced
    DB["DATABASE_MODELING_TRANSACTIONS<br/>(Prereq Unlocked! Ready)"]:::advanced
    ASYNC["ASYNC_CONCURRENCY<br/>(P(L) = 0.48 - Max Uncertainty)"]:::advanced
    EVENT["EVENT_STREAMING_MESSAGING<br/>(LOCKED: Requires ASYNC >= 0.50)"]:::locked

    DSA -->|"PREREQUISITE (w=0.75)"| CACHE
    DSA -->|"PREREQUISITE (w=0.70)"| DB
    API -->|"PREREQUISITE (w=0.65)"| ASYNC
    ASYNC -.->|"PREREQUISITE (w=0.80)<br/>GATE BLOCKED"| EVENT

    ASYNC <-->|"CO_REQUISITE (w=0.65)"| CACHE
    EVENT <-->|"CO_REQUISITE (w=0.60)"| CACHE
```

### The Two Core Graph Algorithms:

#### 1. Mastery Propagation (Message Passing)
When a candidate masters DSA ($P(L) \ge 0.85$), confidence automatically flows downstream:
$$\text{Influence} = (P(L_{\text{DSA}}) - 0.50) \times \text{weight} \times 0.40$$
- If you prove you know Hash Maps and Trees, your initial prior for **Distributed Caching** automatically jumps from `0.40 -> 0.52`.

#### 2. Active Information Gain (Question Selection)
To avoid wasting interview time, the graph recommends the topic with **Maximum Uncertainty** (closest to $P(L) = 0.50$):
$$\text{Uncertainty} = 1.0 - |P(L) - 0.50|$$
- If Skill A is at `0.85` (already known) and Skill B is at `0.48` (uncertain): the engine **picks Skill B** to maximize knowledge gained per turn.

---

## 4. Engine 3: Policy Router & Finite State Machine (FSM) — `app/policy_router.py`

### Why do we need it?
An AI interviewer cannot just ask random questions. It needs a deterministic pedagogical strategy:
- When should it give a hint?
- What kind of hint?
- When should it attack a suspicious claim?
- When should it stop and move to the next topic?

```mermaid
stateDiagram-v2
    [*] --> READY
    READY --> ACTIVE: initialize_session()

    state ACTIVE {
        [*] --> OpenEndedQuestion
        OpenEndedQuestion: Ask open-ended question (Level 0)
    }

    ACTIVE --> SCAFFOLDING_L1: Observation = 0 (Failed L0)
    SCAFFOLDING_L1: Socratic Nudge (No solution given)

    SCAFFOLDING_L1 --> SCAFFOLDING_L2: Observation = 0 (Failed L1)
    SCAFFOLDING_L2: Scenario Skeleton / Concrete Template

    SCAFFOLDING_L2 --> SCAFFOLDING_L3: Observation = 0 (Failed L2)
    SCAFFOLDING_L3: Binary Trade-off Choice

    SCAFFOLDING_L3 --> ACTIVE: Observation = 0 (Failed L3)<br/>[Concede Topic as Unmastered -> Next Skill]

    SCAFFOLDING_L1 --> ACTIVE: Observation = 1 (Solved with nudge)<br/>[Score penalized by 0.85]
    SCAFFOLDING_L2 --> ACTIVE: Observation = 1 (Solved with skeleton)<br/>[Score penalized by 0.72]
    SCAFFOLDING_L3 --> ACTIVE: Observation = 1 (Solved with choice)<br/>[Score penalized by 0.61]

    ACTIVE --> DEVILS_ADVOCATE: Mastery Surge Detected! (Delta >= 0.35)
    
    state DEVILS_ADVOCATE {
        [*] --> AttackChoice
        AttackChoice: Deliberately challenge design with extreme edge case
    }

    DEVILS_ADVOCATE --> ACTIVE: Defense Succeeded (Obs = 1)<br/>[Mastery LOCKED >= 0.90 -> Next Skill]
    DEVILS_ADVOCATE --> ACTIVE: Defense Failed (Obs = 0)<br/>[Mastery COLLAPSED <= 0.20 -> Next Skill]

    ACTIVE --> COMPLETED: All topics evaluated
    COMPLETED --> [*]
```

---

## 5. Engine 4: Multidimensional Item Response Theory (MIRT) — `app/mirt_engine.py`

### Why do we need it?
BKT tells us if someone knows *Distributed Caching*. But hiring managers need to know:
> *"Is this person a Mid-level or a Staff engineer in System Design?"*

MIRT maps every turn onto a continuous **5-Dimensional Ability Vector ($\boldsymbol{\theta}$)**:
1. `algorithms`
2. `system_design`
3. `concurrency`
4. `databases`
5. `distributed_systems`

```mermaid
graph LR
    subgraph Question ["Question Item Parameters"]
        Diff["Difficulty (b)<br/>Range: -3.0 (Easy) to +3.0 (Staff)"]
        Disc["Discrimination Vector (alpha)<br/>{distributed: 1.4, concurrency: 1.1, system_design: 0.8}"]
    end

    subgraph MathModel ["MIRT Neural Math"]
        Predict["P(correct) = sigmoid( alpha · theta - b )"]
        Residual["Residual = Observation - P(correct)"]
        Update["theta_new = theta_old + eta * alpha * Residual"]
        Error["Uncertainty / Standard Error shrinks via Fisher Info"]
    end

    subgraph Radar ["Final Executive Radar Output"]
        Pct["Percentile = 50 * (1 + erf(theta / sqrt(2)))"]
        Tier["Seniority Tier Mapping<br/>>= 2.0: Staff<br/>>= 1.0: Senior<br/>>= 0.0: Mid-Level<br/>< 0.0: Junior"]
    end

    Question --> MathModel
    MathModel --> Radar
```

### The Difference Between Classical Scoring and MIRT:
- **Classical Test:** Getting an easy question right gives 1 point. Getting an impossible question right gives 1 point.
- **MIRT:** 
  - If you solve a **Difficulty $+1.8$** question, $\theta$ jumps significantly.
  - If you fail a **Difficulty $+1.8$** question, the model expected you to struggle anyway, so your score **barely drops**!

---

## 6. Engine 5: Behavioral Proctor Engine (BII) — `app/proctor_engine.py`

### Why do we need it?
In remote AI interviews, candidates can cheat using:
1. **ChatGPT/Claude screens** (reading pre-generated text).
2. **Audio transcription copilots** (listening through headphones).
3. **Memorized buzzwords without real comprehension**.

The Proctor Engine monitors behavioral acoustics and linguistics to maintain the **Behavioral Integrity Index ($\text{BII}$)**:
- Starts at **`1.00`** (flawless integrity).
- If $\text{BII} < \mathbf{0.70}$, the candidate is classified as **`FLAGGED_FOR_FRAUD`** (automatic disqualification regardless of technical score).

```mermaid
flowchart TD
    TurnData(["Candidate Audio Turn Data"]) --> D1 & D2 & D3 & D4

    subgraph D1 ["Detector 1: Lexical Density (TTR)"]
        TTRCheck{"Words >= 35 AND<br/>TTR > 0.88?"}
        TTRCheck -->|Yes| FlagTTR["Flag: UNNATURAL_LEXICAL_DENSITY_TTR<br/>Penalty: -0.10<br/>(Candidate reading formal LLM screen)"]
        TTRCheck -->|No| CleanTTR["Natural human repetition/fillers"]
    end

    subgraph D2 ["Detector 2: Copilot Latency Jitter"]
        JitterCheck{"Turns >= 3 AND<br/>Mean Latency > 2000ms AND<br/>Jitter StdDev < 180ms?"}
        JitterCheck -->|Yes| FlagJitter["Flag: COPILOT_LATENCY_JITTER_ANOMALY<br/>Penalty: -0.40<br/>(Mechanical external LLM turnaround signature)"]
        JitterCheck -->|No| CleanJitter["Natural human hesitation variance"]
    end

    subgraph D3 ["Detector 3: Contradiction Probe"]
        ProbeCheck{"Injected False Premise<br/>blindly accepted?"}
        ProbeCheck -->|Yes| FlagProbe["Flag: CONTRADICTION_PROBE_FAILED<br/>Penalty: -0.35<br/>(Bluffing / teleprompter compliance)"]
        ProbeCheck -->|No| CleanProbe["Authentic engineer pushed back"]
    end

    subgraph D4 ["Detector 4: Conversational Curiosity"]
        CuriosityCheck{"Turns >= 5 with<br/>0 clarifying questions?"}
        CuriosityCheck -->|Yes| FlagCuriosity["Flag: PASSIVE_COMPLIANCE_ZERO_CURIOSITY<br/>Penalty: -0.08<br/>(Lack of architectural inquiry)"]
        CuriosityCheck -->|No| CleanCuriosity["Asked scale/QPS constraints"]
    end

    FlagTTR & FlagJitter & FlagProbe & FlagCuriosity --> CalcBII["Calculate Final BII = max(0.0, 1.0 - Sum(Penalties))"]

    CalcBII --> VerdictCheck{"Is BII >= 0.70?"}
    VerdictCheck -->|Yes| Passed["Integrity Status: PASSED"]
    VerdictCheck -->|No| Disqualified["Integrity Status: FLAGGED_FOR_FRAUD<br/>(Overrides all technical marks)"]
```

---

## 7. Complete Summary Table

| Engine | File | Mathematical Foundation | Core Role in Interview |
|---|---|---|---|
| **BKT Engine** | `app/bkt_engine.py` | Closed-form Bayesian Probability & Scaffolding Decay | Tracks **per-skill latent mastery** $P(L) \in [0, 1]$ |
| **Knowledge Graph** | `app/graph_engine.py` | Graph Message Passing & Active Information Gain | Enforces **prerequisites** & picks the optimal next question |
| **Policy Router** | `app/policy_router.py` | Deterministic Finite State Machine (FSM) | Directs the interviewer (**Hints, Devil's Advocate, Transitions**) |
| **MIRT Engine** | `app/mirt_engine.py` | Multidimensional Item Response Theory & Fisher Info | Computes **5D Engineering Ability Radar** & Percentiles |
| **Proctor Engine** | `app/proctor_engine.py` | Shannon Entropy, Acoustic Jitter & Contradiction Probing | Detects **AI teleprompter cheating** via BII score |

---

## What Comes Next in Phase 6?
Now that the scoring, graph navigation, policy directing, ability radar, and fraud proctoring are completely built and verified, we are ready for **Phase 6: The Shadow Evaluator (`app/evaluator_engine.py`)**. 

The Shadow Evaluator is the background listener that sends the candidate's transcript to **Gemini 2.5 Flash**, grades it against multidimensional rubrics in under 6.5 seconds, and outputs the `observation` (`0` or `1`) and `depth_score` that feeds directly into all the engines above!
