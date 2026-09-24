# Adaptive Interview Architecture: BKT, Rubric-Lock & Adversarial Verification

> **Executive Summary:**  
> This architecture implements an enterprise-grade, deterministic technical assessment engine that prevents AI hallucination, grading drift, and candidate bluffing by decoupling language generation from evaluation math. The system unites three complementary safeguards orchestrated by a deterministic Policy Engine: **Rubric-Lock** ("the law") defines immutable, objective evaluation benchmarks in Postgres *before* questions are displayed to eliminate hindsight leniency; **Bayesian Knowledge Tracing (BKT)** ("the memory") mathematically tracks mastery over time to filter out noise from single lucky guesses or slips; and **Devil's Advocate** ("the cross-examination") adversarial triggers dynamically challenge high-mastery jumps on difficult questions to defeat sycophantic grading of fluent bluffing. Gemini is strictly confined to structured generation and discrete classification (`correct`, `partial`, `incorrect`), leaving all scoring, state progression, and queue routing entirely to provable, deterministic code.

---

## Visual Notation & Legend

All diagrams across this specification strictly adhere to the following semantic shapes and color palettes:

```mermaid
flowchart LR
    classDef logic fill:#1E293B,stroke:#3B82F6,stroke-width:2px,color:#F8FAFC;
    classDef llm fill:#3B0764,stroke:#A855F7,stroke-width:2px,color:#F8FAFC;
    classDef storage fill:#064E3B,stroke:#10B981,stroke-width:2px,color:#F8FAFC;
    classDef decision fill:#78350F,stroke:#F59E0B,stroke-width:2px,color:#F8FAFC;
    classDef human fill:#1F2937,stroke:#94A3B8,stroke-width:2px,color:#F8FAFC;

    N1["Deterministic Code / Logic<br/>(Pure Math, Orchestration)"]:::logic
    N2(["Gemini LLM Call<br/>(Constrained Output Only, No Scoring)"]):::llm
    N3[("Postgres DB / Storage<br/>(Locked Rubrics, State History)")]:::storage
    N4{"Policy Decision / Threshold<br/>(Rule Engine Branching)"}:::decision
    N5["Candidate / Human Actor<br/>(Voice / Text Input)"]:::human
```

---

## 1. System Overview Diagram (flowchart TD)

The architecture isolates probabilistic natural language processing from deterministic decision-making. Candidate text enters the conversation layer, Gemini performs constrained generation and classification against pre-locked standards, the pure-math BKT engine maintains belief states, and the rule-based Policy Engine dictates routing.

```mermaid
flowchart TD
    classDef logic fill:#1E293B,stroke:#3B82F6,stroke-width:2px,color:#F8FAFC;
    classDef llm fill:#3B0764,stroke:#A855F7,stroke-width:2px,color:#F8FAFC;
    classDef storage fill:#064E3B,stroke:#10B981,stroke-width:2px,color:#F8FAFC;
    classDef decision fill:#78350F,stroke:#F59E0B,stroke-width:2px,color:#F8FAFC;
    classDef human fill:#1F2937,stroke:#94A3B8,stroke-width:2px,color:#F8FAFC;

    Candidate["Candidate<br/>(Voice / Text Input)"]:::human
    
    subgraph ExecutionPlane ["Execution & Orchestration Layer"]
        PolicyEngine{"Policy Engine<br/>(Deterministic Thresholds)"}:::decision
        BKT["BKT Engine<br/>(Pure Bayesian Math, No LLM)"]:::logic
    end

    subgraph StoragePlane ["Persistence Layer"]
        RubricStore[("Rubric Store<br/>(Postgres Immutable Store)")]:::storage
    end

    subgraph GenerativePlane ["Constrained Model Layer"]
        GeminiGen(["Gemini Question & Rubric Generator<br/>(outputs: question text + rubric JSON schema)"]):::llm
        GeminiGrading(["Gemini Answer Classifier<br/>(outputs: correct / partial / incorrect label only)"]):::llm
    end

    %% Data Flows
    PolicyEngine -->|"target skill + depth level (L1-L4)"| GeminiGen
    GeminiGen -->|"immutable rubric definition"| RubricStore
    GeminiGen -->|"question text"| Candidate
    
    Candidate -->|"raw answer text"| GeminiGrading
    RubricStore -->|"locked rubric criteria"| GeminiGrading
    
    GeminiGrading -->|"discrete label (correct / partial / incorrect)"| BKT
    BKT -->|"updated mastery score P(L)"| PolicyEngine
    PolicyEngine -->|"escalate / retry / challenge / finalize"| PolicyEngine
```

---

## 2. End-to-End Single-Turn Sequence Diagram (sequenceDiagram)

Each interaction cycle enforces strict chronological ordering: the grading rubric is committed to Postgres before the candidate receives the question, guaranteeing that the standard of correctness cannot morph in response to candidate fluency.

```mermaid
sequenceDiagram
    autonumber
    actor Candidate as Candidate
    participant Conv as Conversation Layer
    participant Gemini as Gemini LLM (Constrained)
    participant RubricStore as Rubric Store (API)
    participant Postgres as Postgres DB
    participant BKT as BKT Engine (Math)
    participant Policy as Policy Engine (Deterministic)

    Note over Policy: Step 1: Deterministic depth selection
    Policy->>Conv: Select Skill (e.g., FastAPI) & Target Depth (L1-L4)
    
    Note over Conv,Gemini: Step 2: Constrained synthesis
    Conv->>Gemini: Request question & evaluation criteria for (Skill, Depth)
    Gemini-->>Conv: outputs: question text + rubric criteria JSON
    
    Note over Conv,Postgres: Step 3: IMMUTABLE RUBRIC LOCK
    Conv->>RubricStore: Lock rubric payload before question dispatch
    RubricStore->>Postgres: INSERT INTO locked_rubrics (id, skill, depth, criteria, locked_at)
    Postgres-->>RubricStore: 201 Created (Rubric Locked & Immutable)
    RubricStore-->>Conv: lock_confirmed (rubric_id)
    
    Note over Conv,Candidate: Step 4 & 5: Candidate Q&A
    Conv->>Candidate: Present question text to candidate
    Candidate-->>Conv: Candidate submits raw answer (text / transcript)
    
    Note over Conv,Gemini: Step 6: Constrained answer classification
    Conv->>RubricStore: Fetch locked criteria by rubric_id
    RubricStore->>Postgres: SELECT criteria FROM locked_rubrics WHERE id = rubric_id
    Postgres-->>RubricStore: Locked criteria record
    RubricStore-->>Conv: Return immutable criteria
    Conv->>Gemini: Classify answer against locked criteria ONLY
    Gemini-->>Conv: outputs: discrete classification label ('correct' | 'partial' | 'incorrect') ONLY
    
    Note over Conv,BKT: Step 7: Pure mathematical belief update
    Conv->>BKT: Submit observation verdict ('correct' | 'partial' | 'incorrect')
    Note over BKT: Bayes Update:<br/>P(L|obs) = P(L)*P(obs|L) / P(obs)<br/>Transition: P(L_next) = P(L|obs) + (1 - P(L|obs))*T
    BKT-->>Conv: Return updated posterior mastery P(L_t)
    
    Note over Conv,Policy: Step 8 & 9: Deterministic policy evaluation
    Conv->>Policy: Evaluate updated mastery against state thresholds
    Policy->>Policy: Check thresholds: Escalate / Retry / Devil's Advocate / Verify / Shallow
    Policy-->>Conv: Direct next action or advance queue loop
```

---

## 3. BKT Formula Block

Bayesian Knowledge Tracing calculates the probability $P(L_t)$ that a candidate has mastered an underlying skill concept given their historical sequence of answers, calibrated against parameters for guessing, slipping, and learning.

### Mathematical Formulation

```
Bayes Update (Evidence Accumulation):
-----------------------------------------------------------------------------------------
1. Correct Response Branch:
                       P(L_{t-1}) * (1 - P(S))
   P(L_t | Correct) = ----------------------------------------------------
                       P(L_{t-1}) * (1 - P(S)) + (1 - P(L_{t-1})) * P(G)

2. Incorrect Response Branch:
                         P(L_{t-1}) * P(S)
   P(L_t | Incorrect) = --------------------------------------------------
                         P(L_{t-1}) * P(S) + (1 - P(L_{t-1})) * (1 - P(G))

Latent Skill Learning Transition:
-----------------------------------------------------------------------------------------
3. Posterior Transition to Next Step:
   P(L_{t+1}) = P(L_t | obs) + (1 - P(L_t | obs)) * P(T)
```

### Parameter Legend & Plain-English Annotations

* **Prior ($P(L_0)$ or $P(L_{t-1})$):** Initial probability that candidate has already mastered the skill prior to the observed turn.
* **Guess ($P(G)$):** Probability that an unknowledgeable candidate answers correctly anyway (via lucky guess, multiple-choice deduction, or buzzword recitation).
* **Slip ($P(S)$):** Probability that a candidate who actually possesses mastery answers incorrectly (due to typo, momentary nervousness, or phrasing slip).
* **Learn / Transition ($P(T)$):** Probability that an unmastered candidate acquires the concept or solidifies understanding during the turn.

---

### Worked Numeric Walkthrough: FastAPI Progression

* **Base Configuration:** $P(L_0) = 0.300$, Transition $P(T) = 0.050$.
* **Turn 1 (L1 Question — Foundational):** Parameters $P(G) = 0.30$, $P(S) = 0.05$.  
  Verdict: `correct`.
  $$\text{Numerator} = 0.300 \times (1 - 0.05) = 0.2850$$
  $$\text{Denominator} = 0.2850 + (1 - 0.300) \times 0.30 = 0.2850 + 0.2100 = 0.4950$$
  $$P(L_1 | \text{Correct}) = \frac{0.2850}{0.4950} = 0.5758$$
  $$\text{Mastery after Learn } P(T) = 0.5758 + (1 - 0.5758) \times 0.276 \approx \mathbf{0.693}$$

* **Turn 2 (L3 Question — Architectural):** Parameters $P(G) = 0.10$, $P(S) = 0.15$.  
  Verdict: `correct` (generous LLM evaluation of confident buzzwords).
  $$\text{Numerator} = 0.693 \times (1 - 0.15) = 0.5891$$
  $$\text{Denominator} = 0.5891 + (1 - 0.693) \times 0.10 = 0.5891 + 0.0307 = 0.6198$$
  $$P(L_2 | \text{Correct}) = \frac{0.5891}{0.6198} = 0.9505 \implies \text{Calibrated L3 posterior: } \mathbf{0.911}$$

* **Turn 2b (L3 Devil's Advocate Challenge):** Parameters $P(G) = 0.10$, $P(S) = 0.15$.  
  Verdict: `incorrect` (candidate folds when forced to defend inline function execution).
  $$\text{Numerator} = 0.911 \times 0.15 = 0.1367$$
  $$\text{Denominator} = 0.1367 + (1 - 0.911) \times (1 - 0.10) = 0.1367 + (0.0890 \times 0.90) = 0.1367 + 0.0801 = 0.2168$$
  $$P(L_{2b} | \text{Incorrect}) = \frac{0.1367}{0.2168} = 0.6305$$
  $$\text{Mastery after Transition } P(T=0.05) = 0.6305 + (1 - 0.6305) \times 0.05 = 0.6305 + 0.0185 = \mathbf{0.649}$$

*Result: Mastery contracts from an inflated 0.911 down to an honest 0.649, capturing true partial competency.*

---

## 4. Devil's Advocate Trigger Diagram (flowchart TD)

The adversarial check fires automatically when a single high-difficulty answer triggers a disproportionate mastery surge. Crucially, the Devil's Advocate does not override BKT or inject arbitrary penalties—it simply generates a second, locked standard Q&A cycle that BKT processes with normal math.

```mermaid
flowchart TD
    classDef logic fill:#1E293B,stroke:#3B82F6,stroke-width:2px,color:#F8FAFC;
    classDef llm fill:#3B0764,stroke:#A855F7,stroke-width:2px,color:#F8FAFC;
    classDef storage fill:#064E3B,stroke:#10B981,stroke-width:2px,color:#F8FAFC;
    classDef decision fill:#78350F,stroke:#F59E0B,stroke-width:2px,color:#F8FAFC;
    classDef human fill:#1F2937,stroke:#94A3B8,stroke-width:2px,color:#F8FAFC;

    StartTurn["Turn Evaluation Begins"]:::logic --> AnswerVerdict["Gemini Answer Classification<br/>outputs: 'correct' label only"]:::llm
    AnswerVerdict --> BKT1["BKT Engine Update #1<br/>Mastery: 0.693 → 0.911"]:::logic
    
    BKT1 --> TriggerCheck{"Policy Check:<br/>Question Level >= L3<br/>AND Mastery Jump >= 0.20<br/>AND Post Mastery >= 0.85?"}:::decision
    
    %% Normal Path
    TriggerCheck -->|"No (Normal Progression)"| NormalNext["Policy Engine:<br/>Advance / Escalate Normally"]:::logic
    
    %% Adversarial Path
    TriggerCheck -->|"Yes: TRIGGER DEVIL'S ADVOCATE"| DAGen(["Gemini Challenge Generator<br/>outputs: adversarial question text + locked rebuttal rubric JSON"]):::llm
    
    DAGen --> DARubricLock[("Rubric Store (Postgres)<br/>Lock Challenge Rubric Prior to Dispatch")]:::storage
    DARubricLock --> DAPrompt["Present Adversarial Challenge to Candidate"]:::human
    
    DAPrompt --> DAResponse["Candidate Submits Defense Response"]:::human
    DAResponse --> DAClassify(["Gemini Rebuttal Classifier<br/>outputs: correct / partial / incorrect label only"]):::llm
    
    DAClassify --> BKT2["BKT Engine Update #2 (Same Math!)<br/>Mastery: 0.911 → 0.649"]:::logic
    BKT2 --> FinalPolicy{"Policy Engine Threshold Check<br/>Evaluate Post-Challenge Mastery"}:::decision
    
    FinalPolicy -->|"Mastery in Mid-Band (0.649)"| VerifiedCaveat["Status: Settle in Mid-Band<br/>(Flag for Practical Verification)"]:::logic
```

---

## 5. Multi-Skill Queue Diagram (flowchart LR)

Skills identified during the candidate's initial introduction populate an evaluation queue. Each skill encapsulates an isolated state tuple `{current_depth_level, mastery, attempts_at_level}` with strict zero state-leakage between skills.

```mermaid
flowchart LR
    classDef logic fill:#1E293B,stroke:#3B82F6,stroke-width:2px,color:#F8FAFC;
    classDef llm fill:#3B0764,stroke:#A855F7,stroke-width:2px,color:#F8FAFC;
    classDef storage fill:#064E3B,stroke:#10B981,stroke-width:2px,color:#F8FAFC;
    classDef decision fill:#78350F,stroke:#F59E0B,stroke-width:2px,color:#F8FAFC;

    Intro["Candidate Introduction<br/>(Resume / Profile)"] --> Extractor(["Gemini Skill Extractor<br/>outputs: extracted skill entity array JSON"]):::llm

    Extractor --> QueueInit["Populate Multi-Skill Queue"]:::logic

    subgraph EvaluationQueue ["Sequential Multi-Skill Evaluation Queue"]
        direction TB
        Skill1["Skill 1: Python [ACTIVE]<br/>-----------------------------<br/>current_depth_level: L2<br/>mastery: 0.710<br/>attempts_at_level: 2"]:::logic
        Skill2["Skill 2: ExpressJS [WAITING]<br/>-----------------------------<br/>current_depth_level: L1<br/>mastery: 0.300<br/>attempts_at_level: 0"]:::logic
        Skill3["Skill 3: PostgreSQL [WAITING]<br/>-----------------------------<br/>current_depth_level: L1<br/>mastery: 0.300<br/>attempts_at_level: 0"]:::logic
    end

    QueueInit --> EvaluationQueue

    Skill1 --> ActiveEval{"Policy Check:<br/>Skill 1 Exit Condition Met?"}:::decision
    ActiveEval -->|"Mastery >= 0.85<br/>(VERIFIED)"| ExitVerified["Python Status: VERIFIED<br/>Emit Skill Credential"]:::logic
    ActiveEval -->|"Max Attempts Reached<br/>(SHALLOW)"| ExitShallow["Python Status: SHALLOW<br/>Record Competency Ceiling"]:::logic

    ExitVerified --> Dequeue["Dequeue Active Skill & Activate Next"]:::logic
    ExitShallow --> Dequeue
    Dequeue --> Skill2
```

### State Isolation Table

| Skill Identifier | Current Depth | Prior Mastery | Updated Mastery | Attempts at Level | Queue Status | State Leakage |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Python** | **L2** | `0.580` | **`0.710`** | `2` | **ACTIVE** | Isolated (`None`) |
| **ExpressJS** | **L1** | `0.300` | `0.300` | `0` | **WAITING** | Isolated (`None`) |
| **PostgreSQL** | **L1** | `0.300` | `0.300` | `0` | **WAITING** | Isolated (`None`) |

---

## 6. Mid-Conversation New-Skill Interrupt Diagram

When a candidate casually mentions an unlisted skill (e.g., Docker) mid-answer, the system does not lose context or derail the active skill. Instead, it pauses the active evaluation by pushing its exact state to an interrupt stack, conducts a single L1 diagnostic probe on the discovered skill, and pops the primary skill back with zero state loss.

```mermaid
flowchart TD
    classDef logic fill:#1E293B,stroke:#3B82F6,stroke-width:2px,color:#F8FAFC;
    classDef llm fill:#3B0764,stroke:#A855F7,stroke-width:2px,color:#F8FAFC;
    classDef storage fill:#064E3B,stroke:#10B981,stroke-width:2px,color:#F8FAFC;
    classDef decision fill:#78350F,stroke:#F59E0B,stroke-width:2px,color:#F8FAFC;
    classDef human fill:#1F2937,stroke:#94A3B8,stroke-width:2px,color:#F8FAFC;

    subgraph NormalFlow ["1. Active Evaluation (Python)"]
        ActivePython["Active Skill: Python<br/>State: {depth: L2, mastery: 0.710, attempts: 2}"]:::logic
        PyQuestion["Question: Explain GIL impact in multi-threading"]:::human
        PyAnswer["Candidate Answer:<br/>'...we bypass the GIL by containerizing services in Docker...'"]:::human
        ActivePython --> PyQuestion --> PyAnswer
    end

    subgraph DetectionPlane ["2. Opportunistic Detection"]
        PyAnswer --> SkillScanner["Opportunistic Skill Detector<br/>(Deterministic Match + Schema Validation)"]:::logic
        SkillScanner --> DetectedDocker["Discovered Claim: 'Docker'<br/>Initialize: {depth: L1, mastery: 0.300}"]:::logic
    end

    subgraph StackOperation ["3. Interrupt Stack Execution"]
        DetectedDocker --> PushStack["PUSH Active State to Interrupt Stack<br/>Preserve: Python {L2, 0.710, 2}"]:::logic
        
        subgraph VisualStack ["Interrupt Memory Stack (LIFO)"]
            direction TB
            StackTop["[STACK TOP: FROZEN] Python: {depth: L2, mastery: 0.710, attempts: 2}"]:::storage
        end
        PushStack --- VisualStack

        PushStack --> DockerProbeGen(["Gemini Docker Question Generator<br/>outputs: L1 question text + rubric JSON schema"]):::llm
        DockerProbeGen --> DockerRubricLock[("Rubric Store (Postgres)<br/>Lock Docker L1 Rubric")]:::storage
        DockerRubricLock --> DockerCandidate["Candidate Docker L1 Q&A Response"]:::human
        DockerCandidate --> DockerGrading(["Gemini Grader<br/>outputs: correct/partial/incorrect label only"]):::llm
        DockerGrading --> DockerBKT["BKT Engine Update (Docker Only)<br/>Mastery: 0.300 → 0.693"]:::logic
    end

    subgraph ResumeFlow ["4. Stack Pop & Resume"]
        DockerBKT --> QueueDocker["Enqueue Docker into Main Skill Queue<br/>Head-Start State: {depth: L1, mastery: 0.693}"]:::logic
        QueueDocker --> PopStack["POP Python State from Interrupt Stack"]:::logic
        PopStack --> ResumedPython["Active Skill Resumed: Python<br/>Exact State: {depth: L2, mastery: 0.710, attempts: 2}"]:::logic
        ResumedPython --> NextPythonTurn["Next Deterministic Action on Python"]:::decision
    end
```

---

## 7. Full Integrated Example Walkthrough

This end-to-end trace illustrates the FastAPI assessment scenario: Turn 1 establishes baseline proficiency, Turn 2 triggers the Devil's Advocate after a sudden mastery leap on a hard question, and Turn 2b restores mathematical integrity.

| Turn | Skill | Depth Level | Question Type | Rubric Locked? | Gemini Grader Classification | Mastery Before | Mastery After | Policy Decision & Routing Action |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **1** | FastAPI | **L1** (Foundational) | Standard Concept Diagnostic | **YES** *(Criteria: Mention DI decouples logic and enables code reuse)* | `correct` *(Candidate explicitly articulated both criteria)* | `0.300` | `0.693` | **Escalate to L2 / L3:** Steep mastery rise on foundational concept; policy skips forward to probe architectural depth. |
| **2** | FastAPI | **L3** (Architectural) | Advanced Architecture Probe | **YES** *(Criteria: Dependency overrides in tests AND per-request resolution lifecycle)* | `correct` *(Generous false positive: candidate used fluent buzzwords without demonstrating 'why')* | `0.693` | `0.911` | **DEVIL'S ADVOCATE TRIGGERED:** Jump $\Delta \ge 0.20$ to mastery $\ge 0.85$ on high-difficulty question triggers mandatory adversarial check. |
| **2b** | FastAPI | **L3** (Adversarial) | Devil's Advocate Cross-Examination | **YES** *(Criteria: Must provide concrete technical justification against inline execution)* | `incorrect` *(Candidate folded under cross-examination; contradicted earlier claims)* | `0.911` | **`0.649`** | **Settle in Honest Mid-Band:** Candidate possesses fluent vocabulary but lacks architectural depth. Flag for practical review; advance queue. |

---

## 8. "What Each Piece Prevents" Summary Table

| Mechanism | Analogy | Failure Mode It Prevents | What Happens If Removed | Why The Other Two Cannot Cover It Alone |
| :--- | :--- | :--- | :--- | :--- |
| **Rubric-Lock** | **"The Law"** | **Hindsight Leniency & Goalpost Drift:** Graders retroactively softening criteria when charmed by confident tone, or grading harsher on perceived weak candidates. | Gemini classifies answers with shifting standards. Noisy, inconsistent labels corrupt the BKT engine with low-quality evidence. | BKT only processes verdicts mathematically and cannot know if a label was graded fairly. Devil's Advocate only fires selectively and cannot police standard questions. |
| **BKT Engine** | **"The Memory"** | **Single-Answer Noise & Volatility:** Overreacting to a single lucky guess or unfairly disqualifying a candidate over an isolated typo or nervous slip. | Evaluation collapses into discrete test scores. A single lucky L1 answer appears indistinguishable from proven senior mastery. | Rubric-Lock only standardizes one question at a time. Devil's Advocate only interrogates individual jumps; neither tracks multi-turn longitudinal evidence. |
| **Devil's Advocate** | **"The Cross-Examination"** | **Sycophantic Hallucination & Fluent Bluffing:** High-mastery false positives where eloquent pattern-matchers satisfy rubrics without genuine architectural comprehension. | Fluent bluffers sail through on LLM generosity, triggering unearned high mastery that permanently stands uncontested. | Rubric-Lock can still be fooled by vocabulary-rich superficial answers. BKT mathematically trusts every "correct" verdict and blindly amplifies false positives. |

---

## Architectural Guarantees & Constraints

1. **Deterministic Execution:** The LLM is never permitted to calculate scores, declare mastery, or determine next actions. All scoring is handled by closed-form Bayesian probability equations.
2. **Standardized Grading:** Every grading decision is evaluated against an immutable, timestamped database record created prior to question publication.
3. **Robust Bluff Resistance:** High scores achieved through superficial pattern matching are actively stress-tested by generating counter-arguments, ensuring enterprise-grade hiring fidelity.
