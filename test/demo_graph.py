"""
Phase 2 Demo: Testing the Knowledge Graph (HHGKT) Engine
Tests:
1. Graph Construction & Dependency Wiring
2. Prerequisite Gating (Preventing advanced questions before fundamentals)
3. Active Information Gain (Recommending optimal next skill)
4. Mastery Propagation / Message Passing (Downstream boost)
"""

import sys
import os

# Add root folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.bkt_engine import SeniorityTier, MasteryStatus
from app.graph_engine import KnowledgeGraph, EdgeType, build_dynamic_pillar_graph


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_prerequisite_gating():
    print_header("TEST 1: Prerequisite Gating")
    graph = KnowledgeGraph(seniority=SeniorityTier.MID)

    # Register 2 skills: Foundational -> Advanced
    graph.add_skill("DATA_STRUCTURES_ALGORITHMS", custom_prior=0.30)
    graph.add_skill("DISTRIBUTED_CACHING", custom_prior=0.45)

    # Add prerequisite: DSA is required for Caching (weight 0.75)
    graph.add_dependency(
        from_skill="DATA_STRUCTURES_ALGORITHMS",
        to_skill="DISTRIBUTED_CACHING",
        edge_type=EdgeType.PREREQUISITE,
        weight=0.75
    )

    print(f"Foundational DSA Prior: {graph.nodes['DATA_STRUCTURES_ALGORITHMS'].p_l:.2f}")
    print(f"Advanced Caching Prior: {graph.nodes['DISTRIBUTED_CACHING'].p_l:.2f}\n")

    # Check readiness of DISTRIBUTED_CACHING while DSA is weak (<0.50)
    is_ready, missing = graph.get_prerequisite_readiness("DISTRIBUTED_CACHING")
    print(f"Can we ask about DISTRIBUTED_CACHING now? -> {is_ready}")
    print(f"Missing Prerequisite(s): {missing}")

    # Now simulate candidate demonstrating DSA mastery
    print("\n... Candidate passes DSA questions (P(L) goes to 0.85) ...")
    graph.nodes["DATA_STRUCTURES_ALGORITHMS"].p_l = 0.85

    is_ready, missing = graph.get_prerequisite_readiness("DISTRIBUTED_CACHING")
    print(f"Can we ask about DISTRIBUTED_CACHING now? -> {is_ready}")
    print(f"Missing Prerequisite(s): {missing} (Gate UNLOCKED!)")


def test_mastery_propagation():
    print_header("TEST 2: Mastery Propagation (Message Passing)")
    graph = KnowledgeGraph(seniority=SeniorityTier.MID)

    # Register skills
    graph.add_skill("DATA_STRUCTURES_ALGORITHMS", custom_prior=0.50)
    graph.add_skill("DISTRIBUTED_CACHING", custom_prior=0.40)
    graph.add_skill("DATABASE_MODELING_TRANSACTIONS", custom_prior=0.40)

    # Connect DSA to both
    graph.add_dependency("DATA_STRUCTURES_ALGORITHMS", "DISTRIBUTED_CACHING", EdgeType.PREREQUISITE, weight=0.75)
    graph.add_dependency("DATA_STRUCTURES_ALGORITHMS", "DATABASE_MODELING_TRANSACTIONS", EdgeType.PREREQUISITE, weight=0.70)

    print(f"Before Propagation:")
    print(f"  DISTRIBUTED_CACHING prior:           {graph.nodes['DISTRIBUTED_CACHING'].p_l:.4f}")
    print(f"  DATABASE_MODELING_TRANSACTIONS prior: {graph.nodes['DATABASE_MODELING_TRANSACTIONS'].p_l:.4f}")

    # Simulate mastering DSA (P(L) = 0.90)
    print("\nCandidate achieves P(L) = 0.90 in DSA! Triggering propagate_mastery()...")
    graph.nodes["DATA_STRUCTURES_ALGORITHMS"].p_l = 0.90
    updates = graph.propagate_mastery("DATA_STRUCTURES_ALGORITHMS")

    print(f"\nAfter Propagation (Downstream Boost):")
    for skill, new_p in updates.items():
        print(f"  {skill:35} -> New Prior: {new_p:.4f}")


def test_next_skill_recommendation():
    print_header("TEST 3: Active Information Gain (Next Skill Recommendation)")
    print("Graph picks the IN_PROGRESS skill with valid prerequisites closest to P(L)=0.50:")
    graph = KnowledgeGraph(seniority=SeniorityTier.MID)

    # Skill A is already near mastery (0.80) -> Low uncertainty (we already know they're good)
    graph.add_skill("API_DESIGN_PROTOCOLS", custom_prior=0.80)

    # Skill B is in the high uncertainty zone (0.48) -> Max information gain!
    graph.add_skill("ASYNC_CONCURRENCY", custom_prior=0.48)

    # Skill C is advanced, but prerequisite unmet
    graph.add_skill("EVENT_STREAMING_MESSAGING", custom_prior=0.50)
    graph.add_dependency("ASYNC_CONCURRENCY", "EVENT_STREAMING_MESSAGING", EdgeType.PREREQUISITE, weight=0.80)

    recommended = graph.get_next_recommended_skill()
    print(f"  API_DESIGN_PROTOCOLS:      P(L) = 0.80 (Uncertainty: {1.0 - abs(0.80 - 0.50):.2f})")
    print(f"  ASYNC_CONCURRENCY:         P(L) = 0.48 (Uncertainty: {1.0 - abs(0.48 - 0.50):.2f})")
    print(f"  EVENT_STREAMING_MESSAGING: P(L) = 0.50 (Prerequisite ASYNC not satisfied yet)")
    print(f"\n>> Optimal Next Skill Selected by Engine: '{recommended}'")


def test_dynamic_pillar_builder():
    print_header("TEST 4: Dynamic Session Graph Builder")
    # Simulate vector search matching 3 candidate pillars from their introduction
    mock_matched_pillars = [
        {"pillar_id": "API_DESIGN_PROTOCOLS", "name": "API Design & Protocols"},
        {"pillar_id": "ASYNC_CONCURRENCY", "name": "Async & Concurrency"},
        {"pillar_id": "EVENT_STREAMING_MESSAGING", "name": "Event Streaming"},
    ]

    graph = build_dynamic_pillar_graph(mock_matched_pillars, seniority=SeniorityTier.MID)
    print(f"Dynamically registered {len(graph.nodes)} nodes:")
    for code, node in graph.nodes.items():
        print(f"  Node: {code:<30} | Initial Prior: {node.p_l:.2f}")

    print(f"\nAuto-wired {len(graph.edges)} dependency edges:")
    for edge in graph.edges:
        print(f"  [{edge.from_skill}] --({edge.edge_type.value}, w={edge.weight})--> [{edge.to_skill}]")


if __name__ == "__main__":
    test_prerequisite_gating()
    test_mastery_propagation()
    test_next_skill_recommendation()
    test_dynamic_pillar_builder()
