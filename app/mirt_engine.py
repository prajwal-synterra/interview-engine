# pyrefly: ignore [missing-import]
"""
Multidimensional Item Response Theory (MIRT) Engine.
Implements:
- 5D latent engineering ability estimation (theta)
- Multi-dimensional discrimination loading (alpha) and item difficulty (b)
- Online stochastic gradient update per turn
- Fisher Information calculation
- Percentile conversion via error function (erf)
- 5D Radar profile generation for final hiring reports
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import math


DIMENSIONS = ["algorithms", "system_design", "concurrency", "databases", "distributed_systems"]


@dataclass
class ItemParameters:
    item_id: str
    prompt: str
    difficulty: float                    # b: scalar difficulty (-3.0 = very easy, 0.0 = mid, +3.0 = staff frontier)
    discrimination: Dict[str, float]     # alpha: weight per dimension


@dataclass
class AbilityEstimate:
    theta: Dict[str, float]              # Current estimated ability in each dimension
    standard_error: Dict[str, float]     # Uncertainty/error in each dimension
    questions_answered: int = 0


class MIRTEngine:
    """Multidimensional Item Response Theory Engine with continuous ability updates."""

    def __init__(self, initial_theta: Optional[Dict[str, float]] = None, learning_rate: float = 0.45):
        # Default baseline theta is 0.0 (average industry mid-level baseline)
        self.theta: Dict[str, float] = initial_theta or {dim: 0.0 for dim in DIMENSIONS}
        self.std_error: Dict[str, float] = {dim: 1.0 for dim in DIMENSIONS}
        self.learning_rate = learning_rate
        self.history: List[Dict] = []

    @staticmethod
    def _sigmoid(x: float) -> float:
        # Clamped sigmoid to prevent overflow
        x_clamped = max(-15.0, min(15.0, x))
        return 1.0 / (1.0 + math.exp(-x_clamped))

    def predict_probability(self, item: ItemParameters) -> float:
        """Calculates P(correct | theta, alpha, b) = sigmoid( alpha · theta - b )."""
        dot_product = 0.0
        for dim, alpha in item.discrimination.items():
            current_theta = self.theta.get(dim, 0.0)
            dot_product += alpha * current_theta

        z = dot_product - item.difficulty
        return self._sigmoid(z)

    def update_ability(
        self,
        item: Optional[ItemParameters] = None,
        observation: int = 1,
        skill: Optional[str] = None,
        difficulty: Optional[float] = None
    ) -> AbilityEstimate:
        """
        Updates the candidate's 5D ability vector theta after an observation.
        Accepts either an ItemParameters instance or (skill, difficulty, observation).
        """
        assert observation in (0, 1), "Observation must be 1 or 0"

        # Auto-construct ItemParameters if called by skill name
        if item is None:
            skill_code = skill or "GENERAL"
            diff = difficulty if difficulty is not None else 0.0
            item = ItemParameters(
                item_id=f"{skill_code}_{len(self.history) + 1}",
                prompt="",
                difficulty=diff,
                discrimination=get_discrimination_for_pillar(skill_code)
            )

        p_predicted = self.predict_probability(item)
        residual = float(observation) - p_predicted

        # Dynamic learning rate decays slightly as confidence grows
        eta = self.learning_rate / (1.0 + 0.05 * len(self.history))

        for dim, alpha in item.discrimination.items():
            if dim in self.theta:
                # Gradient update for ability
                delta = eta * alpha * residual
                self.theta[dim] = round(self.theta[dim] + delta, 4)

                # Uncertainty / standard error reduction
                info = (alpha ** 2) * p_predicted * (1.0 - p_predicted)
                self.std_error[dim] = max(0.15, round(self.std_error[dim] / (1.0 + 0.1 * info), 4))

        self.history.append({
            "step": len(self.history) + 1,
            "item_id": item.item_id,
            "difficulty": item.difficulty,
            "observation": observation,
            "p_predicted": round(p_predicted, 4),
            "residual": round(residual, 4),
            "updated_theta": dict(self.theta)
        })

        return AbilityEstimate(
            theta=dict(self.theta),
            standard_error=dict(self.std_error),
            questions_answered=len(self.history)
        )

    def calculate_fisher_information(self, item: ItemParameters) -> float:
        """Computes Fisher Information for an item at current candidate ability."""
        p = self.predict_probability(item)
        alpha_norm_sq = sum(a ** 2 for a in item.discrimination.values())
        return alpha_norm_sq * p * (1.0 - p)


# Canonical Pillar -> MIRT 5D Discrimination Weights
PILLAR_MIRT_DISCRIMINATION: Dict[str, Dict[str, float]] = {
    "DISTRIBUTED_CACHING": {
        "distributed_systems": 1.3,
        "system_design": 1.0,
        "databases": 0.8,
        "concurrency": 0.6
    },
    "ASYNC_CONCURRENCY": {
        "concurrency": 1.6,
        "system_design": 0.9,
        "algorithms": 0.5
    },
    "DATABASE_MODELING_TRANSACTIONS": {
        "databases": 1.5,
        "system_design": 1.0,
        "concurrency": 0.5
    },
    "AI_INFERENCE_ORCHESTRATION": {
        "system_design": 1.2,
        "concurrency": 0.8,
        "algorithms": 0.7
    },
    "CONTAINER_INFRASTRUCTURE": {
        "system_design": 1.3,
        "distributed_systems": 0.9
    },
    "EVENT_STREAMING_MESSAGING": {
        "distributed_systems": 1.4,
        "concurrency": 1.1,
        "system_design": 0.8
    },
    "API_DESIGN_PROTOCOLS": {
        "system_design": 1.2,
        "concurrency": 0.6
    },
    "DATA_STRUCTURES_ALGORITHMS": {
        "algorithms": 1.8,
        "concurrency": 0.4
    },
    "NOSQL_DISTRIBUTED_STORAGE": {
        "databases": 1.3,
        "distributed_systems": 1.2,
        "system_design": 0.8
    },
    "CLOUD_SECURITY_AUTH": {
        "system_design": 1.0,
        "distributed_systems": 0.6
    }
}


def get_discrimination_for_pillar(pillar_id: str) -> Dict[str, float]:
    """Retrieves 5D discrimination weights for a given technical pillar."""
    pid = pillar_id.upper()
    return PILLAR_MIRT_DISCRIMINATION.get(pid, {"system_design": 1.0, "algorithms": 0.5})


def theta_to_percentile(theta: float) -> float:
    """Converts standard normal ability theta into an industry benchmark percentile (0-100%)."""
    return round(0.5 * (1.0 + math.erf(theta / math.sqrt(2.0))) * 100.0, 1)


DIMENSION_LABELS: Dict[str, str] = {
    "algorithms": "Algorithms & Computational Complexity",
    "system_design": "System Design & Scalability",
    "concurrency": "Concurrency & Asynchronous Streaming",
    "databases": "Database Internals & ACID Transactions",
    "distributed_systems": "Distributed Consensus & Fault Tolerance"
}


def get_radar_summary(mirt_engine: MIRTEngine) -> List[Dict]:
    """Formats theta into human-readable percentiles and benchmark tiers for reports."""
    rows = []
    for dim in DIMENSIONS:
        th = mirt_engine.theta.get(dim, 0.0)
        se = mirt_engine.std_error.get(dim, 1.0)
        pct = theta_to_percentile(th)

        if th >= 2.0:
            tier = "Staff / Principal Frontier"
        elif th >= 1.0:
            tier = "Senior Engineer"
        elif th >= 0.0:
            tier = "Mid-Level Professional"
        elif th >= -1.0:
            tier = "Developing / Junior"
        else:
            tier = "Foundational Trainee"

        rows.append({
            "dimension": DIMENSION_LABELS.get(dim, dim.title()),
            "dimension_code": dim,
            "theta": round(th, 2),
            "std_error": round(se, 2),
            "percentile": pct,
            "tier": tier
        })
    return rows
