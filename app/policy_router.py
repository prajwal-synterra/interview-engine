"""
Deterministic Policy Router & Finite State Machine Orchestrator.
Document Reference: AIS-ARCH-2026-V3-MASTER / REPORT 6
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any

from app.bkt_engine import BKTNode, SeniorityTier, MasteryStatus
from app.graph_engine import KnowledgeGraph, EdgeType
from app.mirt_engine import MIRTEngine, ItemParameters
from app.proctor_engine import BehavioralProctorEngine
from app.cpf_engine import MasterScorer, SkillEvaluationSummary


class SessionState(str, Enum):
    READY = "READY"
    ACTIVE = "ACTIVE"
    SCAFFOLDING_L1 = "SCAFFOLDING_L1"
    SCAFFOLDING_L2 = "SCAFFOLDING_L2"
    SCAFFOLDING_L3 = "SCAFFOLDING_L3"
    DEVILS_ADVOCATE = "DEVILS_ADVOCATE"
    CONTRADICTION_PROBE = "CONTRADICTION_PROBE"
    FINALIZING = "FINALIZING"
    COMPLETED = "COMPLETED"


@dataclass
class PolicyDirective:
    next_action: str             # "NEXT_SKILL", "SCAFFOLD", "DEVILS_ADVOCATE", "CONTRADICTION_PROBE", "FINALIZE"
    current_state: SessionState
    skill_code: str
    scaffolding_level: int
    prompt_directive: str        # Injected into Gemini Live Audio context
    bii: float
    current_mastery: float


class PolicyRouter:
    """Coordinates BKT, Graph, MIRT, Proctoring, and State Machine transitions."""

    def __init__(self, seniority: SeniorityTier = SeniorityTier.MID):
        self.state = SessionState.READY
        self.seniority = seniority
        
        # Initialize Sub-Engines
        self.graph = KnowledgeGraph(seniority=seniority)
        self.mirt = MIRTEngine()
        self.proctor = BehavioralProctorEngine()
        self.scorer = MasterScorer()

        self.current_skill: Optional[str] = None
        self.current_scaffolding_level: int = 0
        self.devils_advocate_active: bool = False
        self.devils_advocate_results: List[float] = []

    def initialize_session(self, skills: List[tuple[str, float]]) -> None:
        """Initializes knowledge graph with required skills and weights."""
        for skill_code, prior in skills:
            self.graph.add_skill(skill_code, custom_prior=prior)
        
        self.current_skill = self.graph.get_next_recommended_skill()
        self.state = SessionState.ACTIVE

    def process_candidate_turn(
        self,
        observation: int,
        latency_ms: int,
        transcript: str,
        is_contradiction_probe: bool = False,
        passed_contradiction_probe: Optional[bool] = None
    ) -> PolicyDirective:
        """
        Core State Machine processing loop.
        Called on every turn when Shadow Evaluator emits observation.
        """
        assert self.current_skill is not None, "Session not initialized"
        node = self.graph.nodes[self.current_skill]

        # 1. Update Behavioral Proctor
        proctor_res = self.proctor.record_turn(
            latency_ms=latency_ms,
            transcript=transcript,
            is_contradiction_probe=is_contradiction_probe,
            passed_contradiction_probe=passed_contradiction_probe
        )
        current_bii = proctor_res["current_bii"]

        # 2. Handle Devil's Advocate Resolution
        # 2. Handle Devil's Advocate Resolution
        if self.state == SessionState.DEVILS_ADVOCATE:
            if observation == 1:
                self.devils_advocate_results.append(1.0)
                # Successful defense confirms mastery!
                node.p_l = max(node.p_l, node.config.mastery_threshold + 0.05)
                self.graph.propagate_mastery(self.current_skill)
            else:
                self.devils_advocate_results.append(-1.0)
                # Failed defense collapses mastery
                node.p_l = min(node.p_l, node.config.deficiency_threshold)

            self.devils_advocate_active = False
            # Transition out of Devil's Advocate to next skill
            return self._advance_to_next_skill(reason="Devils Advocate challenge concluded.")


        # 3. Standard BKT & Scaffolding Update
        bkt_res = node.update(observation=observation, scaffolding_level=self.current_scaffolding_level)

        # 4. Update MIRT Ability
        mirt_item = ItemParameters(
            item_id=f"{self.current_skill}_step_{bkt_res['step']}",
            prompt=transcript,
            difficulty=0.5 * (self.current_scaffolding_level + 1),
            discrimination={self.current_skill: 1.0}
        )
        self.mirt.update_ability(mirt_item, observation=observation)

        # 5. Check for Mastery Surge -> Trigger Devil's Advocate
        if bkt_res["is_surge"] and not self.devils_advocate_active:
            self.state = SessionState.DEVILS_ADVOCATE
            self.devils_advocate_active = True
            return PolicyDirective(
                next_action="DEVILS_ADVOCATE",
                current_state=self.state,
                skill_code=self.current_skill,
                scaffolding_level=0,
                prompt_directive=(
                    f"Candidate exhibited high mastery on {self.current_skill}. "
                    "Deploy the Devil's Advocate protocol: deliberately challenge their architectural choice "
                    "with a severe edge case or constraint to verify authentic understanding."
                ),
                bii=current_bii,
                current_mastery=node.p_l
            )

        # 6. Branch on Observation Success / Failure
        if observation == 1:
            # Candidate answered correctly!
            if node.status == MasteryStatus.MASTERED:
                # Skill mastered -> propagate across graph and advance
                self.graph.propagate_mastery(self.current_skill)
                return self._advance_to_next_skill(reason=f"Skill '{self.current_skill}' MASTERED.")
            else:
                # Still in progress -> deepen exploration
                return PolicyDirective(
                    next_action="DEEPEN_EXPLORATION",
                    current_state=self.state,
                    skill_code=self.current_skill,
                    scaffolding_level=self.current_scaffolding_level,
                    prompt_directive=f"Good progress on {self.current_skill}. Ask a deeper follow-up on failure modes or edge-case handling.",
                    bii=current_bii,
                    current_mastery=node.p_l
                )
        else:
            # Candidate struggled -> Step up Scaffolding Ladder
            if self.current_scaffolding_level < 3:
                self.current_scaffolding_level += 1
                state_map = {
                    1: SessionState.SCAFFOLDING_L1,
                    2: SessionState.SCAFFOLDING_L2,
                    3: SessionState.SCAFFOLDING_L3
                }
                self.state = state_map[self.current_scaffolding_level]
                
                scaffold_prompts = {
                    1: f"Give a subtle Socratic conceptual nudge on {self.current_skill} without giving away the solution.",
                    2: f"Provide a concrete partial scenario or skeleton on {self.current_skill} to guide their thinking.",
                    3: f"Present a binary architectural trade-off choice on {self.current_skill} for them to evaluate."
                }

                return PolicyDirective(
                    next_action="SCAFFOLD",
                    current_state=self.state,
                    skill_code=self.current_skill,
                    scaffolding_level=self.current_scaffolding_level,
                    prompt_directive=scaffold_prompts[self.current_scaffolding_level],
                    bii=current_bii,
                    current_mastery=node.p_l
                )
            else:
                # Scaffolding exhausted (Level 3 failed) -> conclude skill as unmastered
                return self._advance_to_next_skill(reason=f"Max scaffolding reached on '{self.current_skill}'. Moving to next concept.")

    def _advance_to_next_skill(self, reason: str) -> PolicyDirective:
        """Transitions to the next optimal skill in the knowledge graph."""
        self.current_scaffolding_level = 0
        next_skill = self.graph.get_next_recommended_skill()

        if next_skill:
            self.current_skill = next_skill
            self.state = SessionState.ACTIVE
            return PolicyDirective(
                next_action="NEXT_SKILL",
                current_state=self.state,
                skill_code=self.current_skill,
                scaffolding_level=0,
                prompt_directive=f"Transition smoothly to the next architectural topic: {self.current_skill}. {reason}",
                bii=self.proctor.bii,
                current_mastery=self.graph.nodes[self.current_skill].p_l
            )
        else:
            self.state = SessionState.COMPLETED
            return PolicyDirective(
                next_action="CONCLUDE_SESSION",
                current_state=self.state,
                skill_code="COMPLETED",
                scaffolding_level=0,
                prompt_directive="All topics completed. Conclude the interview conversationally and warmly.",
                bii=self.proctor.bii,
                current_mastery=1.0
            )

    def generate_final_session_report(self) -> Dict:
        """Assembles final scores, CPF, and hiring recommendation."""
        skills_summary = [
            SkillEvaluationSummary(
                skill_code=code,
                weight=1.0 / len(self.graph.nodes),
                final_mastery=node.p_l,
                scaffolding_counts={1: 0, 2: 0, 3: 0}
            )
            for code, node in self.graph.nodes.items()
        ]

        devils_score = sum(self.devils_advocate_results) / max(1, len(self.devils_advocate_results)) if self.devils_advocate_results else 0.0

        score_res = self.scorer.calculate_final_score(
            skills=skills_summary,
            bii=self.proctor.bii,
            devils_advocate_score=devils_score
        )

        return {
            "session_state": self.state.value,
            "final_score": score_res["final_score"],
            "recommendation": score_res["recommendation"],
            "behavioral_integrity_index": score_res["behavioral_integrity_index"],
            "passed_proctoring": score_res["passed_proctoring"],
            "skills": {code: round(node.p_l, 4) for code, node in self.graph.nodes.items()}
        }
