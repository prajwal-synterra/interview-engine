# pyrefly: ignore [missing-import]
"""
Conversational Behavioral Proctoring Engine.
Evaluates:
- Lexical entropy & Type-Token Ratio (detects reading pre-generated LLM answers)
- Latency distribution jitter (detects external LLM copilot response turnaround)
- Contradiction probes (detects blind compliance to false premises)
- Conversational curiosity (detects lack of clarifying inquiries)
- Behavioral Integrity Index (BII) tracking
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import math
import re


class AnomalySeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    CRITICAL = "CRITICAL"


@dataclass
class ProctorFlag:
    flag_type: str
    severity: AnomalySeverity
    evidence: str
    penalty: float


@dataclass
class TurnAcousticData:
    turn_id: int
    latency_ms: int              # Time between interviewer question end and candidate speech start
    candidate_transcript: str
    is_clarifying_question: bool = False
    is_contradiction_probe: bool = False
    passed_contradiction_probe: Optional[bool] = None


class BehavioralProctorEngine:
    """Evaluates acoustic latency, lexical entropy, curiosity, and contradiction probes."""

    def __init__(self):
        self.turns: List[TurnAcousticData] = []
        self.flags: List[ProctorFlag] = []
        self.bii: float = 1.0  # Starts at 1.0 (flawless)

        # Regex pattern for authentic engineering clarifying questions
        self.clarification_regex = re.compile(
            r"(\b(should we assume|what scale|what is the read|write ratio|can we trade|is it eventual consistency|any constraints on|how many users|qps)\b|\?)",
            re.IGNORECASE
        )

    def record_turn(
        self,
        latency_ms: float = 800.0,
        transcript: str = "",
        is_contradiction_probe: bool = False,
        passed_contradiction_probe: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Records a candidate response and evaluates all real-time fraud vectors."""
        turn_id = len(self.turns) + 1
        is_clarifying = bool(self.clarification_regex.search(transcript))

        turn_data = TurnAcousticData(
            turn_id=turn_id,
            latency_ms=int(latency_ms),
            candidate_transcript=transcript,
            is_clarifying_question=is_clarifying,
            is_contradiction_probe=is_contradiction_probe,
            passed_contradiction_probe=passed_contradiction_probe
        )
        self.turns.append(turn_data)

        # 1. Evaluate Lexical Density / Type-Token Ratio
        ttr, entropy = self._calculate_lexical_metrics(transcript)
        word_count = len(re.findall(r"\b\w+\b", transcript))
        if word_count >= 35 and ttr > 0.88:
            self._raise_flag(
                flag_type="UNNATURAL_LEXICAL_DENSITY_TTR",
                severity=AnomalySeverity.MEDIUM,
                evidence=f"Turn {turn_id} exhibited TTR={ttr:.2f} across {word_count} words without natural disfluency.",
                penalty=0.10
            )

        # 2. Evaluate Contradiction Probe
        if is_contradiction_probe and passed_contradiction_probe is False:
            self._raise_flag(
                flag_type="CONTRADICTION_PROBE_FAILED",
                severity=AnomalySeverity.CRITICAL,
                evidence=f"Turn {turn_id} blindly accepted an injected false technical premise.",
                penalty=0.35
            )

        # 3. Evaluate Copilot Latency Distribution (after >= 3 turns)
        self._evaluate_latency_distribution()

        return {
            "turn_id": turn_id,
            "latency_ms": int(latency_ms),
            "ttr": round(ttr, 3),
            "entropy": round(entropy, 3),
            "is_clarifying": is_clarifying,
            "current_bii": round(self.bii, 3),
            "flags_count": len(self.flags)
        }

    def _calculate_lexical_metrics(self, text: str) -> Tuple[float, float]:
        """Calculates Type-Token Ratio (TTR) and normalized Shannon Entropy."""
        words = re.findall(r"\b\w+\b", text.lower())
        if not words:
            return 0.0, 0.0

        total_tokens = len(words)
        unique_tokens = len(set(words))
        ttr = unique_tokens / total_tokens

        # Shannon Entropy
        freqs: Dict[str, int] = {}
        for w in words:
            freqs[w] = freqs.get(w, 0) + 1

        entropy = 0.0
        for count in freqs.values():
            p = count / total_tokens
            entropy -= p * math.log2(p)

        max_entropy = math.log2(unique_tokens) if unique_tokens > 1 else 1.0
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0

        return ttr, normalized_entropy

    def _evaluate_latency_distribution(self) -> Optional[ProctorFlag]:
        """Detects the unnatural high-latency, low-jitter signature of external AI copilots."""
        if len(self.turns) < 3:
            return None

        latencies = [t.latency_ms for t in self.turns]
        mean_lat = sum(latencies) / len(latencies)
        variance = sum((l - mean_lat) ** 2 for l in latencies) / len(latencies)
        jitter_std = math.sqrt(variance)

        # Copilot HUD Signature: High mean latency (>2000ms) with near-zero jitter (<180ms)
        if mean_lat > 2000 and jitter_std < 180:
            existing = any(f.flag_type == "COPILOT_LATENCY_JITTER_ANOMALY" for f in self.flags)
            if not existing:
                return self._raise_flag(
                    flag_type="COPILOT_LATENCY_JITTER_ANOMALY",
                    severity=AnomalySeverity.CRITICAL,
                    evidence=(
                        f"Mean latency={mean_lat:.1f}ms with unnatural low jitter std={jitter_std:.1f}ms, "
                        "consistent with external LLM turnaround reading."
                    ),
                    penalty=0.40
                )
        return None

    def evaluate_conversational_curiosity(self, min_turns: int = 5) -> Optional[ProctorFlag]:
        """Evaluates whether candidate ever asked clarifying inquiries in ambiguous prompts."""
        if len(self.turns) < min_turns:
            return None

        clarifying_turns = sum(1 for t in self.turns if t.is_clarifying_question)
        if clarifying_turns == 0:
            existing = any(f.flag_type == "PASSIVE_COMPLIANCE_ZERO_CURIOSITY" for f in self.flags)
            if not existing:
                return self._raise_flag(
                    flag_type="PASSIVE_COMPLIANCE_ZERO_CURIOSITY",
                    severity=AnomalySeverity.LOW,
                    evidence="Zero clarifying questions asked across multi-turn ambiguous architectural prompts.",
                    penalty=0.08
                )
        return None

    def _raise_flag(self, flag_type: str, severity: AnomalySeverity, evidence: str, penalty: float) -> ProctorFlag:
        flag = ProctorFlag(flag_type=flag_type, severity=severity, evidence=evidence, penalty=penalty)
        self.flags.append(flag)
        self.bii = max(0.0, round(self.bii - penalty, 3))
        return flag

    @property
    def integrity_summary(self) -> Dict[str, Any]:
        return {
            "behavioral_integrity_index": round(self.bii, 3),
            "total_turns": len(self.turns),
            "flags_raised": [
                {
                    "type": f.flag_type,
                    "severity": f.severity.value,
                    "penalty": f.penalty,
                    "evidence": f.evidence
                }
                for f in self.flags
            ],
            "passed_proctoring": self.bii >= 0.70
        }


# Canonical Aliases
ProctorEngine = BehavioralProctorEngine
