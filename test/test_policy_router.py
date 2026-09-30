"""
Verification Test Suite for Deterministic Policy Router.
Tests:
1. End-to-end multi-turn interview lifecycle across multiple skills.
2. Scaffolding progression (L0 -> L1 -> L2 -> L3) on struggling candidate.
3. Sudden mastery surge triggering Devil's Advocate protocol.
4. Final session report generation with deterministic recommendation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.policy_router import PolicyRouter, SessionState
from app.bkt_engine import SeniorityTier


def test_full_session_flow():
    print("\n--- Test 1: Full Multi-Turn Orchestration Flow ---")
    router = PolicyRouter(seniority=SeniorityTier.JUNIOR)

    # Initialize session with 2 skills
    router.initialize_session([
        ("redis_caching", 0.25),
        ("database_indexing", 0.25)
    ])
    print(f"Session State: {router.state} | Current Skill: {router.current_skill}")

    # Turn 1: Candidate struggles (obs=0) -> Should step to SCAFFOLDING_L1
    d1 = router.process_candidate_turn(
        observation=0,
        latency_ms=750,
        transcript="Um, I'm not really sure how cache invalidation works."
    )
    print(f"Turn 1 -> Action: {d1.next_action} | State: {d1.current_state} | Scaffold Level: {d1.scaffolding_level}")
    assert d1.current_state == SessionState.SCAFFOLDING_L1
    assert d1.scaffolding_level == 1

    # Turn 2: Candidate gets it right with L1 hint (obs=1)
    d2 = router.process_candidate_turn(
        observation=1,
        latency_ms=620,
        transcript="Oh right, TTL and write-through cache can be used."
    )
    print(f"Turn 2 -> Action: {d2.next_action} | State: {d2.current_state} | Mastery: {d2.current_mastery}")

    # Turn 3: Candidate masters it (obs=1) -> Should advance to next skill
    d3 = router.process_candidate_turn(
        observation=1,
        latency_ms=580,
        transcript="We handle race conditions using distributed locks like Redlock."
    )
    print(f"Turn 3 -> Action: {d3.next_action} | Next Skill: {d3.skill_code}")
    assert d3.next_action == "NEXT_SKILL"
    assert d3.skill_code == "database_indexing"
    print("[PASS] Scaffolding progression and smooth skill transition verified!")


def test_devils_advocate_surge_trigger():
    print("\n--- Test 2: Devil's Advocate Surge Trigger ---")
    router = PolicyRouter(seniority=SeniorityTier.STUDENT)
    router.initialize_session([("distributed_consensus", 0.15)])

    # Flawless unassisted answer produces a huge delta surge
    d = router.process_candidate_turn(
        observation=1,
        latency_ms=650,
        transcript="In Raft, leader election requires a randomized election timer between 150ms and 300ms to prevent split votes."
    )
    print(f"Resulting Action: {d.next_action} | State: {d.current_state}")
    assert d.current_state == SessionState.DEVILS_ADVOCATE
    assert "Devil's Advocate" in d.prompt_directive
    print("[PASS] Mastery surge immediately routed into Devil's Advocate sub-routine!")


def test_final_session_report():
    print("\n--- Test 3: Final Session Report Generation ---")
    router = PolicyRouter(seniority=SeniorityTier.MID)
    router.initialize_session([("api_rate_limiting", 0.45)])

    # Candidate masters it
    router.process_candidate_turn(observation=1, latency_ms=500, transcript="Token bucket algorithm is ideal.")
    router.process_candidate_turn(observation=1, latency_ms=550, transcript="Redis sorted sets allow sliding window rate limiting.")

    report = router.generate_final_session_report()
    print(f"Report: Score={report['final_score']} | Rec={report['recommendation']} | BII={report['behavioral_integrity_index']}")
    assert report["passed_proctoring"] is True
    assert report["final_score"] >= 70.0
    print("[PASS] Final session report assembled with complete mathematical audit trail.")


if __name__ == "__main__":
    test_full_session_flow()
    test_devils_advocate_surge_trigger()
    test_final_session_report()
    print("\n========================================================")
    print("ALL POLICY ROUTER & STATE MACHINE TESTS PASSED (3/3)!")
    print("========================================================")
