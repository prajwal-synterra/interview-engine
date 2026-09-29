"""
Verification Test Suite for BKT Engine.
Tests:
1. Student mastering a topic organically.
2. Candidate struggling and hitting the Slip Floor & Deficiency threshold.
3. Scaffolding decay: Level 3 assistance awards strictly less delta than Level 0.
4. Sudden surge detection triggering Devil's Advocate.
"""

from app.bkt_engine import BKTNode, SeniorityTier, MasteryStatus


def test_organic_mastery():
    print("\n--- Test 1: Organic Mastery (Junior) ---")
    node = BKTNode(skill_code="redis_caching", seniority=SeniorityTier.JUNIOR)
    print(f"Initial Prior P(L0): {node.p_l:.4f}")

    # Candidate answers correctly twice with zero scaffolding
    r1 = node.update(observation=1, scaffolding_level=0)
    print(f"Step 1 (Correct, L0): Mastery -> {r1['current_mastery']} (Delta: +{r1['delta']})")

    r2 = node.update(observation=1, scaffolding_level=0)
    print(f"Step 2 (Correct, L0): Mastery -> {r2['current_mastery']} (Delta: +{r2['delta']}) | Status: {r2['status']}")

    assert r2["current_mastery"] >= 0.85
    assert node.status == MasteryStatus.MASTERED
    print("[PASS] Organic Mastery successfully reached threshold.")


def test_scaffolding_decay():
    print("\n--- Test 2: Scaffolding Decay (Anti-Coaching) ---")
    node_unassisted = BKTNode(skill_code="distributed_locks", seniority=SeniorityTier.STUDENT)
    node_assisted = BKTNode(skill_code="distributed_locks", seniority=SeniorityTier.STUDENT)

    # Both start at same prior
    assert node_unassisted.p_l == node_assisted.p_l

    # Both answer correctly, but one had Level 3 (binary choice) assistance
    r_unassisted = node_unassisted.update(observation=1, scaffolding_level=0)
    r_assisted = node_assisted.update(observation=1, scaffolding_level=3)

    print(f"Level 0 (Unassisted) Gain: +{r_unassisted['delta']} (Final: {r_unassisted['current_mastery']})")
    print(f"Level 3 (Max Assisted) Gain: +{r_assisted['delta']} (Final: {r_assisted['current_mastery']})")

    assert r_assisted["delta"] < r_unassisted["delta"]
    print(f"[PASS] Anti-coaching successfully penalized heavy scaffolding assistance.")


def test_slip_floor_and_deficiency():
    print("\n--- Test 3: Slip Floor & Deficiency Collapse ---")
    node = BKTNode(skill_code="concurrency_primitives", seniority=SeniorityTier.MID)
    print(f"Initial Prior P(L0): {node.p_l:.4f}")

    # Candidate fails 3 times consecutively
    for i in range(3):
        res = node.update(observation=0, scaffolding_level=i)
        print(f"Step {res['step']} (Wrong, L{i}): Mastery -> {res['current_mastery']} | Slip Used: {res['slip_used']}")

    assert res["slip_used"] <= node.config.s_max
    assert node.status == MasteryStatus.UNMASTERED
    print(f"[PASS] Slip Floor held at max {node.config.s_max}, skill correctly marked UNMASTERED.")


def test_surge_detection_for_devils_advocate():
    print("\n--- Test 4: Mastery Surge Trigger (Devil's Advocate) ---")
    node = BKTNode(skill_code="consensus_raft", seniority=SeniorityTier.STUDENT)
    
    # Candidate starts as Student (0.15) and immediately answers a flawless L0 question
    res = node.update(observation=1, scaffolding_level=0)
    print(f"Step 1: Prior: {res['prior_mastery']} -> Mastery: {res['current_mastery']} | Delta: +{res['delta']} | Surge: {res['is_surge']}")

    assert res["is_surge"] is True
    print("[PASS] Mastery Surge correctly triggered for Devil's Advocate sub-routine!")


if __name__ == "__main__":
    test_organic_mastery()
    test_scaffolding_decay()
    test_slip_floor_and_deficiency()
    test_surge_detection_for_devils_advocate()
    print("\n==========================================")
    print("ALL BKT & SCAFFOLDING TESTS PASSED (4/4)!")
    print("==========================================")
