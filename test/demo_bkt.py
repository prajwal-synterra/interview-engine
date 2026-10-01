"""
Phase 1 Demo: Testing the BKT Engine
Simulates 5 test scenarios:
1. Standard Turn Progression (Correct -> Incorrect -> Incorrect -> Correct -> Correct)
2. Scaffolding Decay (Comparing delta gains across levels 0, 1, 2, 3)
3. Seniority Priors (Student vs Junior vs Mid vs Senior Staff)
4. Dynamic Slip Floor (Consecutive errors protection)
5. Surge Detection (Devil's Advocate trigger)
"""

import sys
import os

# Add root folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.bkt_engine import BKTNode, SeniorityTier, MasteryStatus


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_standard_turns():
    print_header("TEST 1: Standard Turn Progression (MID Tier)")
    node = BKTNode(skill_code="ASYNC_CONCURRENCY", seniority=SeniorityTier.MID)
    print(f"Initial Prior P(L0): {node.p_l:.4f} | Initial Status: {node.status.value}\n")

    turns = [
        (1, 0, "Turn 1: Correct (open-ended)"),
        (0, 0, "Turn 2: Incorrect (open-ended)"),
        (0, 0, "Turn 3: Incorrect (open-ended)"),
        (1, 0, "Turn 4: Correct (open-ended)"),
        (1, 0, "Turn 5: Correct (open-ended)"),
    ]

    for obs, scaffold, desc in turns:
        res = node.update(observation=obs, scaffolding_level=scaffold)
        print(
            f"{desc:35} -> Prior: {res['prior_mastery']:.4f} | "
            f"Now: {res['current_mastery']:.4f} | "
            f"Delta: {res['delta']:+.4f} | Status: {res['status']}"
        )


def test_scaffolding_decay():
    print_header("TEST 2: Anti-Coaching Scaffolding Decay")
    print("All start at MID prior P(L0)=0.45 and answer Correct (1), but with different hints:\n")

    scenarios = [
        (0, "Level 0: No Hint (Open-ended)"),
        (1, "Level 1: Minimal Nudge"),
        (2, "Level 2: Structured Hint"),
        (3, "Level 3: Direct Trade-off / Choice"),
    ]

    for level, desc in scenarios:
        node = BKTNode(skill_code="ASYNC_CONCURRENCY", seniority=SeniorityTier.MID)
        res = node.update(observation=1, scaffolding_level=level)
        print(f"{desc:38} -> Mastery: {res['current_mastery']:.4f} | Gain Delta: {res['delta']:+.4f}")


def test_seniority_priors():
    print_header("TEST 3: Seniority Tier Calibrations")
    for tier in [SeniorityTier.STUDENT, SeniorityTier.JUNIOR, SeniorityTier.MID, SeniorityTier.SENIOR_STAFF]:
        node = BKTNode(skill_code="DISTRIBUTED_SYSTEMS", seniority=tier)
        print(f"Tier: {tier.value:<12} -> Starting P(L0): {node.p_l:.2f}")


def test_dynamic_slip_floor():
    print_header("TEST 4: Dynamic Slip Floor Protection")
    print("Repeated incorrect answers must increase slip floor P(S), preventing false 'slips':\n")

    node = BKTNode(skill_code="DISTRIBUTED_SYSTEMS", seniority=SeniorityTier.MID)
    for i in range(1, 5):
        res = node.update(observation=0, scaffolding_level=0)
        print(
            f"Error #{i} -> Slip Used: {res['slip_used']:.2f} | "
            f"Mastery: {res['prior_mastery']:.4f} -> {res['current_mastery']:.4f} | "
            f"Status: {res['status']}"
        )


def test_surge_detection():
    print_header("TEST 5: Surge Detection (Devil's Advocate Trigger)")
    node = BKTNode(skill_code="DISTRIBUTED_SYSTEMS", seniority=SeniorityTier.JUNIOR)
    print(f"Junior Starting Prior: {node.p_l:.2f}\n")

    r1 = node.update(observation=1, scaffolding_level=0)
    print(f"Turn 1: P(L) = {r1['current_mastery']:.4f} | Delta = {r1['delta']:+.4f} | Surge Triggered: {r1['is_surge']}")

    r2 = node.update(observation=1, scaffolding_level=0)
    print(f"Turn 2: P(L) = {r2['current_mastery']:.4f} | Delta = {r2['delta']:+.4f} | Surge Triggered: {r2['is_surge']}")


if __name__ == "__main__":
    test_standard_turns()
    test_scaffolding_decay()
    test_seniority_priors()
    test_dynamic_slip_floor()
    test_surge_detection()
