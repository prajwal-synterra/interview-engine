"""
Bayesian Knowledge Tracing (BKT) Engine with 4-Level Scaffolding & Slip-Floor Protection.
Document Reference: AIS-ARCH-2026-V3-MASTER / REPORT 5
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class MasteryStatus(str, Enum):
    UNMASTERED = "UNMASTERED"
    IN_PROGRESS = "IN_PROGRESS"
    MASTERED = "MASTERED"


class SeniorityTier(str, Enum):
    STUDENT = "STUDENT"          # Lower prior P(L0) = 0.15
    JUNIOR = "JUNIOR"            # P(L0) = 0.25
    MID = "MID"                  # P(L0) = 0.45
    SENIOR_STAFF = "STAFF"       # High prior P(L0) = 0.70


@dataclass
class BKTConfig:
    p_t: float = 0.15           # Probability of transit (learning)
    p_s: float = 0.10           # Baseline slip rate
    p_g: float = 0.05           # Probability of guess
    s_max: float = 0.25         # Maximum slip floor
    decay_rate: float = 0.85    # Anti-coaching decay factor per scaffold level
    mastery_threshold: float = 0.85
    deficiency_threshold: float = 0.20
    min_observations_for_deficiency: int = 3
    surge_threshold: float = 0.40  # Delta surge trigger for Devil's Advocate


@dataclass
class BKTObservation:
    step: int
    observation: int            # 1 for correct, 0 for incorrect
    scaffolding_level: int      # 0 (open-ended), 1 (nudge), 2 (partial), 3 (trade-off)
    prior_mastery: float
    posterior_mastery: float
    transitioned_mastery: float
    effective_mastery: float
    slip_used: float


class BKTNode:
    """Tracks latent mastery P(L) for a single skill."""

    def __init__(self, skill_code: str, seniority: SeniorityTier = SeniorityTier.MID, config: Optional[BKTConfig] = None):
        self.skill_code = skill_code
        self.seniority = seniority
        self.config = config or BKTConfig()
        
        # Calibrate initial P(L0) based on seniority
        self.p_l: float = self._calibrate_prior(seniority)
        self.history: List[BKTObservation] = []
        self.consecutive_slips: int = 0
        self._status_override: Optional[MasteryStatus] = None

    def _calibrate_prior(self, seniority: SeniorityTier) -> float:
        priors = {
            SeniorityTier.STUDENT: 0.15,
            SeniorityTier.JUNIOR: 0.25,
            SeniorityTier.MID: 0.45,
            SeniorityTier.SENIOR_STAFF: 0.70,
        }
        return priors.get(seniority, 0.30)

    def update(self, observation: int, scaffolding_level: int = 0) -> Dict[str, Any]:
        """
        Executes standard BKT Bayesian update with:
        1. Dynamic slip floor (prevents repeated errors being excused as 'slips')
        2. Closed-form posterior update
        3. Forward transition step
        4. Anti-coaching scaffolding decay
        """
        assert observation in (0, 1), "Observation must be 1 (correct) or 0 (incorrect)"
        assert 0 <= scaffolding_level <= 3, "Scaffolding level must be 0, 1, 2, or 3"

        p_prev = self.p_l
        p_t = self.config.p_t
        p_g = self.config.p_g

        # 1. Dynamic Slip Floor Protection
        if observation == 0:
            self.consecutive_slips += 1
            # Dynamic slip scales with consecutive errors but is capped at s_max
            p_s = min(self.config.s_max, self.config.p_s + (0.05 * (self.consecutive_slips - 1)))
        else:
            self.consecutive_slips = 0
            p_s = self.config.p_s

        # 2. Closed-form posterior calculation P(L_t | O_t)
        if observation == 1:
            numerator = p_prev * (1.0 - p_s)
            denominator = (p_prev * (1.0 - p_s)) + ((1.0 - p_prev) * p_g)
        else:
            numerator = p_prev * p_s
            denominator = (p_prev * p_s) + ((1.0 - p_prev) * (1.0 - p_g))

        p_posterior = numerator / denominator if denominator > 0 else p_prev

        # 3. Forward state transition: P(L_t+1) = Posterior + (1 - Posterior) * P(T)
        p_transitioned = p_posterior + (1.0 - p_posterior) * p_t

        # 4. Anti-coaching Scaffolding Decay
        delta = p_transitioned - p_prev
        if delta > 0 and scaffolding_level > 0:
            # Dampen positive gains if the candidate required higher scaffolding
            decay_factor = self.config.decay_rate ** scaffolding_level
            p_effective = p_prev + (delta * decay_factor)
        else:
            p_effective = p_transitioned

        # Clamp between 0.001 and 0.999
        self.p_l = max(0.001, min(0.999, p_effective))

        # Check for mastery surge (trigger for Devil's Advocate)
        is_surge = (delta >= self.config.surge_threshold) or (self.p_l >= 0.90 and scaffolding_level == 0 and len(self.history) <= 1)

        # Record history
        record = BKTObservation(
            step=len(self.history) + 1,
            observation=observation,
            scaffolding_level=scaffolding_level,
            prior_mastery=round(p_prev, 4),
            posterior_mastery=round(p_posterior, 4),
            transitioned_mastery=round(p_transitioned, 4),
            effective_mastery=round(self.p_l, 4),
            slip_used=round(p_s, 4),
        )
        self.history.append(record)

        return {
            "skill_code": self.skill_code,
            "step": record.step,
            "observation": observation,
            "scaffolding_level": scaffolding_level,
            "prior_mastery": record.prior_mastery,
            "current_mastery": record.effective_mastery,
            "delta": round(self.p_l - p_prev, 4),
            "status": self.status.value,
            "is_surge": is_surge,
            "slip_used": record.slip_used,
        }

    @property
    def status(self) -> MasteryStatus:
        if self._status_override:
            return self._status_override
        if self.p_l >= self.config.mastery_threshold:
            return MasteryStatus.MASTERED
        if (
            len(self.history) >= self.config.min_observations_for_deficiency
            and self.p_l <= self.config.deficiency_threshold
        ):
            return MasteryStatus.UNMASTERED
        return MasteryStatus.IN_PROGRESS

    @status.setter
    def status(self, val: MasteryStatus):
        self._status_override = val
