"""
Verification Test Suite for MIRT Engine.
Tests:
1. Probability prediction based on discrimination vector and difficulty scalar.
2. Continuous ability scaling: candidate tackling increasingly hard questions without limits.
3. Fisher Information optimization: finding questions that probe right at the candidate's edge.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.mirt_engine import MIRTEngine, ItemParameters


def test_mirt_prediction_and_gradient_update():
    print("\n--- Test 1: MIRT Probability & Ability Updates ---")
    engine = MIRTEngine()
    print(f"Starting Baseline Theta: {engine.theta}")

    # Create a medium distributed systems question (b = 0.5)
    q1 = ItemParameters(
        item_id="q_consensus_1",
        prompt="Explain leader election in Raft.",
        difficulty=0.5,
        discrimination={"distributed_systems": 1.2, "concurrency": 0.6}
    )

    p_initial = engine.predict_probability(q1)
    print(f"Predicted P(correct) at baseline theta (0.0): {p_initial:.4f}")

    # Candidate answers with high competence (observation = 1)
    est = engine.update_ability(q1, observation=1)
    print(f"Updated Theta after correct answer: {est.theta}")

    assert est.theta["distributed_systems"] > 0.0
    assert est.theta["concurrency"] > 0.0
    print("[PASS] Ability vector updated accurately via multidimensional gradient.")


def test_continuous_scaling_without_limits():
    print("\n--- Test 2: Continuous Scaling Beyond Limits (Discovering Ceiling) ---")
    engine = MIRTEngine()

    # We throw progressively harder questions up to staff frontier (+3.0)
    difficulties = [0.0, 1.0, 2.0, 3.0]
    for b in difficulties:
        item = ItemParameters(
            item_id=f"q_deep_dive_b{b}",
            prompt=f"Frontier distributed question at difficulty {b}",
            difficulty=b,
            discrimination={"distributed_systems": 1.5, "system_design": 1.0}
        )
        # Student aces each one!
        engine.update_ability(item, observation=1)
        print(f"Passed difficulty b={b:.1f} -> New Distributed Theta: {engine.theta['distributed_systems']:.4f}")

    final_theta = engine.theta["distributed_systems"]
    print(f"Final Frontier Ability Theta: {final_theta:.4f}")
    assert final_theta > 1.4
    print("[PASS] Engine seamlessly scaled candidate into senior/staff ability tier without artificial limits!")


def test_fisher_information_question_selection():
    print("\n--- Test 3: Fisher Information Maximization ---")
    # Candidate with known advanced ability in system_design (+1.8)
    engine = MIRTEngine(initial_theta={"system_design": 1.8, "algorithms": 0.0, "concurrency": 0.0, "databases": 0.0, "distributed_systems": 0.0})

    # Question pool with varied difficulties
    pool = [
        ItemParameters("easy", "Basic API question", difficulty=-1.5, discrimination={"system_design": 1.0}),
        ItemParameters("medium", "Load balancer question", difficulty=0.0, discrimination={"system_design": 1.0}),
        ItemParameters("frontier", "Multi-region sharded cache coherence", difficulty=1.8, discrimination={"system_design": 1.0}),
    ]

    best_item = engine.select_highest_information_item(pool)
    print(f"Selected item: '{best_item.item_id}' (Difficulty: {best_item.difficulty}) for candidate theta=1.8")

    assert best_item.item_id == "frontier"
    print("[PASS] Correctly matched question difficulty to candidate's exact ability edge.")


if __name__ == "__main__":
    test_mirt_prediction_and_gradient_update()
    test_continuous_scaling_without_limits()
    test_fisher_information_question_selection()
    print("\n==========================================")
    print("ALL MIRT ABILITY TESTS PASSED (3/3)!")
    print("==========================================")
