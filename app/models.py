"""
Pydantic Data Models & Schemas
Defines the contracts for Rubric-Lock, BKT Telemetry, and Multi-Skill Session State.
"""

from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


class LockedRubric(BaseModel):
    """Rubric-Lock contract ('The Law'). Frozen in memory before the candidate ever sees the questions."""
    rubric_id: str = Field(default_factory=lambda: f"RUB-{uuid.uuid4().hex[:8].upper()}")
    skill_name: str
    depth_level: str
    question_text: str
    required_criteria: List[str] = Field(
        description="Key conceptual facts or mechanics the candidate must demonstrate to pass this level"
    )
    prohibited_misconceptions: List[str] = Field(
        description="Common flawed assumptions or buzzwords that disqualify full credit"  
    )
    is_devils_advocate: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


class GradingResult(BaseModel):
    """
    Discrete Grader Output.
    Gemini is restricted to classification against the locked rubric.
    It NEVER computes numbers or mastery scores.
    """
    verdict: Literal["correct", "partial", "incorrect"]
    rationale: str = Field(description="Clear, concise explanation of why this answer meets or violates the rubric")
    matched_criteria: List[str] = Field(default_factory=list, description="Specific required criteria that were hit")
    violated_misconceptions: List[str] = Field(default_factory=list, description="Specific prohibited assumptions that were detected")


class BKTTelemetry(BaseModel):
    """Real-time mathematical snapshot emitted after each Bayesian update."""
    turn_number: int
    depth_level: str
    verdict: Literal["correct", "partial", "incorrect"]
    prior: float
    guess_used: float
    slip_used: float
    learn_used: float
    posterior: float
    next_mastery: float
    delta: float


# --- Skill Extraction & Interceptor Schemas --- 

class ExtractedSkills(BaseModel):
    """Structured output extracted from candidate's intro."""
    skills: List[str] = Field(
        description="List of primary tech skills, frameworks, or tools mentioned"
    )


class SpotCheckRecord(BaseModel):
    """Audit record for the 2-question in-flight spot-check when an unlisted skill is casually dropped."""
    skill_name: str
    question_1: str
    answer_1: str = ""
    verdict_1: Optional[Literal["correct", "incorrect", "partial"]] = None
    question_2: Optional[str] = None
    answer_2: Optional[str] = None
    verdict_2: Optional[Literal["correct", "incorrect", "partial"]] = None
    final_verdict: Literal["VERIFIED_HANDS_ON", "UNVERIFIED_BUZZWORD", "IN_PROGRESS"] = "IN_PROGRESS"
    rationale: str = ""


# --- Audit Data Schemas ---

class TurnAuditRecord(BaseModel):
    """Detailed audit snapshot of a single question-answer cycle."""
    turn_number: int
    skill_name: str = "General"
    depth_level: str
    question_text: str
    rubric_id: str
    candidate_answer: str
    verdict: Literal["correct", "partial", "incorrect"]
    rationale: str
    prior_mastery: float
    guess_used: float
    slip_used: float
    learn_used: float
    posterior: float
    next_mastery: float
    delta: float
    policy_action: str
    policy_reason: str
    pipeline_trace: List[str] = Field(default_factory=list)


class FinalAuditReport(BaseModel):
    """Executive assessment report for a single completed skill."""
    skill: str
    final_state: str  # VERIFIED, SHALLOW
    final_mastery: float
    total_turns: int
    da_triggered: bool
    da_defended: bool
    summary_headline: str
    turns: List[TurnAuditRecord]


class MultiSkillDossier(BaseModel):
    """Overarching dossier aggregating all completed primary skills and spot-checked tangents."""
    primary_skills_reports: List[FinalAuditReport] = Field(default_factory=list)
    spot_check_records: List[SpotCheckRecord] = Field(default_factory=list)
    verified_skills: List[str] = Field(default_factory=list)
    shallow_skills: List[str] = Field(default_factory=list)
    unverified_buzzwords: List[str] = Field(default_factory=list)
    executive_summary: str = ""


class TurnResponse(BaseModel):
    """Payload sent over WebSocket to frontend on turn events."""
    event: str = "turn_completed"
    session_phase: Literal["INTRO", "PRIMARY_SKILL", "SPOT_CHECK", "COMPLETED"] = "PRIMARY_SKILL"
    active_skill: Optional[str] = None
    queued_skills: List[str] = Field(default_factory=list)
    completed_skills: List[str] = Field(default_factory=list)
    spot_check_progress: Optional[str] = None  # e.g., "Spot-Check Q1 of 2: Redis"
    candidate_answer: Optional[str] = None
    grading: Optional[GradingResult] = None
    telemetry: Optional[BKTTelemetry] = None
    policy_action: Optional[str] = None
    policy_reason: Optional[str] = None
    skill_state: Optional[str] = None
    next_question: Optional[str] = None
    next_rubric: Optional[LockedRubric] = None
    final_report: Optional[FinalAuditReport] = None
    multi_skill_dossier: Optional[MultiSkillDossier] = None
