"""
Policy & Orchestration Engine
Reference: AIS-ARCH-2026-V1 Section 2.3 & Report 2
Deterministic rules for depth escalation, Devil's Advocate triggers, and exit criteria.
"""

from dataclasses import dataclass
from typing import Literal

SkillState = Literal["IN_PROGRESS", "VERIFIED", "SHALLOW"]
PolicyAction = Literal[
    "CONTINUE_SAME_LEVEL",
    "ESCALATE_DEPTH",
    "TRIGGER_DEVILS_ADVOCATE",
    "EXIT_VERIFIED",
    "EXIT_SHALLOW",
]

DEPTH_HIERARCHY = ["L1", "L2", "L3", "L4"]
MAX_ATTEMPTS_PER_SKILL = 4
MASTERY_VERIFICATION_THRESHOLD = 0.85


@dataclass
class PolicyDecision:
    action: PolicyAction
    next_depth: str
    state: SkillState
    is_devils_advocate: bool
    reason: str


def check_devils_advocate_trigger(
    depth_level: str,
    prior: float,
    next_mastery: float,
    has_faced_da: bool,
    attempts: int = 1
) -> bool:
    """
    Evaluates Devil's Advocate trigger conditions:
    1. Candidate has not already faced Devil's Advocate in this session.
    2. Triggered if EITHER:
       a) Depth level is L3 or L4 with steep surge (Delta >= 0.20) or near exit (Mastery >= 0.85)
       b) Candidate reached Mastery >= 0.85 at L2 (or attempt 4) and has not defended DA yet.
          Guarantees high-scoring candidates get a fair trade-off challenge rather than being branded Shallow!
    """
    if has_faced_da:
        return False

    delta = next_mastery - prior
    is_steep_surge = delta >= 0.20
    is_near_exit = next_mastery >= MASTERY_VERIFICATION_THRESHOLD

    # Advanced gate: L3/L4 steep surge or near exit
    if depth_level in ["L3", "L4"] and (is_steep_surge or is_near_exit):
        return True

    # High-mastery gate: Candidates at L2 reaching >= 0.85 (e.g. 90.2% on Attempt 4)
    if next_mastery >= MASTERY_VERIFICATION_THRESHOLD:
        return True

    return False



def evaluate_policy(
    depth_level: str,
    prior: float,
    next_mastery: float,
    attempts: int,
    verdict: str,
    is_da_turn: bool = False,
    has_faced_da: bool = False
) -> PolicyDecision:
    # 1. Handling the outcome of a Devil's Advocate turn
    if is_da_turn:
        if verdict == "correct" or (verdict == "partial" and next_mastery >= MASTERY_VERIFICATION_THRESHOLD):
            return PolicyDecision(
                action="EXIT_VERIFIED",
                next_depth=depth_level,
                state="VERIFIED",
                is_devils_advocate=False,
                reason="Candidate successfully defended architectural trade-offs under Devil's Advocate examination."
            )
        else:
            return PolicyDecision(
                action="EXIT_SHALLOW",
                next_depth=depth_level,
                state="SHALLOW",
                is_devils_advocate=False,
                reason="Candidate collapsed under Devil's Advocate cross-examination. Architectural bluff detected; skill concluded as Shallow."
            )

    # 2. Check for Devil's Advocate Trigger (Evaluated BEFORE budget exit so high performers get their DA defense!)
    if check_devils_advocate_trigger(depth_level, prior, next_mastery, has_faced_da, attempts):
        return PolicyDecision(
            action="TRIGGER_DEVILS_ADVOCATE",
            next_depth=depth_level,
            state="IN_PROGRESS",
            is_devils_advocate=True,
            reason=f"High mastery demonstrated on {depth_level} ({next_mastery*100:.1f}%). Triggering Devil's Advocate trade-off probe to test architectural defense."
        )

    # 3. Check for Max Attempts / Budget Cap
    if attempts >= MAX_ATTEMPTS_PER_SKILL:
        if next_mastery >= MASTERY_VERIFICATION_THRESHOLD:
            # Candidate has high score (>= 85%) - certify as VERIFIED!
            return PolicyDecision(
                action="EXIT_VERIFIED",
                next_depth=depth_level,
                state="VERIFIED",
                is_devils_advocate=False,
                reason=f"Candidate achieved verified mastery ({next_mastery*100:.1f}%) across {attempts} questions at {depth_level} level."
            )
        else:
            # Score remained below 85%
            return PolicyDecision(
                action="EXIT_SHALLOW",
                next_depth=depth_level,
                state="SHALLOW",
                is_devils_advocate=False,
                reason=f"Maximum allowed questions ({MAX_ATTEMPTS_PER_SKILL}) reached. Latent mastery ({next_mastery*100:.1f}%) remained below verification threshold ({MASTERY_VERIFICATION_THRESHOLD*100:.0f}%). Competency ceiling recorded as Shallow."
            )

    # 4. Check for Mastery Verification Exit (when attempts < 4 and already defended DA)
    if next_mastery >= MASTERY_VERIFICATION_THRESHOLD:
        if has_faced_da:
            return PolicyDecision(
                action="EXIT_VERIFIED",
                next_depth=depth_level,
                state="VERIFIED",
                is_devils_advocate=False,
                reason=f"Candidate demonstrated verified mastery ({next_mastery*100:.1f}%) at depth {depth_level} with trade-offs defended."
            )
        else:
            # Escalate depth
            next_depth = "L2" if depth_level == "L1" else "L3"
            return PolicyDecision(
                action="ESCALATE_DEPTH",
                next_depth=next_depth,
                state="IN_PROGRESS",
                is_devils_advocate=False,
                reason=f"High foundational mastery ({next_mastery*100:.1f}%). Escalating to {next_depth} to test higher-order competency."
            )


    # 5. Routine Turn: Handle Correct, Partial, and Incorrect
    current_idx = DEPTH_HIERARCHY.index(depth_level) if depth_level in DEPTH_HIERARCHY else 0

    if verdict == "correct":
        if current_idx < len(DEPTH_HIERARCHY) - 1:
            next_depth = DEPTH_HIERARCHY[current_idx + 1]
            action = "ESCALATE_DEPTH"
            reason = f"Correct answer at {depth_level}. Escalating cognitive depth to {next_depth}."
        else:
            next_depth = depth_level
            action = "CONTINUE_SAME_LEVEL"
            reason = f"Correct answer at maximum depth {depth_level}."
    elif verdict == "partial":
        # Keep candidate at same level for a clarifying re-probe
        next_depth = depth_level
        action = "CONTINUE_SAME_LEVEL"
        reason = f"Partial credit at {depth_level}. Demonstrates core grasp; re-probing at same depth to evaluate full competency."
    else:
        # Incorrect answer
        next_depth = depth_level
        action = "CONTINUE_SAME_LEVEL"
        reason = f"Incorrect answer at {depth_level}. Re-probing at {next_depth} with alternative question."

    return PolicyDecision(
        action=action,
        next_depth=next_depth,
        state="IN_PROGRESS",
        is_devils_advocate=False,
        reason=reason
    )



if __name__ == "__main__":
    print("Testing Policy Engine & Devil's Advocate Triggers...")

    # Test 1: Normal L1 -> L2 Escalation
    dec1 = evaluate_policy(depth_level="L1", prior=0.30, next_mastery=0.597, attempts=1, verdict="correct")
    print(f"Test 1 (L1 Correct) : Action={dec1.action} -> Next={dec1.next_depth} (Expected: ESCALATE_DEPTH -> L2)")
    assert dec1.action == "ESCALATE_DEPTH" and dec1.next_depth == "L2"

    # Test 2: Steep surge on L3 triggering Devil's Advocate
    dec2 = evaluate_policy(depth_level="L3", prior=0.65, next_mastery=0.88, attempts=2, verdict="correct")
    print(f"Test 2 (L3 Surge)   : Action={dec2.action} -> DA={dec2.is_devils_advocate} (Expected: TRIGGER_DEVILS_ADVOCATE)")
    assert dec2.action == "TRIGGER_DEVILS_ADVOCATE" and dec2.is_devils_advocate is True

    # Test 3: DA Passed -> VERIFIED
    dec3 = evaluate_policy(depth_level="L3", prior=0.88, next_mastery=0.92, attempts=3, verdict="correct", is_da_turn=True)
    print(f"Test 3 (DA Passed)  : State={dec3.state} -> Action={dec3.action} (Expected: VERIFIED)")
    assert dec3.state == "VERIFIED"

    # Test 4: Max attempts reached without mastery -> SHALLOW
    dec4 = evaluate_policy(depth_level="L1", prior=0.08, next_mastery=0.02, attempts=4, verdict="incorrect")
    print(f"Test 4 (Attempts 4) : State={dec4.state} -> Action={dec4.action} (Expected: SHALLOW)")
    assert dec4.state == "SHALLOW"

    # Test 5: Python Attempt 4 high-mastery case (90.2% on L2) -> Trigger Devil's Advocate!
    dec5 = evaluate_policy(depth_level="L2", prior=0.781, next_mastery=0.902, attempts=4, verdict="correct", has_faced_da=False)
    print(f"Test 5 (L2 Attempt 4 High Score): Action={dec5.action} -> DA={dec5.is_devils_advocate} (Expected: TRIGGER_DEVILS_ADVOCATE)")
    assert dec5.action == "TRIGGER_DEVILS_ADVOCATE" and dec5.is_devils_advocate is True

    # Test 6: Python Turn 5 (DA Defended) -> EXIT_VERIFIED
    dec6 = evaluate_policy(depth_level="L2", prior=0.902, next_mastery=0.950, attempts=5, verdict="correct", is_da_turn=True, has_faced_da=True)
    print(f"Test 6 (DA Defense Passed): State={dec6.state} -> Action={dec6.action} (Expected: VERIFIED)")
    assert dec6.state == "VERIFIED" and dec6.action == "EXIT_VERIFIED"

    # Test 7: Max attempts reached with high mastery after DA faced -> EXIT_VERIFIED (Certified L2 Proficient)
    dec7 = evaluate_policy(depth_level="L2", prior=0.781, next_mastery=0.902, attempts=4, verdict="correct", has_faced_da=True)
    print(f"Test 7 (Max Attempts + High Mastery): State={dec7.state} -> Action={dec7.action} (Expected: VERIFIED)")
    assert dec7.state == "VERIFIED" and dec7.action == "EXIT_VERIFIED"

    print("\nSUCCESS: All Policy Engine decisions and Devil's Advocate triggers tested cleanly!")
