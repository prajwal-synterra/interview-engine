"""
Phase 3 Demo: Testing the Policy Router Finite State Machine (FSM)
Tests:
1. Scaffolding Ladder Progression (L0 -> L1 -> L2 -> L3 -> Concede topic)
2. Successful Turn Progression & Topic Mastery Advance
3. Devil's Advocate Trigger on Mastery Surge
4. Devil's Advocate Defense: PASS (Mastery Confirmed >= 0.90) vs FAIL (Mastery Collapsed <= 0.20)
"""

import sys
import os

# Add root folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.bkt_engine import SeniorityTier
from app.policy_router import PolicyRouter, SessionState


def print_header(title: str):
    print("\n" + "=" * 75)
    print(f"  {title}")
    print("=" * 75)


def test_scaffolding_ladder():
    print_header("TEST 1: Scaffolding Ladder Progression (Repeated Failures)")
    router = PolicyRouter(seniority=SeniorityTier.MID)

    mock_pillars = [
        {"pillar_id": "ASYNC_CONCURRENCY", "name": "Async & Concurrency"},
        {"pillar_id": "DISTRIBUTED_CACHING", "name": "Distributed Caching"},
    ]
    directive = router.initialize_session(mock_pillars)
    print(f"Session Initialized -> State: {directive.current_state.value} | Active Skill: {directive.skill_code}\n")

    # Candidate makes 4 consecutive errors to test L1 -> L2 -> L3 -> Topic Conceded
    turns = [
        ("Candidate struggles on L0 open-ended", 0),
        ("Candidate struggles on L1 nudge", 0),
        ("Candidate struggles on L2 scenario skeleton", 0),
        ("Candidate fails L3 binary choice", 0),
    ]

    for desc, obs in turns:
        res = router.process_turn(observation=obs)
        print(f"Event: {desc}")
        print(f"  -> State:             {res.current_state.value}")
        print(f"  -> Next Action:       {res.next_action}")
        print(f"  -> Scaffolding Level: {res.scaffolding_level}")
        print(f"  -> Skill Code:        {res.skill_code}")
        print(f"  -> Alex Directive:    \"{res.prompt_directive[:70]}...\"\n")


def test_deepen_and_mastery():
    print_header("TEST 2: Deepening Exploration & Mastery Progression")
    router = PolicyRouter(seniority=SeniorityTier.MID)

    mock_pillars = [
        {"pillar_id": "API_DESIGN_PROTOCOLS", "name": "API Design & Protocols"},
        {"pillar_id": "DISTRIBUTED_CACHING", "name": "Distributed Caching"},
    ]
    router.initialize_session(mock_pillars)
    print(f"Start Skill: {router.current_skill} | Initial Mastery: {router.graph.nodes[router.current_skill].p_l:.2f}\n")

    # Turn 1: Correct answer (not yet mastered) -> should DEEPEN_EXPLORATION
    d1 = router.process_turn(observation=1)
    print(f"Turn 1 Correct -> Action: {d1.next_action} | State: {d1.current_state.value} | P(L): {d1.current_mastery:.4f}")
    print(f"Directive: \"{d1.prompt_directive}\"\n")

    # Turn 2: Second correct answer -> crosses mastery threshold -> should NEXT_SKILL
    d2 = router.process_turn(observation=1)
    print(f"Turn 2 Correct -> Action: {d2.next_action} | State: {d2.current_state.value} | P(L): {d2.current_mastery:.4f}")
    print(f"Directive: \"{d2.prompt_directive}\"")


def test_devils_advocate_defense():
    print_header("TEST 3: Devil's Advocate Protocol (Surge, Pass & Fail)")

    # --- Scenario A: Candidate PASSES Devil's Advocate ---
    print("\n--- Sub-test A: Candidate PASSES Devil's Advocate Challenge ---")
    router_pass = PolicyRouter(seniority=SeniorityTier.JUNIOR)
    mock_pillars = [
        {"pillar_id": "DISTRIBUTED_SYSTEMS", "name": "Distributed Systems"},
        {"pillar_id": "API_DESIGN_PROTOCOLS", "name": "API Design"},
    ]
    router_pass.initialize_session(mock_pillars)

    # Force a surge by giving correct on open-ended as Junior
    surge_d = router_pass.process_turn(observation=1)
    print(f"Turn 1 -> Action: {surge_d.next_action} | State: {surge_d.current_state.value}")
    print(f"Directive: \"{surge_d.prompt_directive[:80]}...\"\n")

    # Now simulate candidate successfully defending Devil's Advocate (observation = 1)
    defense_pass = router_pass.process_turn(observation=1)
    print(f"Turn 2 (DA Defended successfully!) -> Action: {defense_pass.next_action}")
    print(f"New Skill: {defense_pass.skill_code} | Resulting Mastery of Prior Skill: {router_pass.graph.nodes['DISTRIBUTED_SYSTEMS'].p_l:.4f}")
    print(f"Passed DA Boost Confirmed: {router_pass.graph.nodes['DISTRIBUTED_SYSTEMS'].p_l >= 0.90}")

    # --- Scenario B: Candidate FAILS Devil's Advocate ---
    print("\n--- Sub-test B: Candidate FAILS Devil's Advocate Challenge ---")
    router_fail = PolicyRouter(seniority=SeniorityTier.JUNIOR)
    router_fail.initialize_session(mock_pillars)

    # Force surge
    router_fail.process_turn(observation=1)

    # Simulate candidate failing Devil's Advocate probe (observation = 0)
    defense_fail = router_fail.process_turn(observation=0)
    print(f"Turn 2 (DA Failed / Bluffed!) -> Action: {defense_fail.next_action}")
    print(f"New Skill: {defense_fail.skill_code} | Resulting Mastery of Prior Skill: {router_fail.graph.nodes['DISTRIBUTED_SYSTEMS'].p_l:.4f}")
    print(f"Failed DA Collapse Confirmed: {router_fail.graph.nodes['DISTRIBUTED_SYSTEMS'].p_l <= 0.20}")


if __name__ == "__main__":
    test_scaffolding_ladder()
    test_deepen_and_mastery()
    test_devils_advocate_defense()
