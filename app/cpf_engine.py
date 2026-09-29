"""
Cognitive Potential Fingerprint (CPF) & Master Composite Scorer.
Document Reference: AIS-ARCH-2026-V3-MASTER / REPORT 5 & REPORT 6
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
import math


class HiringRecommendation(str, Enum):
    STRONG_HIRE = "STRONG_HIRE"       # Score >= 85
    HIRE = "HIRE"                     # Score 70 - 84
    LEANING_HIRE = "LEANING_HIRE"     # Score 55 - 69
    NO_HIRE = "NO_HIRE"               # Score < 55
    FLAGGED_FOR_FRAUD = "FLAGGED_FOR_FRAUD"  # BII < 0.70 overrides any technical score


@dataclass
class CognitiveFingerprint:
    breadth: float        # B: 0 to 100
    depth: float          # D: 0 to 100
    velocity: float       # V: 0 to 100 (learning rate)
    rigor: float          # R: 0 to 100 (trade-off completeness)
    resilience: float     # A: 0 to 100 (adversarial challenge survival)


@dataclass
class SkillEvaluationSummary:
    skill_code: str
    weight: float                     # e.g., 0.35
    final_mastery: float              # P(L_final) from BKT: 0.0 to 1.0
    scaffolding_counts: Dict[int, int] # {1: count, 2: count, 3: count}


class MasterScorer:
    """Computes the 5D CPF and the deterministic Master Scoring equation."""

    def __init__(self, scaffolding_penalty_lambda: float = 0.05, devils_bonus_gamma: float = 0.10):
        self.lambda_penalty = scaffolding_penalty_lambda
        self.gamma_bonus = devils_bonus_gamma

    def generate_cpf(
        self,
        skills_tested: List[SkillEvaluationSummary],
        total_jd_skills_count: int,
        learning_deltas: List[float],
        rigor_checks_passed: int,
        total_rigor_checks: int,
        devils_advocate_passed: int,
        total_devils_advocate: int
    ) -> CognitiveFingerprint:
        """Constructs the 5-dimensional Cognitive Potential Fingerprint."""
        # 1. Breadth: percentage of JD skills explored
        breadth = min(100.0, (len(skills_tested) / max(1, total_jd_skills_count)) * 100.0)

        # 2. Depth: average terminal mastery on tested skills
        avg_mastery = sum(s.final_mastery for s in skills_tested) / max(1, len(skills_tested))
        depth = round(avg_mastery * 100.0, 2)

        # 3. Velocity: average positive delta when candidate was challenged
        avg_delta = sum(learning_deltas) / max(1, len(learning_deltas)) if learning_deltas else 0.15
        velocity = min(100.0, round(avg_delta * 180.0, 2))  # Scaled to 0-100

        # 4. Rigor: ratio of trade-offs articulated (latency, memory, consistency)
        rigor = round((rigor_checks_passed / max(1, total_rigor_checks)) * 100.0, 2)

        # 5. Resilience: Devil's Advocate survival rate
        resilience = round((devils_advocate_passed / max(1, total_devils_advocate)) * 100.0, 2)

        return CognitiveFingerprint(
            breadth=round(breadth, 2),
            depth=round(depth, 2),
            velocity=round(velocity, 2),
            rigor=round(rigor, 2),
            resilience=round(resilience, 2)
        )

    def calculate_final_score(
        self,
        skills: List[SkillEvaluationSummary],
        bii: float,
        devils_advocate_score: float = 0.0  # -1.0 (failed) to +1.0 (flawlessly defended)
    ) -> Dict:
        """
        Computes the Master Scoring Formula:
        FinalScore = (Sum(w_k * P(L_k))) * (1 - lambda * Sum(l * N_l)) * BII * (1 + gamma * S_devils)
        """
        # 1. Weighted Terminal Knowledge Base
        weighted_knowledge = sum(s.weight * s.final_mastery for s in skills)

        # 2. Scaffolding Penalty Factor
        total_scaffold_penalty_units = sum(
            level * count
            for s in skills
            for level, count in s.scaffolding_counts.items()
        )
        scaffold_multiplier = max(0.50, 1.0 - (self.lambda_penalty * total_scaffold_penalty_units))

        # 3. Devil's Advocate Modifier (-1.0 to +1.0)
        adversarial_multiplier = 1.0 + (self.gamma_bonus * max(-1.0, min(1.0, devils_advocate_score)))

        # 4. Composite Mathematical Score (0.0 to 1.0)
        raw_score = weighted_knowledge * scaffold_multiplier * bii * adversarial_multiplier
        final_score_100 = round(max(0.0, min(100.0, raw_score * 100.0)), 2)

        # 5. Final Recommendation
        if bii < 0.70:
            recommendation = HiringRecommendation.FLAGGED_FOR_FRAUD
        elif final_score_100 >= 85.0:
            recommendation = HiringRecommendation.STRONG_HIRE
        elif final_score_100 >= 70.0:
            recommendation = HiringRecommendation.HIRE
        elif final_score_100 >= 55.0:
            recommendation = HiringRecommendation.LEANING_HIRE
        else:
            recommendation = HiringRecommendation.NO_HIRE

        return {
            "final_score": final_score_100,
            "recommendation": recommendation.value,
            "weighted_knowledge_base": round(weighted_knowledge * 100, 2),
            "scaffolding_multiplier": round(scaffold_multiplier, 3),
            "behavioral_integrity_index": round(bii, 3),
            "adversarial_multiplier": round(adversarial_multiplier, 3),
            "passed_proctoring": bii >= 0.70
        }
