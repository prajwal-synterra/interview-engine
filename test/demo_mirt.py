"""
Phase 4 Demo: Testing the Multidimensional Item Response Theory (MIRT) Engine
Tests:
1. Baseline Ability (0.0 -> 50th Percentile / Mid-Level Professional)
2. Multi-turn Online Ability Updates across diverse technical domains
3. Difficulty Sensitivity (Answering hard questions earns more theta)
4. Generating the Final 5D Executive Radar Profile
"""

import sys
import os

# Add root folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.mirt_engine import MIRTEngine, ItemParameters, get_radar_summary, theta_to_percentile


def print_header(title: str):
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


def test_baseline_theta():
    print_header("TEST 1: Baseline Ability Calibration (Mid-Level Baseline)")
    mirt = MIRTEngine()
    print("Initial 5D Ability Vector (theta=0.0 represents 50th percentile):\n")
    for dim, th in mirt.theta.items():
        pct = theta_to_percentile(th)
        print(f"  {dim:<22} -> theta: {th:+.2f} | Percentile: {pct}% | Error: {mirt.std_error[dim]:.2f}")


def test_multi_turn_simulation():
    print_header("TEST 2: Candidate Evaluation Simulation (5 Distinct Turns)")
    mirt = MIRTEngine()

    turns = [
        ("ASYNC_CONCURRENCY", 0.5, 1, "Turn 1: Solves async event-loop question (difficulty +0.5)"),
        ("ASYNC_CONCURRENCY", 1.2, 1, "Turn 2: Solves lock-free queue concurrency problem (difficulty +1.2)"),
        ("DISTRIBUTED_CACHING", 1.0, 1, "Turn 3: Correctly designs cache invalidation & stampede (difficulty +1.0)"),
        ("DATA_STRUCTURES_ALGORITHMS", 1.8, 0, "Turn 4: Struggles on complex graph cycle algorithm (difficulty +1.8)"),
        ("DATABASE_MODELING_TRANSACTIONS", 0.8, 1, "Turn 5: Strong answer on 2PC vs Saga transactions (difficulty +0.8)"),
    ]

    for skill, diff, obs, desc in turns:
        res = mirt.update_ability(skill=skill, difficulty=diff, observation=obs)
        last = mirt.history[-1]
        print(f"{desc}")
        print(f"  -> Predicted P(correct): {last['p_predicted']:.2f} | Observed: {obs} | Residual: {last['residual']:+.2f}")
        print(f"  -> Concurrency theta:    {res.theta['concurrency']:+.2f} (err: {res.standard_error['concurrency']:.2f})")
        print(f"  -> Distributed theta:    {res.theta['distributed_systems']:+.2f}")
        print(f"  -> Algorithms theta:     {res.theta['algorithms']:+.2f}\n")


def test_radar_summary():
    print_header("TEST 3: Final 5D Executive Radar Profile")
    mirt = MIRTEngine()

    # Simulate strong senior engineer in distributed systems & concurrency
    mirt.update_ability(skill="DISTRIBUTED_CACHING", difficulty=1.5, observation=1)
    mirt.update_ability(skill="EVENT_STREAMING_MESSAGING", difficulty=1.5, observation=1)
    mirt.update_ability(skill="ASYNC_CONCURRENCY", difficulty=1.2, observation=1)
    mirt.update_ability(skill="DATABASE_MODELING_TRANSACTIONS", difficulty=1.0, observation=1)
    mirt.update_ability(skill="DATA_STRUCTURES_ALGORITHMS", difficulty=0.5, observation=1)

    radar = get_radar_summary(mirt)
    print(f"{'Dimension':<40} {'Theta':<8} {'Percentile':<12} {'Seniority Tier'}")
    print("-" * 78)
    for row in radar:
        print(f"{row['dimension']:<40} {row['theta']:<8.2f} {row['percentile']:>5.1f}%      {row['tier']}")


if __name__ == "__main__":
    test_baseline_theta()
    test_multi_turn_simulation()
    test_radar_summary()
