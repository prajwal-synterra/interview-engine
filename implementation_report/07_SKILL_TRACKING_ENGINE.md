# 07 — Skill Tracking Engine (HHGKT — Knowledge Graph)

## Purpose

Tracks the candidate's knowledge state across multiple skills/pillars
using a heterogeneous directed graph where mastery on one node
propagates to related nodes.

## Location

File: app/graph_engine.py
Class: KnowledgeGraph
Called from: policy_router.py, live_server.py

## Graph Structure

Nodes: BKTNode instances (one per competency pillar)
Edges: GraphEdge instances with three types:
  - PREREQUISITE: directed, from foundational to advanced skill
  - CO_REQUISITE: bidirectional, synergistic skills
  - ABSTRACTION: hierarchical parent -> child (defined but not used in live build)

## Standard Ontology Dependencies (Hardcoded)

Prerequisite edges:
  DATA_STRUCTURES_ALGORITHMS -> DISTRIBUTED_CACHING (weight 0.75)
  DATA_STRUCTURES_ALGORITHMS -> DATABASE_MODELING_TRANSACTIONS (weight 0.70)
  API_DESIGN_PROTOCOLS -> ASYNC_CONCURRENCY (weight 0.65)
  ASYNC_CONCURRENCY -> EVENT_STREAMING_MESSAGING (weight 0.80)
  DATABASE_MODELING_TRANSACTIONS -> DISTRIBUTED_CACHING (weight 0.70)
  DATABASE_MODELING_TRANSACTIONS -> NOSQL_DISTRIBUTED_STORAGE (weight 0.75)

Co-requisite edges:
  ASYNC_CONCURRENCY <-> DISTRIBUTED_CACHING (weight 0.65)
  EVENT_STREAMING_MESSAGING <-> DISTRIBUTED_CACHING (weight 0.60)
  AI_INFERENCE_ORCHESTRATION <-> ASYNC_CONCURRENCY (weight 0.70)
  AI_INFERENCE_ORCHESTRATION <-> API_DESIGN_PROTOCOLS (weight 0.60)
  CONTAINER_INFRASTRUCTURE <-> EVENT_STREAMING_MESSAGING (weight 0.55)
  CONTAINER_INFRASTRUCTURE <-> API_DESIGN_PROTOCOLS (weight 0.50)
  CLOUD_SECURITY_AUTH <-> API_DESIGN_PROTOCOLS (weight 0.65)

## Graph Construction (per session)

live_server.py line ~1645:
1. match_candidate_topics() returns top-3 pillars
2. build_dynamic_pillar_graph(matched_pillars, seniority) called
3. Nodes added with tier-calibrated initial priors
4. Relevant edges wired from STANDARD_ONTOLOGY_DEPENDENCIES
5. Isolated nodes bridged with CO_REQUISITE to nearest peer

## Next Skill Recommendation Algorithm

```python
# KnowledgeGraph.get_next_recommended_skill()
For each IN_PROGRESS node with all prerequisites at P(L) >= 0.50:
    uncertainty = 1.0 - abs(node.p_l - 0.50)
    # Higher uncertainty = closer to 0.50 = more information gain
Sort by uncertainty descending -> pick top skill
```

## Mastery Propagation (Message Passing)

When a skill is mastered:
```python
# KnowledgeGraph.propagate_mastery(source_skill)
For each outgoing edge from source:
    mastery_influence = (source_p - 0.50) * edge_weight * 0.40
    target_node.p_l += mastery_influence  # boosted if source mastered, dampened if deficient
    target_node.p_l = clamp(new_p, 0.05, 0.95)
```

This means mastering DATA_STRUCTURES_ALGORITHMS raises the initial prior
for DISTRIBUTED_CACHING and DATABASE_MODELING_TRANSACTIONS.

## Prerequisite Gate

Before recommending a skill, system checks:
```python
# get_prerequisite_readiness(skill_code)
For each PREREQUISITE edge pointing to skill:
    If prereq_node.p_l < 0.50: add to missing_prereqs
Returns (is_ready, missing_prereqs)
```

A skill with unmet prerequisites is skipped in get_next_recommended_skill().

## Dynamic Graph (per session)

The graph is built from the candidate's vector-matched pillars.
Two candidates get different graphs if their introduction texts match different pillars.

## Compacted Topic Cards

When a topic is exited (mastery >= 0.80 or turns >= 3):
- Status: "MASTERED" or "INCOMPLETE"
- Verdict summary saved to PostgreSQL compacted_topic_cards
- Graph mastery propagation runs for downstream skills
