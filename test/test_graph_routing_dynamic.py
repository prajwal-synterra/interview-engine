"""
Verification Test Suite for Dynamic Knowledge Graph Dependency Routing.
Document Reference: AIS-ARCH-2026-V3-MASTER / REPORT 5
Tests:
1. Dynamic KnowledgeGraph construction from vector-matched pillars.
2. Topological edge wiring (Prerequisites and Co-requisites).
3. Prerequisite gating: Dependent pillar remains locked until prerequisite clears readiness threshold.
4. Mastery message propagation: Mastering foundational pillar elevates dependent child prior.
5. Information-entropy based next skill selection.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph_engine import (
    KnowledgeGraph, EdgeType, build_dynamic_pillar_graph,
    STANDARD_ONTOLOGY_DEPENDENCIES
)
from app.bkt_engine import SeniorityTier, MasteryStatus


def test_dynamic_graph_edge_wiring():
    print("\n--- Test 1: Dynamic Pillar Graph Construction & Topology ---")
    mock_matched_pillars = [
        {"pillar_id": "ASYNC_CONCURRENCY", "name": "Real-Time Streaming & Concurrency"},
        {"pillar_id": "EVENT_STREAMING_MESSAGING", "name": "Event-Driven Architecture & Message Queues"},
        {"pillar_id": "DISTRIBUTED_CACHING", "name": "Distributed Caching & Invalidation"}
    ]

    graph = build_dynamic_pillar_graph(mock_matched_pillars, seniority=SeniorityTier.MID)
    print(f"Registered Nodes: {list(graph.nodes.keys())}")
    print(f"Total Edges Wired: {len(graph.edges)}")

    # Verify all 3 nodes registered
    assert set(graph.nodes.keys()) == {"ASYNC_CONCURRENCY", "EVENT_STREAMING_MESSAGING", "DISTRIBUTED_CACHING"}
    
    # Verify directed prerequisite edge: ASYNC_CONCURRENCY -> EVENT_STREAMING_MESSAGING
    has_prereq = any(
        e.from_skill == "ASYNC_CONCURRENCY" and e.to_skill == "EVENT_STREAMING_MESSAGING" and e.edge_type == EdgeType.PREREQUISITE
        for e in graph.edges
    )
    assert has_prereq, "Expected PREREQUISITE edge from ASYNC_CONCURRENCY to EVENT_STREAMING_MESSAGING"
    print("[PASS] Verified dynamic ontology prerequisite edge generation.")


def test_prerequisite_gating_and_propagation():
    print("\n--- Test 2: Prerequisite Gating & Mastery Propagation ---")
    mock_matched_pillars = [
        {"pillar_id": "DATA_STRUCTURES_ALGORITHMS", "name": "Data Structures & Algorithms"},
        {"pillar_id": "DISTRIBUTED_CACHING", "name": "Distributed Caching & Invalidation"}
    ]
    graph = build_dynamic_pillar_graph(mock_matched_pillars, seniority=SeniorityTier.MID)

    # Initial state: DATA_STRUCTURES_ALGORITHMS is prior=0.40 (< 0.50)
    is_ready, missing = graph.get_prerequisite_readiness("DISTRIBUTED_CACHING")
    print(f"Is DISTRIBUTED_CACHING ready initially? {is_ready} (Missing: {missing})")
    assert not is_ready, "DISTRIBUTED_CACHING should be blocked by unmastered DATA_STRUCTURES_ALGORITHMS"
    assert "DATA_STRUCTURES_ALGORITHMS" in missing

    # Candidate masters DATA_STRUCTURES_ALGORITHMS
    ds_node = graph.nodes["DATA_STRUCTURES_ALGORITHMS"]
    ds_node.p_l = 0.92  # Automatically sets status to MASTERED (>=0.85)

    # Check readiness again
    is_ready_now, missing_now = graph.get_prerequisite_readiness("DISTRIBUTED_CACHING")
    assert is_ready_now, "DISTRIBUTED_CACHING should now be unlocked"
    print("[PASS] Prerequisite gating successfully held and unlocked on mastery.")

    # Test Message Passing
    cache_prior_before = graph.nodes["DISTRIBUTED_CACHING"].p_l
    boosts = graph.propagate_mastery("DATA_STRUCTURES_ALGORITHMS")
    cache_prior_after = graph.nodes["DISTRIBUTED_CACHING"].p_l
    print(f"DISTRIBUTED_CACHING Prior: {cache_prior_before} -> {cache_prior_after} (Boosts: {boosts})")
    assert cache_prior_after > cache_prior_before
    print("[PASS] Graph message passing boosted downstream child node.")


def test_next_skill_routing():
    print("\n--- Test 3: Graph Information-Entropy Next Skill Routing ---")
    mock_matched_pillars = [
        {"pillar_id": "ASYNC_CONCURRENCY", "name": "Concurrency"},
        {"pillar_id": "EVENT_STREAMING_MESSAGING", "name": "Messaging"}
    ]
    graph = build_dynamic_pillar_graph(mock_matched_pillars, seniority=SeniorityTier.MID)

    # Initial choice should be ASYNC_CONCURRENCY since EVENT_STREAMING_MESSAGING is gated
    next_s = graph.get_next_recommended_skill()
    print(f"First recommended skill: {next_s}")
    assert next_s == "ASYNC_CONCURRENCY"

    # Mark ASYNC_CONCURRENCY as completed
    graph.nodes["ASYNC_CONCURRENCY"].p_l = 0.88

    # Now EVENT_STREAMING_MESSAGING should be selected
    next_s2 = graph.get_next_recommended_skill()
    print(f"Second recommended skill: {next_s2}")
    assert next_s2 == "EVENT_STREAMING_MESSAGING"

    # Mark EVENT_STREAMING_MESSAGING completed
    graph.nodes["EVENT_STREAMING_MESSAGING"].p_l = 0.88

    # Graph should conclude with None
    final_s = graph.get_next_recommended_skill()
    assert final_s is None
    print("[PASS] KnowledgeGraph route navigation completed all topics cleanly.")


if __name__ == "__main__":
    test_dynamic_graph_edge_wiring()
    test_prerequisite_gating_and_propagation()
    test_next_skill_routing()
    print("\n========================================================")
    print("ALL DYNAMIC GRAPH DEPENDENCY ROUTING TESTS PASSED (3/3)!")
    print("========================================================")
