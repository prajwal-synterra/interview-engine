"""
FastAPI Server & WebSocket Orchestrator
Connects Multi-Skill Queue, BKT Math, Policy Engine, In-Flight Interceptor,
and Gemini Rubric-Lock to an interactive Web UI.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import time
from typing import Optional

from app.models import (
    LockedRubric,
    GradingResult,
    BKTTelemetry,
    TurnResponse,
    TurnAuditRecord,
    FinalAuditReport,
    SpotCheckRecord,
    MultiSkillDossier,
    TokenUsage
)
from app.bkt import update_mastery, DEFAULT_PRIOR, DEPTH_LEVEL_PARAMS
from app.policy import evaluate_policy, PolicyDecision
from app.gemini_service import (
    generate_question_and_rubric,
    generate_devils_advocate_question,
    grade_and_detect_skills,       # NEW: Merged 2-in-1 call (grades + extracts skills)
    extract_skills_from_intro,
    generate_spot_check_question,
)

app = FastAPI(title="Adaptive Technical Interview Engine (Multi-Skill & Spot-Check)")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Serves the main interview screen & live BKT inspector."""
    return templates.TemplateResponse(request=request, name="index.html")


class InterviewSession:
    """Maintains active interview state across multi-skill turns and spot checks."""
    def __init__(self):
        self.phase: str = "INTRO"  # INTRO, PRIMARY_SKILL, SPOT_CHECK, COMPLETED
        self.skill_queue: list[str] = []
        self.completed_skills: list[str] = []
        self.current_skill: str = "Introduction"
        self.current_depth: str = "L1"
        self.prior_mastery: float = DEFAULT_PRIOR
        self.attempts: int = 0
        self.turn_number: int = 0
        self.state: str = "IN_PROGRESS"
        self.has_faced_da: bool = False
        self.da_defended: bool = False
        self.is_da_turn: bool = False
        self.active_rubric: LockedRubric = None
        self.turns_history: list[TurnAuditRecord] = []
        self.primary_skills_reports: list[FinalAuditReport] = []

        # Spot-Check Interceptor State
        self.active_spot_check: SpotCheckRecord = None
        self.spot_check_records: list[SpotCheckRecord] = []
        self.max_spot_checks: int = 1
        self.spot_checks_count: int = 0
        self.spot_check_count: int = 0
        self.spot_check_question_index: int = 0
        self.paused_primary_rubric: LockedRubric = None

        # Telemetry & Time Governance
        self.candidate_name: Optional[str] = None
        self.backend_calls_count: int = 0
        self.gemini_calls_count: int = 0
        self.asked_questions_history: list[str] = []
        self.tokens = TokenUsage()
        self.start_time: float = time.time()


@app.websocket("/ws/interview")
async def interview_websocket(websocket: WebSocket):
    await websocket.accept()
    session = InterviewSession()

    print("\n[Session Started] Initializing Intro Warm-up Phase...")

    # Phase 0: Initial Introduction Prompt
    intro_question = (
        "Welcome to your adaptive technical evaluation! To begin, please introduce yourself, "
        "your engineering background, and the primary technologies, frameworks, and databases you've worked with recently."
    )

    initial_payload = {
        "event": "session_started",
        "session_phase": "INTRO",
        "active_skill": "Introduction",
        "queued_skills": [],
        "completed_skills": [],
        "question": intro_question,
        "rubric": None,
        "prior_mastery": session.prior_mastery,
    }
    await websocket.send_text(json.dumps(initial_payload))

    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            action = data.get("action")

            if action != "submit_answer":
                continue

            candidate_answer = data.get("answer", "").strip()
            if not candidate_answer:
                continue

            session.backend_calls_count += 1

            # =========================================================================
            # CASE 1: CANDIDATE SUBMITS INTRODUCTION (Turn 0)
            # =========================================================================
            if session.phase == "INTRO":
                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": "Analyzing introduction and compiling candidate skill queue..."
                }))

                extracted, candidate_name, p_token, c_token = extract_skills_from_intro(candidate_answer)
                session.candidate_name = candidate_name
                session.tokens.add(p_token, c_token)
                session.gemini_calls_count += 1
                session.skill_queue = extracted if extracted else ["Python", "FastAPI"]
                session.current_skill = session.skill_queue.pop(0)
                session.phase = "PRIMARY_SKILL"
                session.current_depth = "L1"
                session.prior_mastery = DEFAULT_PRIOR
                session.attempts = 0

                name_msg = f"Welcome, {session.candidate_name}! " if session.candidate_name else ""
                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": f"{name_msg}Skill queue ready: {session.current_skill}, {', '.join(session.skill_queue)}. Preparing first question for {session.current_skill}..."
                }))

                session.active_rubric, p_tok, c_tok = generate_question_and_rubric(
                    skill=session.current_skill, 
                    depth_level="L1",
                    previous_questions=session.asked_questions_history,
                    candidate_name=session.candidate_name,
                )
                session.tokens.add(p_tok, c_tok)
                session.gemini_calls_count += 1
                session.asked_questions_history.append(session.active_rubric.question_text)

                response_payload = TurnResponse(
                    event="turn_completed",
                    session_phase="PRIMARY_SKILL",
                    active_skill=session.current_skill,
                    attempts=0,
                    candidate_name=session.candidate_name,
                    total_backend_calls=session.backend_calls_count,
                    total_gemini_calls=session.gemini_calls_count,
                    queued_skills=session.skill_queue,
                    completed_skills=session.completed_skills,
                    candidate_answer=candidate_answer,
                    next_question=session.active_rubric.question_text,
                    next_rubric=session.active_rubric,
                    skill_state="IN_PROGRESS",
                    total_tokens=session.tokens.total_tokens,
                    estimated_cost_usd=session.tokens.estimated_cost_usd,
                    elapsed_seconds=int(time.time() - session.start_time),
                )
                await websocket.send_text(json.dumps(response_payload.model_dump()))
                continue

            # =========================================================================
            # CASE 2: CANDIDATE ANSWERS A SPOT-CHECK QUESTION (1 of 2 or 2 of 2)
            # =========================================================================
            # --- UPDATE NEEDED HERE (BLOCK 4: LEAN 1-QUESTION SPOT CHECK) ---
            if session.phase == "SPOT_CHECK":
                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": f"Grading spot-check response for {session.active_spot_check.skill_name}..."
                }))

                # Unified evaluation with token tracking
                grading, p_tok, c_tok = grade_and_detect_skills(session.active_rubric, candidate_answer)
                session.tokens.add(p_tok, c_tok)
                session.gemini_calls_count += 1

                # Finalize 1-Question Spot Check
                session.active_spot_check.answer = candidate_answer
                session.active_spot_check.verdict = grading.verdict

                if grading.verdict == "correct":
                    session.active_spot_check.final_verdict = "VERIFIED_HANDS_ON"
                    session.active_spot_check.rationale = "Candidate demonstrated concrete architectural mechanics under targeted spot-checking."
                elif grading.verdict == "partial":
                    session.active_spot_check.final_verdict = "VERIFIED_HANDS_ON"
                    session.active_spot_check.rationale = "Candidate demonstrated practical familiarity with minor omissions."
                else:
                    session.active_spot_check.final_verdict = "UNVERIFIED_BUZZWORD"
                    session.active_spot_check.rationale = "Candidate gave superficial or flawed answers; identified as name-drop."

                session.spot_check_records.append(session.active_spot_check)
                spot_finished_skill = session.active_spot_check.skill_name

                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": f"Spot-check complete for {spot_finished_skill} ({session.active_spot_check.final_verdict}). Resuming primary assessment for {session.current_skill}..."
                }))

                # Resume Primary Skill
                session.phase = "PRIMARY_SKILL"
                session.active_rubric = session.paused_primary_rubric
                session.active_spot_check = None

                response_payload = TurnResponse(
                    event="turn_completed",
                    session_phase="PRIMARY_SKILL",
                    active_skill=session.current_skill,
                    attempts=session.attempts,
                    candidate_name=session.candidate_name,
                    total_backend_calls=session.backend_calls_count,
                    total_gemini_calls=session.gemini_calls_count,
                    queued_skills=session.skill_queue,
                    completed_skills=session.completed_skills,
                    spot_check_progress=None,
                    candidate_answer=candidate_answer,
                    grading=grading,
                    next_question=session.active_rubric.question_text,
                    next_rubric=session.active_rubric,
                    skill_state=session.state,
                    total_tokens=session.tokens.total_tokens,
                    estimated_cost_usd=session.tokens.estimated_cost_usd,
                    elapsed_seconds=int(time.time() - session.start_time),
                )
                await websocket.send_text(json.dumps(response_payload.model_dump()))
                continue


            # =========================================================================
            # CASE 3: PRIMARY SKILL ASSESSMENT (BKT + Rubric-Lock + Policy Engine)
            # =========================================================================
            session.turn_number += 1
            session.attempts += 1

            await websocket.send_text(json.dumps({
                "event": "status_update",
                "message": f"Evaluating answer for {session.current_skill} (Single-Call Grading & Skill Scan)..."
            }))

            # Step 1: Combined Evaluation with 503 Crash Protection
            try:
                grading, p_tok, c_tok = grade_and_detect_skills(session.active_rubric, candidate_answer)
                session.tokens.add(p_tok, c_tok)
                session.gemini_calls_count += 1
            except Exception as e:
                print(f"[Gemini 503/API Spike Caught] {e}")
                # Revert attempt increments so candidate can retry without penalty
                session.turn_number -= 1
                session.attempts -= 1
                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": "⚠️ Gemini API is temporarily experiencing high demand. Please click 'Submit Answer' again in a moment."
                }))
                await websocket.send_text(json.dumps({
                    "event": "turn_completed",
                    "session_phase": session.phase,
                    "active_skill": session.current_skill,
                    "attempts": session.attempts,
                    "queued_skills": session.skill_queue,
                    "completed_skills": session.completed_skills,
                    "next_question": session.active_rubric.question_text,
                    "next_rubric": session.active_rubric,
                    "skill_state": session.state,
                    "total_tokens": session.tokens.total_tokens,
                    "estimated_cost_usd": session.tokens.estimated_cost_usd,
                    "elapsed_seconds": int(time.time() - session.start_time),
                }))
                continue

            # Step 2: Compute BKT Math
            params = DEPTH_LEVEL_PARAMS[session.current_depth]
            posterior, next_mastery = update_mastery(
                prior=session.prior_mastery,
                verdict=grading.verdict,
                depth_level=session.current_depth,
            )
            delta = round(next_mastery - session.prior_mastery, 4)

            # OLD CODE:
            # telemetry = BKTTelemetry(turn_number=session.turn_number, depth_level=session.current_depth, ...)
            telemetry = BKTTelemetry(
                turn_number=session.turn_number,
                attempts=session.attempts,  # NEW: Accurate attempt number
                depth_level=session.current_depth,
                verdict=grading.verdict,
                prior=session.prior_mastery,
                guess_used=params.guess,
                slip_used=params.slip,
                learn_used=params.learn,
                posterior=posterior,
                next_mastery=next_mastery,
                delta=delta,
            )


            # Step 3: Run Policy Engine
            policy_decision: PolicyDecision = evaluate_policy(
                depth_level=session.current_depth,
                prior=session.prior_mastery,
                next_mastery=next_mastery,
                attempts=session.attempts,
                verdict=grading.verdict,
                is_da_turn=session.is_da_turn,
                has_faced_da=session.has_faced_da,
            )

            if session.is_da_turn and policy_decision.state == "VERIFIED":
                session.da_defended = True

            # Record turn in audit history
            audit_record = TurnAuditRecord(
                turn_number=session.turn_number,
                skill_name=session.current_skill,
                depth_level=session.current_depth,
                question_text=session.active_rubric.question_text,
                rubric_id=session.active_rubric.rubric_id,
                candidate_answer=candidate_answer,
                verdict=grading.verdict,
                rationale=grading.rationale,
                prior_mastery=session.prior_mastery,
                guess_used=params.guess,
                slip_used=params.slip,
                learn_used=params.learn,
                posterior=posterior,
                next_mastery=next_mastery,
                delta=delta,
                policy_action=policy_decision.action,
                policy_reason=policy_decision.reason,
                pipeline_trace=[
                    "gemini.grade_and_detect_skills()",
                    "bkt.update_mastery()",
                    "policy.evaluate_policy()",
                ],
            )
            session.turns_history.append(audit_record)

            session.prior_mastery = next_mastery
            session.state = policy_decision.state

            # Step 4: Check if Current Skill Concluded
            if policy_decision.state in ("VERIFIED", "SHALLOW"):
                session.is_da_turn = False
                headline = (
                    f"Candidate certified as VERIFIED in {session.current_skill} ({next_mastery*100:.1f}% Mastery)."
                    if policy_decision.state == "VERIFIED"
                    else f"Assessment concluded for {session.current_skill}. Competency ceiling recorded as SHALLOW ({next_mastery*100:.1f}% Mastery)."
                )

                skill_report = FinalAuditReport(
                    skill=session.current_skill,
                    final_state=session.state,
                    final_mastery=next_mastery,
                    total_turns=session.attempts,
                    da_triggered=session.has_faced_da,
                    da_defended=session.da_defended,
                    summary_headline=headline,
                    turns=[t for t in session.turns_history if t.skill_name == session.current_skill],
                )
                session.primary_skills_reports.append(skill_report)
                session.completed_skills.append(session.current_skill)

                # Are there more skills in queue?
                if session.skill_queue:
                    session.current_skill = session.skill_queue.pop(0)
                    session.current_depth = "L1"
                    session.prior_mastery = DEFAULT_PRIOR
                    session.attempts = 0
                    session.has_faced_da = False
                    session.da_defended = False
                    session.is_da_turn = False
                    session.state = "IN_PROGRESS"

                    await websocket.send_text(json.dumps({
                        "event": "status_update",
                        "message": f"Advancing to next queued skill: {session.current_skill}. Locking L1 rubric..."
                    }))

                    session.active_rubric, p_tok, c_tok = generate_question_and_rubric(
                        skill=session.current_skill, 
                        depth_level="L1",
                        previous_questions=session.asked_questions_history,
                        candidate_name=session.candidate_name,
                    )
                    session.tokens.add(p_tok, c_tok)
                    session.gemini_calls_count += 1
                    session.asked_questions_history.append(session.active_rubric.question_text)

                    response_payload = TurnResponse(
                        event="turn_completed",
                        session_phase="PRIMARY_SKILL",
                        active_skill=session.current_skill,
                        attempts=0,
                        candidate_name=session.candidate_name,
                        total_backend_calls=session.backend_calls_count,
                        total_gemini_calls=session.gemini_calls_count,
                        queued_skills=session.skill_queue,
                        completed_skills=session.completed_skills,
                        candidate_answer=candidate_answer,
                        grading=grading,
                        telemetry=telemetry,
                        policy_action="NEXT_SKILL",
                        policy_reason=f"Transitioning to next queued skill: {session.current_skill}",
                        skill_state="IN_PROGRESS",
                        next_question=session.active_rubric.question_text,
                        next_rubric=session.active_rubric,
                        final_report=skill_report,
                        total_tokens=session.tokens.total_tokens,
                        estimated_cost_usd=session.tokens.estimated_cost_usd,
                        elapsed_seconds=int(time.time() - session.start_time),
                    )
                    await websocket.send_text(json.dumps(response_payload.model_dump()))
                    continue
                else:
                    # All skills completed! Compile MultiSkillDossier
                    session.phase = "COMPLETED"
                    duration = int(time.time() - session.start_time)
                    dossier = MultiSkillDossier(
                        primary_skills_reports=session.primary_skills_reports,
                        spot_check_records=session.spot_check_records,
                        verified_skills=[r.skill for r in session.primary_skills_reports if r.final_state == "VERIFIED"]
                        + [s.skill_name for s in session.spot_check_records if s.final_verdict == "VERIFIED_HANDS_ON"],
                        shallow_skills=[r.skill for r in session.primary_skills_reports if r.final_state == "SHALLOW"],
                        unverified_buzzwords=[s.skill_name for s in session.spot_check_records if s.final_verdict == "UNVERIFIED_BUZZWORD"],
                        executive_summary=f"Multi-Skill assessment complete. Tested {len(session.completed_skills)} primary skills and {len(session.spot_check_records)} spot check(s).",
                        candidate_name=session.candidate_name,
                        total_backend_calls=session.backend_calls_count,
                        total_gemini_calls=session.gemini_calls_count,
                        total_prompt_tokens=session.tokens.prompt_tokens,
                        total_completion_tokens=session.tokens.completion_tokens,
                        total_tokens=session.tokens.total_tokens,
                        estimated_cost_usd=session.tokens.estimated_cost_usd,
                        session_duration_seconds=duration,
                    )

                    response_payload = TurnResponse(
                        event="turn_completed",
                        session_phase="COMPLETED",
                        active_skill=session.current_skill,
                        attempts=session.attempts,
                        candidate_name=session.candidate_name,
                        total_backend_calls=session.backend_calls_count,
                        total_gemini_calls=session.gemini_calls_count,
                        queued_skills=[],
                        completed_skills=session.completed_skills,
                        candidate_answer=candidate_answer,
                        grading=grading,
                        telemetry=telemetry,
                        policy_action="INTERVIEW_COMPLETE",
                        policy_reason="All skills in queue completed.",
                        skill_state="COMPLETED",
                        final_report=skill_report,
                        multi_skill_dossier=dossier,
                        total_tokens=session.tokens.total_tokens,
                        estimated_cost_usd=session.tokens.estimated_cost_usd,
                        elapsed_seconds=duration,
                    )
                    await websocket.send_text(json.dumps(response_payload.model_dump()))
                    continue

            # Step 5: Normal Next Question Generation
            if policy_decision.action == "TRIGGER_DEVILS_ADVOCATE":
                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": f"⚠️ UNUSUAL MASTERY SURGE on {session.current_skill}! Triggering Devil's Advocate cross-examination..."
                }))
                session.is_da_turn = True
                session.has_faced_da = True
                next_rubric, p_tok, c_tok = generate_devils_advocate_question(
                    skill=session.current_skill,
                    depth_level=session.current_depth,
                    previous_context=candidate_answer,
                    candidate_name=session.candidate_name,
                )
                session.tokens.add(p_tok, c_tok)
                session.gemini_calls_count += 1
                session.asked_questions_history.append(next_rubric.question_text)
            else:
                session.is_da_turn = False
                session.current_depth = policy_decision.next_depth
                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": f"Locking evaluation rubric for {session.current_skill} ({session.current_depth})..."
                }))
                next_rubric, p_tok, c_tok = generate_question_and_rubric(
                    skill=session.current_skill, 
                    depth_level=session.current_depth,
                    previous_questions=session.asked_questions_history,
                    candidate_name=session.candidate_name,
                    previous_context=candidate_answer,
                )
                session.tokens.add(p_tok, c_tok)
                session.gemini_calls_count += 1
                session.asked_questions_history.append(next_rubric.question_text)

            # Step 6: In-Flight Skill Interceptor (Reads from grading directly, capped to max 1)
# --- UPDATE NEEDED HERE (BLOCK 3B: PROGRAMMATIC SPOT-CHECK GUARDS) ---
            # Step 6: In-Flight Skill Interceptor
            surprise_skills = []
            if session.spot_checks_count < session.max_spot_checks:
                for s in grading.mentioned_technologies:
                    s_clean = s.strip()
                    s_lower = s_clean.lower()
                    
                    # Guard 1: Drop submodules, function calls, file formats, or code syntax (e.g. tf.saved_model, torch.nn)
                    if any(char in s_clean for char in [".", "(", ")", "/", "\\", "_"]):
                        continue

                    # Guard 2: Drop subcomponents or aliases of current skill (e.g. tensorflow serving vs tensorflow)
                    current_lower = session.current_skill.lower()
                    if s_lower == current_lower or s_lower in current_lower or current_lower in s_lower:
                        continue

                    # Guard 3: Must not be already in queue, completed, or tested
                    if (
                        s_lower not in [c.lower() for c in session.completed_skills]
                        and s_lower not in [q.lower() for q in session.skill_queue]
                        and s_lower not in [sc.skill_name.lower() for sc in session.spot_check_records]
                    ):
                        surprise_skills.append(s_clean)
            if surprise_skills:
                # Intercept! Pause primary progression and ask 1 lean spot-check question
                intercept_skill = surprise_skills[0]
                session.phase = "SPOT_CHECK"
                session.paused_primary_rubric = next_rubric
                session.spot_checks_count += 1
                session.active_spot_check = SpotCheckRecord(skill_name=intercept_skill, question="")
                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": f"⚡ Unlisted technology detected: '{intercept_skill}'! Pausing {session.current_skill} for a 1-question hands-on spot-check..."
                }))
                spot_rubric, p_tok, c_tok = generate_spot_check_question(
                    skill=intercept_skill,
                    previous_context=candidate_answer,
                    candidate_name=session.candidate_name,
                )
                session.tokens.add(p_tok, c_tok)
                session.gemini_calls_count += 1
                session.asked_questions_history.append(spot_rubric.question_text)
                session.active_spot_check.question = spot_rubric.question_text
                session.active_rubric = spot_rubric
                response_payload = TurnResponse(
                    event="turn_completed",
                    session_phase="SPOT_CHECK",
                    active_skill=session.current_skill,
                    attempts=session.attempts,
                    candidate_name=session.candidate_name,
                    total_backend_calls=session.backend_calls_count,
                    total_gemini_calls=session.gemini_calls_count,
                    queued_skills=session.skill_queue,
                    completed_skills=session.completed_skills,
                    spot_check_progress=f"Spot-Check Probe: {intercept_skill}",
                    candidate_answer=candidate_answer,
                    grading=grading,
                    telemetry=telemetry,
                    policy_action="TRIGGER_SPOT_CHECK",
                    policy_reason=f"Candidate casually referenced '{intercept_skill}'. Probing practical hands-on experience.",
                    skill_state=session.state,
                    next_question=spot_rubric.question_text,
                    next_rubric=spot_rubric,
                    total_tokens=session.tokens.total_tokens,
                    estimated_cost_usd=session.tokens.estimated_cost_usd,
                    elapsed_seconds=int(time.time() - session.start_time),
                )
                await websocket.send_text(json.dumps(response_payload.model_dump()))
                continue

            # Routine turn completion (no intercept)
            session.active_rubric = next_rubric
            response_payload = TurnResponse(
                event="turn_completed",
                session_phase="PRIMARY_SKILL",
                active_skill=session.current_skill,
                attempts=session.attempts,
                candidate_name=session.candidate_name,
                total_backend_calls=session.backend_calls_count,
                total_gemini_calls=session.gemini_calls_count,
                queued_skills=session.skill_queue,
                completed_skills=session.completed_skills,
                candidate_answer=candidate_answer,
                grading=grading,
                telemetry=telemetry,
                policy_action=policy_decision.action,
                policy_reason=policy_decision.reason,
                skill_state=session.state,
                next_question=next_rubric.question_text,
                next_rubric=next_rubric,
                total_tokens=session.tokens.total_tokens,
                estimated_cost_usd=session.tokens.estimated_cost_usd,
                elapsed_seconds=int(time.time() - session.start_time),
            )
            await websocket.send_text(json.dumps(response_payload.model_dump()))


    except WebSocketDisconnect:
        print("[Session Disconnected] Candidate closed connection.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.server:app", host="127.0.0.1", port=8000, reload=True)
