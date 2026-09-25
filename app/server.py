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

from app.models import (
    LockedRubric,
    GradingResult,
    BKTTelemetry,
    TurnResponse,
    TurnAuditRecord,
    FinalAuditReport,
    SpotCheckRecord,
    MultiSkillDossier,
)
from app.bkt import update_mastery, DEFAULT_PRIOR, DEPTH_LEVEL_PARAMS
from app.policy import evaluate_policy, PolicyDecision
from app.gemini_service import (
    generate_question_and_rubric,
    generate_devils_advocate_question,
    grade_answer_with_rubric,
    extract_skills_from_intro,
    detect_mentioned_skills,
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
        self.spot_check_question_index: int = 0
        self.paused_primary_rubric: LockedRubric = None


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

            # =========================================================================
            # CASE 1: CANDIDATE SUBMITS INTRODUCTION (Turn 0)
            # =========================================================================
            if session.phase == "INTRO":
                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": "Analyzing introduction and compiling candidate skill queue..."
                }))

                extracted = extract_skills_from_intro(candidate_answer)
                session.skill_queue = extracted if extracted else ["Python", "FastAPI"]
                session.current_skill = session.skill_queue.pop(0)
                session.phase = "PRIMARY_SKILL"
                session.current_depth = "L1"
                session.prior_mastery = DEFAULT_PRIOR
                session.attempts = 0

                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": f"Skill queue built: {session.current_skill}, {', '.join(session.skill_queue)}. Locking initial rubric for {session.current_skill}..."
                }))

                session.active_rubric = generate_question_and_rubric(session.current_skill, "L1")

                response_payload = TurnResponse(
                    event="turn_completed",
                    session_phase="PRIMARY_SKILL",
                    active_skill=session.current_skill,
                    queued_skills=session.skill_queue,
                    completed_skills=session.completed_skills,
                    candidate_answer=candidate_answer,
                    next_question=session.active_rubric.question_text,
                    next_rubric=session.active_rubric,
                    skill_state="IN_PROGRESS",
                )
                await websocket.send_text(json.dumps(response_payload.model_dump()))
                continue

            # =========================================================================
            # CASE 2: CANDIDATE ANSWERS A SPOT-CHECK QUESTION (1 of 2 or 2 of 2)
            # =========================================================================
            if session.phase == "SPOT_CHECK":
                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": f"Grading spot-check response for {session.active_spot_check.skill_name}..."
                }))

                grading: GradingResult = grade_answer_with_rubric(session.active_rubric, candidate_answer)

                if session.spot_check_question_index == 1:
                    # Save Answer 1 & move to Question 2
                    session.active_spot_check.answer_1 = candidate_answer
                    session.active_spot_check.verdict_1 = grading.verdict
                    session.spot_check_question_index = 2

                    await websocket.send_text(json.dumps({
                        "event": "status_update",
                        "message": f"Generating Question 2 of 2 (Production Trade-offs) for {session.active_spot_check.skill_name}..."
                    }))

                    spot_rubric_2 = generate_spot_check_question(
                        skill=session.active_spot_check.skill_name,
                        question_index=2,
                        previous_context=candidate_answer,
                    )
                    session.active_rubric = spot_rubric_2

                    response_payload = TurnResponse(
                        event="turn_completed",
                        session_phase="SPOT_CHECK",
                        active_skill=session.current_skill,
                        queued_skills=session.skill_queue,
                        completed_skills=session.completed_skills,
                        spot_check_progress=f"Spot-Check 2/2: {session.active_spot_check.skill_name}",
                        candidate_answer=candidate_answer,
                        grading=grading,
                        next_question=spot_rubric_2.question_text,
                        next_rubric=spot_rubric_2,
                        skill_state="IN_PROGRESS",
                    )
                    await websocket.send_text(json.dumps(response_payload.model_dump()))
                    continue

                else:
                    # Question 2 answered: Finalize Spot-Check
                    session.active_spot_check.answer_2 = candidate_answer
                    session.active_spot_check.verdict_2 = grading.verdict

                    # Determine hands-on status
                    v1 = session.active_spot_check.verdict_1
                    v2 = session.active_spot_check.verdict_2
                    if "correct" in (v1, v2) or (v1 == "partial" and v2 == "partial"):
                        session.active_spot_check.final_verdict = "VERIFIED_HANDS_ON"
                        session.active_spot_check.rationale = "Candidate demonstrated concrete architectural mechanics under targeted spot-checking."
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
                        queued_skills=session.skill_queue,
                        completed_skills=session.completed_skills,
                        spot_check_progress=None,
                        candidate_answer=candidate_answer,
                        grading=grading,
                        next_question=session.active_rubric.question_text,
                        next_rubric=session.active_rubric,
                        skill_state=session.state,
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
                "message": f"Evaluating answer for {session.current_skill} against frozen rubric..."
            }))

            # Step 1: Grade against locked rubric
            grading: GradingResult = grade_answer_with_rubric(session.active_rubric, candidate_answer)

            # Step 2: Compute BKT Math
            params = DEPTH_LEVEL_PARAMS[session.current_depth]
            posterior, next_mastery = update_mastery(
                prior=session.prior_mastery,
                verdict=grading.verdict,
                depth_level=session.current_depth,
            )
            delta = round(next_mastery - session.prior_mastery, 4)

            telemetry = BKTTelemetry(
                turn_number=session.turn_number,
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

            if session.is_da_turn and grading.verdict == "correct":
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
                    "gemini.grade_answer_with_rubric()",
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

                    session.active_rubric = generate_question_and_rubric(session.current_skill, "L1")

                    response_payload = TurnResponse(
                        event="turn_completed",
                        session_phase="PRIMARY_SKILL",
                        active_skill=session.current_skill,
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
                    )
                    await websocket.send_text(json.dumps(response_payload.model_dump()))
                    continue
                else:
                    # All skills completed! Compile MultiSkillDossier
                    session.phase = "COMPLETED"
                    dossier = MultiSkillDossier(
                        primary_skills_reports=session.primary_skills_reports,
                        spot_check_records=session.spot_check_records,
                        verified_skills=[r.skill for r in session.primary_skills_reports if r.final_state == "VERIFIED"]
                        + [s.skill_name for s in session.spot_check_records if s.final_verdict == "VERIFIED_HANDS_ON"],
                        shallow_skills=[r.skill for r in session.primary_skills_reports if r.final_state == "SHALLOW"],
                        unverified_buzzwords=[s.skill_name for s in session.spot_check_records if s.final_verdict == "UNVERIFIED_BUZZWORD"],
                        executive_summary=f"Multi-Skill assessment complete. Tested {len(session.completed_skills)} primary skills and {len(session.spot_check_records)} in-flight spot checks.",
                    )

                    response_payload = TurnResponse(
                        event="turn_completed",
                        session_phase="COMPLETED",
                        active_skill=session.current_skill,
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
                    )
                    await websocket.send_text(json.dumps(response_payload.model_dump()))
                    continue

            # Step 5: Normal Next Question Generation (Devil's Advocate or Depth Progression)
            if policy_decision.action == "TRIGGER_DEVILS_ADVOCATE":
                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": f"⚠️ UNUSUAL MASTERY SURGE on {session.current_skill}! Triggering Devil's Advocate cross-examination..."
                }))
                session.is_da_turn = True
                session.has_faced_da = True
                next_rubric = generate_devils_advocate_question(
                    skill=session.current_skill,
                    depth_level=session.current_depth,
                    previous_context=candidate_answer,
                )
            else:
                session.is_da_turn = False
                session.current_depth = policy_decision.next_depth
                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": f"Locking evaluation rubric for {session.current_skill} ({session.current_depth})..."
                }))
                next_rubric = generate_question_and_rubric(session.current_skill, session.current_depth)

            # Step 6: In-Flight Skill Interceptor Scan
            detected_skills = detect_mentioned_skills(candidate_answer)
            surprise_skills = []
            for s in detected_skills:
                s_clean = s.strip()
                s_lower = s_clean.lower()
                if (
                    s_lower != session.current_skill.lower()
                    and s_lower not in [c.lower() for c in session.completed_skills]
                    and s_lower not in [q.lower() for q in session.skill_queue]
                    and s_lower not in [sc.skill_name.lower() for sc in session.spot_check_records]
                ):
                    surprise_skills.append(s_clean)

            if surprise_skills:
                # Intercept! Pause primary progression and ask Spot-Check Q1
                intercept_skill = surprise_skills[0]
                session.phase = "SPOT_CHECK"
                session.paused_primary_rubric = next_rubric
                session.spot_check_question_index = 1
                session.active_spot_check = SpotCheckRecord(skill_name=intercept_skill, question_1="")

                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": f"⚡ In-flight technology detected: '{intercept_skill}'! Pausing {session.current_skill} for a 2-question hands-on spot-check..."
                }))

                spot_rubric_1 = generate_spot_check_question(
                    skill=intercept_skill,
                    question_index=1,
                    previous_context=candidate_answer,
                )
                session.active_spot_check.question_1 = spot_rubric_1.question_text
                session.active_rubric = spot_rubric_1

                response_payload = TurnResponse(
                    event="turn_completed",
                    session_phase="SPOT_CHECK",
                    active_skill=session.current_skill,
                    queued_skills=session.skill_queue,
                    completed_skills=session.completed_skills,
                    spot_check_progress=f"Spot-Check 1/2: {intercept_skill}",
                    candidate_answer=candidate_answer,
                    grading=grading,
                    telemetry=telemetry,
                    policy_action="TRIGGER_SPOT_CHECK",
                    policy_reason=f"Candidate casually referenced '{intercept_skill}'. Probing practical hands-on experience.",
                    skill_state=session.state,
                    next_question=spot_rubric_1.question_text,
                    next_rubric=spot_rubric_1,
                )
                await websocket.send_text(json.dumps(response_payload.model_dump()))
                continue

            # Routine turn completion (no intercept)
            session.active_rubric = next_rubric
            response_payload = TurnResponse(
                event="turn_completed",
                session_phase="PRIMARY_SKILL",
                active_skill=session.current_skill,
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
            )
            await websocket.send_text(json.dumps(response_payload.model_dump()))

    except WebSocketDisconnect:
        print("[Session Disconnected] Candidate closed connection.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.server:app", host="127.0.0.1", port=8000, reload=True)
