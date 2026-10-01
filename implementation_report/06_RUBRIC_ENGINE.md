# 06 — Rubric Engine

## Purpose

Defines what constitutes a correct, partially correct, or incorrect answer
for any given question within the Shadow Evaluator.

## Location

File: app/evaluator_engine.py
Function: evaluate_candidate_response()
The rubric is embedded in the prompt sent to gemini-3.1-flash-lite.

## Rubric Structure (Current)

The rubric has 4 fixed dimensions:

| Criterion | What it Measures |
|-----------|-----------------|
| Core Concept Depth | Does the candidate understand underlying principles? |
| Practical Implementation | Did they mention concrete tools/patterns for the active ecosystem? |
| Trade-off Awareness | Did they identify failure modes, complexity, trade-offs? |
| Technical Relevance & Focus | Did they directly address the prompt? |

Each criterion returns: {"criterion": "...", "passed": true/false, "note": "..."}

## Rubric Generation Timing

CURRENT: The rubric is generated INSIDE the same LLM call that sees the candidate answer.
This means the rubric outcomes are answer-aware — the LLM decides pass/fail after reading the answer.

PROPOSED: Generate rubric criteria BEFORE showing the candidate answer;
lock criteria; then evaluate in a separate call.

## Is the Rubric Immutable After Generation?

NO. Because there is no separate pre-generation step.
The same LLM call simultaneously determines both the correct answer criteria
and evaluates whether the candidate met them.

## Can the Candidate Influence the Rubric?

PARTIALLY. The candidate answer is quoted data in the prompt.
The LLM has instructions not to follow candidate instructions.
However, because the rubric criteria and evaluation happen in one call,
a particularly convincing-sounding answer might influence the LLM's pass/fail decision.

## How the Rubric Connects to Scoring

```
rubric_items[*].passed -> not directly aggregated mathematically
observation (top-level) -> binary 0 or 1 -> fed to BKT update
depth_score -> normalised to [0.0, 1.0] -> stored in turn telemetry
estimated_difficulty -> fed to MIRT as item difficulty parameter
```

observation is the only rubric output that directly affects BKT mastery.

## Handling of Off-Topic / Trivial Answers

Explicitly specified in evaluator prompt:
"If the candidate asked unrelated trivia questions ... went completely off-topic ...
 you MUST set observation: 0 and depth_score: 0.10"

## Scaffolding Effect on Rubric

Scaffolding level is passed to the evaluator as context.
A correct answer at scaffolding L2 (with partial hints) still results in observation:1,
but the BKT anti-coaching decay reduces the effective mastery gain.

## What is NOT Implemented

- Pre-locked rubric (rubric generated before candidate answers)
- Rubric versioning or immutability guarantee
- Alternative valid answer handling (beyond LLM judgment)
- Rubric per question type (conceptual vs implementation vs debugging)
- Hallucination detection in candidate claims
