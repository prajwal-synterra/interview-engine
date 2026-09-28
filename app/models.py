"""
Pydantic Data Models & Schemas (v2: Token & Cost Governance)
Defines contracts for Rubric-Lock, BKT Telemetry, Multi-Skill Queue,
Token & Financial Tracking, and Session Pacing.
"""

from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


# --- Telemetry & Financial Cost Governance ---

class TokenUsage(BaseModel):
    """Tracks prompt tokens, completion tokens, and real-time USD billing."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    gemini_api_calls: int = 0
    backend_requests: int = 0

    def add(self, prompt: int, completion: int):
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens += (prompt + completion)
        self.gemini_api_calls += 1
        # Gemini Flash-Lite Pricing: $0.075 / 1M prompt, $0.30 / 1M completion
        cost = (self.prompt_tokens / 1_000_000 * 0.075) + (self.completion_tokens / 1_000_000 * 0.30)
        self.estimated_cost_usd = round(cost, 6)


class LockedRubric(BaseModel):
    """Rubric-Lock contract ('The Law'). Frozen in memory before candidate sees the question."""
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
    Discrete Grader Output with Combined In-Flight Skill Detection.
    Merges grading and skill scanning into a single LLM call to cut API calls in half.
    """
    verdict: Literal["correct", "partial", "incorrect"]
    rationale: str = Field(description="Clear, concise explanation of why this answer meets or violates the rubric")
    matched_criteria: List[str] = Field(default_factory=list, description="Specific required criteria that were hit")
    violated_misconceptions: List[str] = Field(default_factory=list, description="Specific prohibited assumptions that were detected")
    mentioned_technologies: List[str] = Field(
        default_factory=list, 
        description="Specific external architectural tools, message brokers, databases, or systems explicitly mentioned in passing (e.g., Redis, Kafka, Celery, Docker, Kubernetes). Exclude standard programming keywords."
    )


class BKTTelemetry(BaseModel):
    """Real-time mathematical snapshot emitted after each Bayesian update."""
    turn_number: int
    attempts :int = 1
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
    candidate_name: Optional[str] = Field(
        default=None,
        description="Candidate's first name if explicitly stated in intro (e.g. 'Prajwal', 'Alex'). Null if not mentioned."
    )
    skills: List[str] = Field(
        description="List of primary tech skills, frameworks, or tools mentioned"
    )


class SpotCheckRecord(BaseModel):
    """Audit record for a single targeted in-flight spot-check probe."""
    skill_name: str
    question: str
    answer: str = ""
    verdict: Optional[Literal["correct", "incorrect", "partial"]] = None
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
    """Overarching dossier aggregating all completed primary skills, spot-checks, and financial metrics."""
    primary_skills_reports: List[FinalAuditReport] = Field(default_factory=list)
    spot_check_records: List[SpotCheckRecord] = Field(default_factory=list)
    verified_skills: List[str] = Field(default_factory=list)
    shallow_skills: List[str] = Field(default_factory=list)
    unverified_buzzwords: List[str] = Field(default_factory=list)
    executive_summary: str = ""
    
    # Financial & Time Telemetry
    candidate_name: Optional[str] = None
    total_backend_calls: int = 0
    total_gemini_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    session_duration_seconds: int = 0


class TurnResponse(BaseModel):
    """Payload sent over WebSocket to frontend on turn events."""
    event: str = "turn_completed"
    session_phase: Literal["INTRO", "PRIMARY_SKILL", "SPOT_CHECK", "COMPLETED"] = "PRIMARY_SKILL"
    active_skill: Optional[str] = None
    attempts:int =1
    queued_skills: List[str] = Field(default_factory=list)
    completed_skills: List[str] = Field(default_factory=list)
    spot_check_progress: Optional[str] = None
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
    
    # Live Token & Audit Telemetry
    candidate_name: Optional[str] = None
    total_backend_calls: int = 0
    total_gemini_calls: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    elapsed_seconds: int = 0
