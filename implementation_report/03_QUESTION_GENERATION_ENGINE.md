# 03 — Question Generation Engine

## Purpose

Selects which engineering topic/pillar to ask about and injects the
right Socratic prompt directive so Gemini Live (Alex) generates
a contextually relevant question.

## Status: PARTIALLY IMPLEMENTED

There is NO static question bank. Questions are generated entirely by
the Gemini Live LLM (Alex) based on server-injected contextual directives.
The system controls WHAT topic and WHAT angle to ask from; the LLM
decides the exact phrasing.

## Question Selection Flow

```
Candidate Introduction Text
    -> match_candidate_topics() [vector_service.py]
       -> Gemini embedding-2 (768D)
       -> DynamoDB search_vectors (cosine similarity, top-k=3)
       -> Returns matched CompetencyPillars sorted by criticality + similarity
    -> build_dynamic_pillar_graph() [graph_engine.py]
       -> Nodes: matched pillar BKT nodes
       -> Edges: STANDARD_ONTOLOGY_DEPENDENCIES (prerequisite + co-requisite)
    -> policy_router.graph.get_next_recommended_skill()
       -> Selects pillar closest to P(L)=0.50 boundary (max information gain)
       -> Respects prerequisite gates (prereq must have P(L)>=0.50)
    -> active_topic = selected pillar
```

## Prompt Directive Injection

For each turn, Alex is told:
1. Primary topic code (e.g. ASYNC_CONCURRENCY)
2. Ecosystem dialect (e.g. Java/JVM idioms, Python GIL)
3. Pedagogical instruction (deepen / scaffold / transition)
4. The probe hint from pillar definition (e.g. "How do you handle cache stampedes?")

Alex then generates the actual spoken question.

## Skill Ordering Algorithm

From graph_engine.py KnowledgeGraph.get_next_recommended_skill():

```python
# For each IN_PROGRESS skill with fulfilled prerequisites:
uncertainty = 1.0 - abs(node.p_l - 0.50)
# Select the skill with highest uncertainty (closest to 0.50 decision boundary)
# This maximises Fisher information = tests where system is most uncertain
```

## Topic Transition Triggers

| Trigger | Condition |
|---------|-----------|
| Mastery reached | P(L) >= 0.80 on active topic |
| Turns exhausted | turns_on_active_topic >= 3 |
| All topics done | graph.get_next_recommended_skill() returns None |

## Adaptive Difficulty (via Scaffolding)

Alex's question difficulty is not set by a number.
It is guided by the scaffolding level injected in the prompt directive:
- L0: Open-ended ("Tell me how you handle X")
- L1: Subtle nudge ("Think about what happens when Y fails")
- L2: Partial scenario ("Given this skeleton, fill in Z")
- L3: Binary trade-off choice ("Would you use A or B here?")

## What is NOT Implemented

- Static question bank or question registry
- Pre-rated question difficulty calibration
- Question deduplication (same question could theoretically repeat)
- Domain-specific question generation policies (e.g. Mobile / Flutter)
- Follow-up question chaining based on specific answer content (Alex does this conversationally but it is not programmatically tracked)
