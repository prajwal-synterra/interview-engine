"""
Multidimensional Item Response Theory (MIRT) Engine.
Document Reference: AIS-ARCH-2026-V3-MASTER / REPORT 5
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math


DIMENSIONS = ["algorithms", "system_design", "concurrency", "databases", "distributed_systems"]


@dataclass
class ItemParameters:
    item_id: str
    prompt: str
    difficulty: float                    # b: scalar difficulty (-3.0 = very easy, 0.0 = mid, +3.0 = staff frontier)
    discrimination: Dict[str, float]     # alpha: weight per dimension (e.g., {"system_design": 1.2, "concurrency": 0.8})


@dataclass
class AbilityEstimate:
    theta: Dict[str, float]              # Current estimated ability in each dimension
    standard_error: Dict[str, float]     # Uncertainty/error in each dimension
    questions_answered: int = 0


class MIRTEngine:
    """Multidimensional Item Response Theory Engine with continuous ability updates."""

    def __init__(self, initial_theta: Optional[Dict[str, float]] = None, learning_rate: float = 0.45):
        # Default baseline theta is 0.0 (average industry baseline)
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
        """
        Calculates P(correct | theta, alpha, b) = sigmoid( alpha · theta - b )
        """
        # Dot product: alpha · theta
        dot_product = 0.0
        for dim, alpha in item.discrimination.items():
            current_theta = self.theta.get(dim, 0.0)
            dot_product += alpha * current_theta

        z = dot_product - item.difficulty
        return self._sigmoid(z)

    def update_ability(self, item: ItemParameters, observation: int) -> AbilityEstimate:
        """
        Updates the candidate's multidimensional ability vector theta after an observation.
        observation: 1 (demonstrated competence) or 0 (struggled/failed)
        Uses online gradient update: theta_new = theta_old + eta * alpha * (obs - P)
        """
        assert observation in (0, 1), "Observation must be 1 or 0"
        p_predicted = self.predict_probability(item)
        residual = float(observation) - p_predicted

        # Dynamic learning rate decays slightly as confidence increases, but never locks
        eta = self.learning_rate / (1.0 + 0.05 * len(self.history))

        for dim, alpha in item.discrimination.items():
            if dim in self.theta:
                # Update theta
                delta = eta * alpha * residual
                self.theta[dim] = round(self.theta[dim] + delta, 4)
                
                # Update uncertainty/standard error (Information increases -> error decreases)
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
        """
        Computes Fisher Information for an item at current theta.
        Information is highest when item difficulty matches current candidate ability.
        """
        p = self.predict_probability(item)
        alpha_norm_sq = sum(a ** 2 for a in item.discrimination.values())
        return alpha_norm_sq * p * (1.0 - p)

    def select_highest_information_item(self, candidate_items: List[ItemParameters]) -> Optional[ItemParameters]:
        """
        Selects the item that yields the highest Fisher Information at the candidate's current theta.
        Enables testing right at the edge of the candidate's competence.
        """
        if not candidate_items:
            return None

        best_item = None
        max_info = -1.0

        for item in candidate_items:
            info = self.calculate_fisher_information(item)
            if info > max_info:
                max_info = info
                best_item = item

        return best_item


# Canonical Macro Pillar -> MIRT Dimension Discrimination Mapping
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
    """Retrieves 5D discrimination weights for a given pillar."""
    pid = pillar_id.upper()
    if pid in PILLAR_MIRT_DISCRIMINATION:
        return PILLAR_MIRT_DISCRIMINATION[pid]
    # Fallback balanced discrimination
    return {"system_design": 1.0, "algorithms": 0.5}


def theta_to_percentile(theta: float) -> float:
    """Converts a standard normal latent ability score theta into an industry percentile."""
    return round(0.5 * (1.0 + math.erf(theta / math.sqrt(2.0))) * 100.0, 1)


DIMENSION_LABELS: Dict[str, str] = {
    "algorithms": "Algorithms & Computational Complexity",
    "system_design": "System Design & Scalability",
    "concurrency": "Concurrency & Asynchronous Streaming",
    "databases": "Database Internals & ACID Transactions",
    "distributed_systems": "Distributed Consensus & Fault Tolerance"
}


def get_radar_summary(theta: Dict[str, float], std_error: Dict[str, float]) -> List[Dict]:
    """Formats theta and standard error into human-readable percentiles and benchmark tiers."""
    rows = []
    for dim in DIMENSIONS:
        th = theta.get(dim, 0.0)
        se = std_error.get(dim, 1.0)
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
