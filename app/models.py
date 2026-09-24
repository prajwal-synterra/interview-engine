"""
Pydantic Data Models & Schemas
Defines the contracts for Rubric-Lock, BKT Telemetry, and Session State.
"""


from typing import List, Literal, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


class LockedRubric(BaseModel):
    """ Rubric-Locak contract ("The law"). Forzen in memory before the candiate ever see the questions"""

    rubric_id : str = Field(default_factory=lambda:f"RUB-{uuid.uuid4().hex[:-8].upper()}")
    skill_name : str
    depth_level : str
    question_text : str
    required_criteria: List[str] = Field(
        description="Key conceptual facts or mechanics the candidate must demonstrate to pass this level"
    )
    prohibited_misconceptions: List[str] = Field(
        description="Common flawed assumption or buzzwords that disqualifiy full credits"  
    )
    is_devils_advocate: bool = False
    created_at : str = Field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))

class GradingResult(BaseModel):
    """
    Discrete Grader Output.
    Gemini is restricted to classification against the locked rubric.
    It NEVER computes numbers or mastery scores.
    """
    verdict: Literal["correct", "partial", "incorrect"]
    rationale:str =Field(description="Clear, concise explanation of why this answer meets or violates the rubric")
    matched_criteria: List[str] = Field(default_factory=list, description="Specific required criteria that were hit")
    violated_misconceptions: List[str] = Field(default_factory=list, description="Specific prohibited assumptions that were detected")

class BKTTelemetry(BaseModel):
    """
    Real-time 
    mathematical snapshot emitted after each Bayesian update.
    """

    turn_number:int
    depth_level :str
    verdict: Literal["correct", "partial", "incorrect"]
    prior: float
    guess_used: float
    slip_used: float
    learn_used: float
    posterior: float
    next_mastery: float
    delta: float

class TurnResponse(BaseModel):
    event: str = "turn_completed"
    candidate_answer: str
    grading: GradingResult
    telemetry: BKTTelemetry
    policy_action: str
    policy_reason: str
    skill_state: str
    next_question: Optional[str] = None
    next_rubric: Optional[LockedRubric] = None
    final_report: Optional[FinalAuditReport] = None


#audit data schemas

class TurnAuditRecord(BaseModel):
    """Detailed audit snapshot of a single question-answer cycle."""
    turn_number: int
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
    """Executive assessment report generated at the conclusion of an interview."""
    skill: str
    final_state: str  # VERIFIED, SHALLOW
    final_mastery: float
    total_turns: int
    da_triggered: bool
    da_defended: bool
    summary_headline: str
    turns: List[TurnAuditRecord]

    
