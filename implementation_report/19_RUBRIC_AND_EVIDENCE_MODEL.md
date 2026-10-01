# 19 — Rubric and Evidence Model

## Current Rubric Architecture

The rubric is NOT pre-generated before candidate answering.
Rubric evaluation and candidate answer scoring happen in a single Gemini REST call.

### Rubric Criteria (Fixed, Hardcoded in evaluator_engine.py)

1. Concept Depth
   Passes when: candidate understands underlying principles and abstractions

2. Practical Implementation
   Passes when: candidate mentions concrete tools, patterns, or ecosystem-specific constructs

3. Trade-off Awareness
   Passes when: candidate identifies failure modes, complexity, or system trade-offs

4. Technical Relevance & Focus
   Passes when: candidate directly addresses the technical prompt
   Automatically fails (observation:0, depth:0.10) when: candidate goes completely off-topic,
   asks trivia, or gives evasive non-technical commentary

### What Constitutes Correct Answer

Determined by Shadow Evaluator LLM for each turn:
  observation == 1 (correct) when: answer meets expectations for the current seniority level
  observation == 0 (failing) when: response is fundamentally flawed, incomplete, or off-topic

### What Constitutes Partially Correct

There is NO explicit partial credit in BKT.
depth_score (0.0 - 1.0) captures partial quality but is NOT fed into BKT update.
depth_score is stored in turn_telemetry_logs and used in reports.
The BKT update only receives binary observation (0 or 1).

### What Constitutes Incorrect

observation == 0 from Shadow Evaluator.
This triggers: scaffolding level increment, dynamic slip floor increase.

### Evidence Required

The Shadow Evaluator determines evidence internally.
There is no structured evidence extraction (e.g. "did they mention O(log n)?").
Evidence is qualitative: LLM judged correctness.

### Alternative Valid Answers

Handled implicitly by the LLM — it can accept alternative valid explanations.
No explicit handling of alternative answers in code.

### Shallow Memorization vs Genuine Understanding

Addressed by:
1. Follow-up questions: Alex is prompted to go deeper on edge cases and failure modes
2. Devil's Advocate: challenges claimed mastery with edge cases when mastery surge detected
3. Scaffolding level tracking: answers given after hints receive lower BKT gain

NOT addressed by: explicit verbatim-detection or memorization fingerprinting.

### Rubric Immutability

CURRENT: Rubric NOT locked before candidate answers.
The LLM evaluates candidate answer AND determines pass/fail in one call.
A persuasive-sounding wrong answer could influence LLM judgment.

PROPOSED (not implemented): 
  Step 1: Before question is asked, call LLM to generate expected answer criteria (locked rubric)
  Step 2: Freeze rubric string
  Step 3: After candidate answers, evaluate against frozen rubric in second call
  Step 4: Rubric cannot be altered by candidate answer content

### Can Candidate Influence the Rubric?

Indirectly possible: candidate answer content is in the same context as rubric evaluation.
Directly: NO — candidate cannot change the rubric via API or WebSocket.

### Rubric Connection to Scoring

rubric_items -> stored in turns_history in-memory
observation -> BKT update (primary scoring impact)
depth_score -> stored in PostgreSQL turn_telemetry_logs (not used in BKT)
recommended_probe -> stored in turns_history (context for next question awareness)

Rubric items are NOT aggregated mathematically.
They are qualitative narrative passed to the report generator.
