"""
FastAPI Server & WebSocket Orchestrator
Connects BKT Math, Policy Engine, and Gemini Rubric-Lock to an interactive Web UI.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import os

from app.models import LockedRubric, GradingResult, BKTTelemetry, TurnResponse, TurnAuditRecord, FinalAuditReport
from app.bkt import update_mastery, DEFAULT_PRIOR, DEPTH_LEVEL_PARAMS
from app.policy import evaluate_policy, PolicyDecision
from app.gemini_service import (
    generate_question_and_rubric,
    generate_devils_advocate_question,
    grade_answer_with_rubric,
)

app = FastAPI(title="Adaptive Technical Interview Engine (BKT + Rubric-Lock)")

# Mount static folder and Jinja2 templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Serves the main interview screen & live BKT inspector."""
    return templates.TemplateResponse(request=request,name="index.html")


class InterviewSession:
    """Maintains active interview state across turns."""
    def __init__(self, skill: str = "FastAPI"):
        self.skill = skill
        self.current_depth = "L1"
        self.prior_mastery = DEFAULT_PRIOR
        self.attempts = 0
        self.turn_number = 0
        self.state = "IN_PROGRESS"
        self.has_faced_da = False
        self.da_defended = False
        self.is_da_turn = False
        self.active_rubric: LockedRubric = None
        self.turns_history: list[TurnAuditRecord] = []


@app.websocket("/ws/interview")
async def interview_websocket(websocket: WebSocket):
    await websocket.accept()
    session = InterviewSession(skill="FastAPI")

    print(f"\n[Session Started] Initializing skill: {session.skill}")

    # Generate initial L1 Question & Locked Rubric
    session.active_rubric = generate_question_and_rubric(session.skill, session.current_depth)

    # Send initial setup event to frontend
    initial_payload = {
        "event": "session_started",
        "skill": session.skill,
        "depth_level": session.current_depth,
        "prior_mastery": session.prior_mastery,
        "question": session.active_rubric.question_text,
        "rubric": session.active_rubric.model_dump(),
        "is_devils_advocate": False,
    }
    await websocket.send_text(json.dumps(initial_payload))

    try:
        while True:
            # Wait for candidate to submit an answer
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            action = data.get("action")

            if action == "submit_answer":
                candidate_answer = data.get("answer", "").strip()
                if not candidate_answer:
                    continue

                session.turn_number += 1
                session.attempts += 1

                # Send processing status update
                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": "Evaluating answer against frozen rubric criteria..."
                }))

                # Step 1: Grade against locked rubric
                grading: GradingResult = grade_answer_with_rubric(session.active_rubric, candidate_answer)

                # Send math calculation status update
                await websocket.send_text(json.dumps({
                    "event": "status_update",
                    "message": f"Verdict: {grading.verdict.upper()}. Running Bayesian Knowledge Tracing update..."
                }))

                # Step 2: Compute BKT Math
                params = DEPTH_LEVEL_PARAMS[session.current_depth]
                posterior, next_mastery = update_mastery(
                    prior=session.prior_mastery,
                    verdict=grading.verdict,
                    depth_level=session.current_depth
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

                                # Track if Devil's Advocate was successfully defended
                if session.is_da_turn and grading.verdict == "correct":
                    session.da_defended = True

                # Record this turn in the audit trail
                audit_record = TurnAuditRecord(
                    turn_number=session.turn_number,
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
                        "policy.evaluate_policy()"
                    ]
                )
                session.turns_history.append(audit_record)

                # Update session mastery
                session.prior_mastery = next_mastery
                session.state = policy_decision.state

                # Step 4: Handle Next Question or Exit
                next_question = None
                next_rubric = None
                final_report = None

                if policy_decision.state in ("VERIFIED", "SHALLOW"):
                    # Interview completed! Compile final audit report
                    session.is_da_turn = False
                    
                    if policy_decision.state == "VERIFIED":
                        headline = f"Candidate certified as VERIFIED Senior Engineer in {session.skill} ({next_mastery*100:.1f}% Mastery). Successfully defended architectural trade-offs."
                    else:
                        headline = f"Assessment concluded. Competency ceiling recorded as SHALLOW in {session.skill} ({next_mastery*100:.1f}% Mastery) after {session.attempts} attempts."

                    final_report = FinalAuditReport(
                        skill=session.skill,
                        final_state=session.state,
                        final_mastery=next_mastery,
                        total_turns=session.turn_number,
                        da_triggered=session.has_faced_da,
                        da_defended=session.da_defended,
                        summary_headline=headline,
                        turns=session.turns_history
                    )
                elif policy_decision.action == "TRIGGER_DEVILS_ADVOCATE":
                    # Generate Devil's Advocate adversarial challenge
                    await websocket.send_text(json.dumps({
                        "event": "status_update",
                        "message": "⚠️ UNUSUAL MASTERY SURGE! Triggering Devil's Advocate cross-examination..."
                    }))
                    session.is_da_turn = True
                    session.has_faced_da = True
                    next_rubric = generate_devils_advocate_question(
                        skill=session.skill,
                        depth_level=session.current_depth,
                        previous_context=candidate_answer
                    )
                    session.active_rubric = next_rubric
                    next_question = next_rubric.question_text
                else:
                    # Routine progression (escalation or re-probe)
                    session.is_da_turn = False
                    session.current_depth = policy_decision.next_depth
                    await websocket.send_text(json.dumps({
                        "event": "status_update",
                        "message": f"Locking new evaluation rubric for {session.current_depth}..."
                    }))
                    next_rubric = generate_question_and_rubric(session.skill, session.current_depth)
                    session.active_rubric = next_rubric
                    next_question = next_rubric.question_text

                # Step 5: Send Complete Turn Response with Final Report (if finished)
                response_payload = TurnResponse(
                    event="turn_completed",
                    candidate_answer=candidate_answer,
                    grading=grading,
                    telemetry=telemetry,
                    policy_action=policy_decision.action,
                    policy_reason=policy_decision.reason,
                    skill_state=session.state,
                    next_question=next_question,
                    next_rubric=next_rubric,
                    final_report=final_report,
                )

                await websocket.send_text(json.dumps(response_payload.model_dump()))

    except WebSocketDisconnect:
        print("[Session Disconnected] Candidate closed connection.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.server:app", host="127.0.0.1", port=8000, reload=True)
