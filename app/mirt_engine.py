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
