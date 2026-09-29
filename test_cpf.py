"""
Verification Test Suite for CPF & Master Scorer.
Tests:
1. Exceptional human engineer: High depth, strong Devil's Advocate defense -> STRONG_HIRE.
2. Candidate requiring multiple scaffolding nudges: penalized mathematically -> HIRE / LEANING_HIRE.
3. Copilot cheater: 100% technical mastery but BII = 0.60 -> FLAGGED_FOR_FRAUD override.
"""

from app.cpf_engine import MasterScorer, SkillEvaluationSummary, HiringRecommendation


def test_strong_hire_candidate():
    print("\n--- Test 1: Senior Staff Engineer (Strong Hire) ---")
    scorer = MasterScorer()

    skills = [
        SkillEvaluationSummary("distributed_consensus", weight=0.50, final_mastery=0.98, scaffolding_counts={1: 0, 2: 0, 3: 0}),
        SkillEvaluationSummary("event_driven_architecture", weight=0.50, final_mastery=0.95, scaffolding_counts={1: 0, 2: 0, 3: 0}),
    ]

    # Flawless proctoring (BII = 1.0) and survived Devil's Advocate (+1.0)
    result = scorer.calculate_final_score(skills=skills, bii=1.0, devils_advocate_score=1.0)
    print(f"Final Score: {result['final_score']} | Rec: {result['recommendation']}")

    assert result["recommendation"] == HiringRecommendation.STRONG_HIRE.value
    assert result["final_score"] >= 85.0
    print("[PASS] High technical mastery + resilient defense yielded STRONG_HIRE.")


def test_heavily_assisted_candidate():
    print("\n--- Test 2: Heavily Assisted Candidate (Scaffolding Penalties) ---")
    scorer = MasterScorer()

    # Candidate reached 0.85 mastery but required two Level 2 nudges and one Level 3 nudge
    skills = [
        SkillEvaluationSummary("redis_caching", weight=1.0, final_mastery=0.85, scaffolding_counts={1: 0, 2: 2, 3: 1}),
    ]

    result = scorer.calculate_final_score(skills=skills, bii=1.0, devils_advocate_score=0.0)
    print(f"Final Score: {result['final_score']} (Scaffold mult: {result['scaffolding_multiplier']}) | Rec: {result['recommendation']}")

    # Scaffold penalty units: (2*2) + (3*1) = 7 units * 0.05 = 0.35 deduction
    assert result["scaffolding_multiplier"] < 1.0
    assert result["final_score"] < 70.0  # Dropped from HIRE to LEANING_HIRE
    print("[PASS] Scaffolding assistance accurately decayed composite score.")


def test_fraud_override_protection():
    print("\n--- Test 3: Cheater Fraud Override Guardrail ---")
    scorer = MasterScorer()

    # Candidate has pristine 100% technical answers
    skills = [
        SkillEvaluationSummary("system_design", weight=1.0, final_mastery=1.0, scaffolding_counts={1: 0, 2: 0, 3: 0}),
    ]

    # BUT Behavioral Integrity Index is 0.60 (Copilot HUD latency detected)
    result = scorer.calculate_final_score(skills=skills, bii=0.60, devils_advocate_score=-0.5)
    print(f"Final Score: {result['final_score']} | BII: {result['behavioral_integrity_index']} | Rec: {result['recommendation']}")

    assert result["recommendation"] == HiringRecommendation.FLAGGED_FOR_FRAUD.value
    print("[PASS] Integrity failure immediately overrode 100% technical score with FLAGGED_FOR_FRAUD.")


if __name__ == "__main__":
    test_strong_hire_candidate()
    test_heavily_assisted_candidate()
    test_fraud_override_protection()
    print("\n========================================================")
    print("ALL CPF & MASTER SCORER TESTS PASSED (3/3)!")
    print("========================================================")
