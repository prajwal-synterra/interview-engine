"""
Verification Test Suite for HHGKT Graph Engine.
Tests:
1. Knowledge graph topology creation.
2. Message-passing: Mastering prerequisite boosts child skill prior.
3. Prerequisite gating: Child skill blocked until prerequisite clears readiness threshold.
4. Next-skill recommendation based on maximum information leverage.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph_engine import KnowledgeGraph, EdgeType
from app.bkt_engine import SeniorityTier, MasteryStatus


def test_graph_topology_and_message_passing():
    print("\n--- Test 1: Graph Message Passing (Mastery Transfer) ---")
    graph = KnowledgeGraph(seniority=SeniorityTier.JUNIOR)

    # Register skills
    graph.add_skill("os_concurrency", custom_prior=0.25)
    graph.add_skill("event_loop", custom_prior=0.25)
    graph.add_skill("redis_cache", custom_prior=0.25)

    # Define edges: os_concurrency is a PREREQUISITE for event_loop
    graph.add_dependency("os_concurrency", "event_loop", EdgeType.PREREQUISITE, weight=0.8)
    graph.add_dependency("event_loop", "redis_cache", EdgeType.CO_REQUISITE, weight=0.5)

    initial_event_loop_prior = graph.nodes["event_loop"].p_l
    print(f"Initial 'event_loop' Prior: {initial_event_loop_prior:.4f}")

    # Candidate demonstrates deep mastery on os_concurrency
    graph.nodes["os_concurrency"].update(observation=1, scaffolding_level=0)
    graph.nodes["os_concurrency"].update(observation=1, scaffolding_level=0)
    print(f"'os_concurrency' final mastery: {graph.nodes['os_concurrency'].p_l:.4f}")

    # Trigger message passing
    propagated = graph.propagate_mastery("os_concurrency")
    print(f"Propagated updates: {propagated}")

    assert graph.nodes["event_loop"].p_l > initial_event_loop_prior
    print(f"[PASS] Prerequisite mastery boosted 'event_loop' prior from {initial_event_loop_prior:.4f} to {graph.nodes['event_loop'].p_l:.4f}")


def test_prerequisite_gating():
    print("\n--- Test 2: Prerequisite Readiness Gating ---")
    graph = KnowledgeGraph(seniority=SeniorityTier.STUDENT)

    graph.add_skill("database_indexes", custom_prior=0.15)
    graph.add_skill("sharding_distributed_query", custom_prior=0.15)
    graph.add_dependency("database_indexes", "sharding_distributed_query", EdgeType.PREREQUISITE, weight=0.9)

    # Check readiness of advanced sharding before database indexing is mastered
    is_ready, missing = graph.get_prerequisite_readiness("sharding_distributed_query")
    print(f"Is 'sharding_distributed_query' ready? {is_ready} | Missing: {missing}")
    assert is_ready is False
    assert "database_indexes" in missing

    # Candidate answers database_indexes correctly
    graph.nodes["database_indexes"].update(observation=1, scaffolding_level=0)
    print(f"'database_indexes' new mastery: {graph.nodes['database_indexes'].p_l:.4f}")

    is_ready_now, _ = graph.get_prerequisite_readiness("sharding_distributed_query")
    assert is_ready_now is True
    print("[PASS] Child skill safely unlocked after prerequisite cleared readiness boundary.")


def test_adaptive_next_skill_recommendation():
    print("\n--- Test 3: Adaptive Next-Skill Routing ---")
    graph = KnowledgeGraph(seniority=SeniorityTier.MID)

    # Add 3 skills
    graph.add_skill("auth_jwt", custom_prior=0.90)       # Already near mastery
    graph.add_skill("api_rate_limiting", custom_prior=0.48) # High uncertainty (near 0.50)
    graph.add_skill("cryptography", custom_prior=0.10)     # Low prior

    next_skill = graph.get_next_recommended_skill()
    print(f"Next recommended skill for maximum info gain: '{next_skill}'")

    assert next_skill == "api_rate_limiting"
    print("[PASS] Successfully prioritized highest information-leverage question node.")


if __name__ == "__main__":
    test_graph_topology_and_message_passing()
    test_prerequisite_gating()
    test_adaptive_next_skill_recommendation()
    print("\n==========================================")
    print("ALL HHGKT GRAPH TESTS PASSED (3/3)!")
    print("==========================================")
