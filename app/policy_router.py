# pyrefly: ignore [missing-import]
"""
Policy Router & Session Finite State Machine (FSM).
Orchestrates:
- Scaffolding Ladder (L0 -> L1 -> L2 -> L3)
- Devil's Advocate challenge protocol on mastery surges
- Topic progression via Knowledge Graph
- Directive generation for the LLM interviewer (Alex)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any

from app.bkt_engine import BKTNode, SeniorityTier, MasteryStatus
from app.graph_engine import KnowledgeGraph, build_dynamic_pillar_graph

# Graceful optional imports for upcoming Phase 4 & Phase 5 engines
try:
    from app.mirt_engine import MIRTEngine, ItemParameters, get_discrimination_for_pillar
except ImportError:
    MIRTEngine = None

try:
    from app.proctor_engine import ProctorEngine
except ImportError:
    ProctorEngine = None


class SessionState(str, Enum):
    READY = "READY"
    ACTIVE = "ACTIVE"
    SCAFFOLDING_L1 = "SCAFFOLDING_L1"
    SCAFFOLDING_L2 = "SCAFFOLDING_L2"
    SCAFFOLDING_L3 = "SCAFFOLDING_L3"
    DEVILS_ADVOCATE = "DEVILS_ADVOCATE"
    COMPLETED = "COMPLETED"


@dataclass
class PolicyDirective:
    """Actionable instruction emitted after every turn for the LLM interviewer."""
    next_action: str                 # 'SCAFFOLD', 'DEEPEN_EXPLORATION', 'DEVILS_ADVOCATE', 'NEXT_SKILL', 'CONCLUDE_SESSION'
    current_state: SessionState
    skill_code: str
    scaffolding_level: int           # 0 to 3
    prompt_directive: str           # Plain-English prompt for Alex
    bii: float                       # Behavioral Integrity Index (1.0 = clean)
    current_mastery: float           # Current P(L)


class FallbackProctor:
    """Minimal proctor fallback until Phase 5 proctor_engine is built."""
    def __init__(self):
        self.bii = 1.0

    def record_turn(self, **kwargs) -> Dict[str, Any]:
        return {"current_bii": self.bii, "flags": []}


class PolicyRouter:
    """Deterministic Interview Finite State Machine (FSM)."""

    def __init__(
        self,
        seniority: SeniorityTier = SeniorityTier.MID,
        graph: Optional[KnowledgeGraph] = None
    ):
        self.seniority = seniority
        self.graph = graph or KnowledgeGraph(seniority=seniority)
        self.state = SessionState.READY
        self.current_skill: Optional[str] = None
        self.current_scaffolding_level: int = 0
        self.devils_advocate_active: bool = False
        self.devils_advocate_results: List[float] = []

        # Proctor & MIRT hooks
        self.proctor = ProctorEngine() if ProctorEngine else FallbackProctor()
        self.mirt = MIRTEngine() if MIRTEngine else None

    def initialize_session(self, initial_pillars: List[Dict]) -> PolicyDirective:
        """Initializes the session graph with matched competency pillars."""
        self.graph = build_dynamic_pillar_graph(initial_pillars, seniority=self.seniority)
        
        # Pick first optimal skill
        first_skill = self.graph.get_next_recommended_skill()
        if not first_skill and self.graph.nodes:
            first_skill = list(self.graph.nodes.keys())[0]

        self.current_skill = first_skill
        self.state = SessionState.ACTIVE
        self.current_scaffolding_level = 0

        return PolicyDirective(
            next_action="START_TOPIC",
            current_state=self.state,
            skill_code=self.current_skill,
            scaffolding_level=0,
            prompt_directive=(
                f"Begin the technical evaluation with an open-ended question on {self.current_skill}. "
                "Assess their high-level architectural understanding without hints."
            ),
            bii=self.proctor.bii,
            current_mastery=self.graph.nodes[self.current_skill].p_l if self.current_skill else 0.40
        )

    def process_turn(
        self,
        observation: int,
        latency_ms: float = 800.0,
        transcript: str = "",
        is_contradiction_probe: bool = False,
        passed_contradiction_probe: Optional[bool] = None,
        estimated_difficulty: Optional[float] = None
    ) -> PolicyDirective:

        
        """
        Core FSM update cycle called on every candidate turn.
        1. Updates proctor telemetry
        2. Resolves Devil's Advocate challenges if active
        3. Updates BKT mastery & scaffolding
        4. Detects surges
        5. Returns actionable directive
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
        current_bii = proctor_res.get("current_bii", 1.0)

        # 2. Handle Devil's Advocate Resolution
        if self.state == SessionState.DEVILS_ADVOCATE:
            if observation == 1:
                self.devils_advocate_results.append(1.0)
                # Successful defense confirms mastery!
                node.p_l = max(node.p_l, node.config.mastery_threshold + 0.05)
                self.graph.propagate_mastery(self.current_skill)
                reason = f"Candidate successfully defended {self.current_skill} under adversarial pressure! Mastery locked."
            else:
                self.devils_advocate_results.append(-1.0)
                # Failed defense collapses mastery
                node.p_l = min(node.p_l, node.config.deficiency_threshold)
                reason = f"Candidate failed Devil's Advocate probe on {self.current_skill}. Mastery collapsed."

            self.devils_advocate_active = False
            # Transition to next skill after Devil's Advocate challenge
            return self._advance_to_next_skill(reason=reason)

        # 3. Standard BKT & Scaffolding Update
        bkt_res = node.update(
            observation=observation,
            scaffolding_level=self.current_scaffolding_level
        )

        # 4. Optional MIRT Ability Update (Phase 4 hook)
        if self.mirt and hasattr(self.mirt, "update_ability"):
            diff_scalar = estimated_difficulty or (0.3 * (self.current_scaffolding_level + 1))
            self.mirt.update_ability(
                skill=self.current_skill,
                observation=observation,
                difficulty=diff_scalar
            )

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

        # 6. Branch on Answer Correctness
        if observation == 1:
            # Candidate answered correctly!
            if node.status == MasteryStatus.MASTERED:
                self.graph.propagate_mastery(self.current_skill)
                return self._advance_to_next_skill(reason=f"Skill '{self.current_skill}' MASTERED.")
            else:
                # Skill still in progress -> deepen exploration
                return PolicyDirective(
                    next_action="DEEPEN_EXPLORATION",
                    current_state=self.state,
                    skill_code=self.current_skill,
                    scaffolding_level=self.current_scaffolding_level,
                    prompt_directive=(
                        f"Good answer on {self.current_skill}. Ask a deeper follow-up on "
                        "edge cases, failure modes, or trade-offs to test depth."
                    ),
                    bii=current_bii,
                    current_mastery=node.p_l
                )
        else:
            # Candidate struggled -> Step up Scaffolding Ladder (L1 -> L2 -> L3)
            if self.current_scaffolding_level < 3:
                self.current_scaffolding_level += 1
                state_map = {
                    1: SessionState.SCAFFOLDING_L1,
                    2: SessionState.SCAFFOLDING_L2,
                    3: SessionState.SCAFFOLDING_L3,
                }
                self.state = state_map[self.current_scaffolding_level]

                scaffold_prompts = {
                    1: f"Give a subtle Socratic conceptual nudge on {self.current_skill} without revealing the answer.",
                    2: f"Provide a concrete partial scenario or skeleton on {self.current_skill} to guide their thinking.",
                    3: f"Present a binary architectural trade-off choice on {self.current_skill} for them to evaluate directly.",
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
                # Max scaffolding reached (failed L3) -> concede topic as unmastered
                return self._advance_to_next_skill(
                    reason=f"Max scaffolding reached on '{self.current_skill}'. Candidate could not solve even with full assistance."
                )

    def _advance_to_next_skill(self, reason: str) -> PolicyDirective:
        """Transitions to the next optimal skill in the Knowledge Graph."""
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
                prompt_directive=f"Transition smoothly to the next architectural topic: {self.current_skill}. ({reason})",
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
