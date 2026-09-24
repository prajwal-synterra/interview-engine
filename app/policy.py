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
    has_faced_da: bool
) -> bool:
    """
    Evaluates the 3 deterministic Devil's Advocate trigger conditions:
    1. Advanced Level: depth is L3 or L4
    2. Steep Surge: Delta >= 0.20 in this turn
    3. Threshold: Resulting mastery >= 0.85
    Plus: Has not already faced Devil's Advocate in this session.
    """
    if has_faced_da:
        return False

    is_advanced = depth_level in ["L3", "L4"]
    delta = next_mastery - prior
    is_steep_surge = delta >= 0.20
    is_near_exit = next_mastery >= MASTERY_VERIFICATION_THRESHOLD

    return is_advanced and is_steep_surge and is_near_exit


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
        if verdict == "correct":
            return PolicyDecision(
                action="EXIT_VERIFIED",
                next_depth=depth_level,
                state="VERIFIED",
                is_devils_advocate=False,
                reason="Candidate successfully defended architectural trade-offs under Devil's Advocate examination."
            )
        else:
            return PolicyDecision(
                action="CONTINUE_SAME_LEVEL",
                next_depth="L2",  # Gracefully step back or re-probe
                state="IN_PROGRESS",
                is_devils_advocate=False,
                reason="Candidate collapsed under Devil's Advocate probe. Buzzword bluff detected; stepping back."
            )

    # 2. Check for Devil's Advocate Trigger
    if check_devils_advocate_trigger(depth_level, prior, next_mastery, has_faced_da):
        return PolicyDecision(
            action="TRIGGER_DEVILS_ADVOCATE",
            next_depth=depth_level,
            state="IN_PROGRESS",
            is_devils_advocate=True,
            reason=f"Steep mastery surge on {depth_level} (Δ={next_mastery - prior:.4f}, Mastery={next_mastery:.4f}). Triggering Devil's Advocate trade-off probe."
        )

    # 3. Check for standard Mastery Verification Exit (without surge trigger)
    if next_mastery >= MASTERY_VERIFICATION_THRESHOLD:
        return PolicyDecision(
            action="EXIT_VERIFIED",
            next_depth=depth_level,
            state="VERIFIED",
            is_devils_advocate=False,
            reason=f"Candidate achieved mastery ({next_mastery:.4f} >= {MASTERY_VERIFICATION_THRESHOLD}). Certified verified."
        )

    # 4. Check for Max Attempts / Shallow Exit
    if attempts >= MAX_ATTEMPTS_PER_SKILL:
        return PolicyDecision(
            action="EXIT_SHALLOW",
            next_depth=depth_level,
            state="SHALLOW",
            is_devils_advocate=False,
            reason=f"Max attempts ({MAX_ATTEMPTS_PER_SKILL}) reached without reaching verification threshold. Ceiling recorded as Shallow."
        )

    # 5. Routine Turn: Escalate Depth or Re-probe
    current_idx = DEPTH_HIERARCHY.index(depth_level) if depth_level in DEPTH_HIERARCHY else 0

    if verdict == "correct":
        if current_idx < len(DEPTH_HIERARCHY) - 1:
            next_depth = DEPTH_HIERARCHY[current_idx + 1]
            action = "ESCALATE_DEPTH"
            reason = f"Correct answer at {depth_level}. Escalating cognitive depth to {next_depth}."
        else:
            next_depth = depth_level
            action = "CONTINUE_SAME_LEVEL"
            reason = f"Correct answer at {depth_level} but already at max depth."
    else:
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

    print("\nSUCCESS: All Policy Engine decisions and Devil's Advocate triggers tested cleanly!")
