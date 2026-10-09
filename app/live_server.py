"""
Live Server Orchestrator.
Central real-time pipeline connecting candidate browser, Gemini Live voice streaming,
Shadow Evaluator, Policy Router FSM, BKT, MIRT, Proctor, Vector Pillar Matching,
PostgreSQL database persistence, and Dual Report Generation.
"""

import os
import re
import sys
import json
import time
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv

# Ensure .env is resolved reliably from workspace root
ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(ENV_PATH)

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from app.logger import log_event, log_speech, log_shadow_eval, log_bkt_math, log_policy, log_proctor
from app.speech_cleaner import clean_candidate_transcript
from app.bkt_engine import SeniorityTier
from app.policy_router import PolicyRouter
from app.mirt_engine import MIRTEngine, get_radar_summary
from app.proctor_engine import BehavioralProctorEngine
from app.evaluator_engine import evaluate_candidate_response
from app.vector_service import match_candidate_topics, SEED_PILLARS
from app.ecosystem_service import (
    detect_ecosystems_from_intro,
    bind_pillars_to_ecosystems,
    get_ecosystem_directive,
    get_evaluator_ecosystem_context
)
from app.report_generator import (
    generate_student_report,
    generate_evaluator_report,
    save_reports_to_disk,
    calculate_master_score
)
from app.db_service import DatabaseService

# ── Global State & Services ──
db_service = DatabaseService()
ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}
LATEST_SESSION_ID: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes PostgreSQL connection and tables on startup."""
    await db_service.initialize()
    log_event("SERVER_START", "FastAPI Live Server initialized with PostgreSQL database.")
    yield


app = FastAPI(title="Socratic Interview Engine", lifespan=lifespan)

# Mount Static & Templates
TEMPLATES_DIR = ROOT_DIR / "templates"
STATIC_DIR = ROOT_DIR / "static"
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="frontend-assets")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ── System Instruction Prompts for Alex ──

def get_system_prompt_for_level(level: str) -> str:
    """Returns Alex's core interviewer persona calibrated by candidate seniority."""
    base = (
        "You are Alex, an elite Principal Software Architect conducting an interactive Socratic technical interview. "
        "Your mission is to rigorously assess the candidate's engineering depth, architecture trade-offs, and systems thinking.\n\n"
        "RULES OF ENGAGEMENT:\n"
        "1. Speak ONLY in natural, spoken English. Never use Markdown formatting, bullet points, asterisks, or code blocks in speech.\n"
        "2. Keep your spoken responses concise and conversational (2-3 sentences max per turn). Never lecture or deliver monologues.\n"
        "3. You are the interviewer, NOT a teaching assistant or trivia chatbot. If the candidate asks you riddles, questions about vehicles/animals, or off-topic questions, politely deflect and bring them back to the active technical topic.\n"
        "4. Follow the pedagogical directives provided with each turn (hints, scenarios, or challenges).\n"
        "5. Speak with professional warmth, curiosity, and high technical rigor."
    )
    if level == "STUDENT":
        return base + "\nCandidate Level: STUDENT / INTERN. Be encouraging, focus on fundamental data structures, web basics, and clarity of thought."
    elif level == "HARD":
        return base + "\nCandidate Level: SENIOR / STAFF. Challenge them with production scale, distributed failure modes, race conditions, and architectural trade-offs."
    else:
        return base + "\nCandidate Level: MID-LEVEL PROFESSIONAL. Probe practical system design, caching strategies, API protocols, and concurrency."


def check_for_offtopic_candidate_prompts(text: str) -> str:
    """Detects evasive candidate questions or prompt injection attempts."""
    text_lower = text.lower()
    offtopic_patterns = [
        r"which is (?:stronger|better|faster|more powerful)",
        r"(?:truck|lorry|car|bus|tiger|lion).*(?:stronger|faster|better)",
        r"tell me a joke",
        r"what is the weather",
        r"answer my question",
        r"ignore (?:all )?previous instructions",
    ]
    for pat in offtopic_patterns:
        if re.search(pat, text_lower):
            return (
                "[URGENT DEFLECTION DIRECTIVE: The candidate asked an off-topic or evasive question. "
                "Do NOT answer it. Deflect politely, remind them this is a technical architecture interview, "
                "and ask your original technical question again.]"
            )
    return "[OFF-TOPIC DEFLECTION GUARD: Maintain interviewer authority. Do not let candidate deviate from technical topic.]"


# ==============================================================================
# HTML Frontend Endpoints
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/telemetry", response_class=HTMLResponse)
async def get_telemetry_page(request: Request):
    return templates.TemplateResponse("telemetry.html", {"request": request})

@app.get("/reports", response_class=HTMLResponse)
async def get_reports_page(request: Request):
    return templates.TemplateResponse("reports.html", {"request": request})

@app.get("/logs", response_class=HTMLResponse)
async def get_logs_page(request: Request):
    return templates.TemplateResponse("logs.html", {"request": request})

@app.get("/architecture", response_class=HTMLResponse)
async def get_architecture_page(request: Request):
    return templates.TemplateResponse("architecture.html", {"request": request})

@app.get("/console", response_class=HTMLResponse)
async def get_console_page():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h3>Developer Console not built yet. Run 'npm run build' in /frontend</h3>", status_code=404)


# ==============================================================================
# REST API Endpoints
# ==============================================================================

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "gemini_live_model": os.getenv("GEMINI_LIVE_VOICE_MODEL", "gemini-3.8-live")
    }

@app.get("/api/session/active")
async def get_active_session():
    if LATEST_SESSION_ID and LATEST_SESSION_ID in ACTIVE_SESSIONS:
        sess = ACTIVE_SESSIONS[LATEST_SESSION_ID]
        return {
            "session_id": sess["session_id"],
            "candidate_name": sess["candidate_name"],
            "level": sess["level"],
            "status": "ACTIVE"
        }
    return JSONResponse(status_code=404, content={"message": "No active session"})

@app.get("/api/session/{session_id}/state")
async def get_session_state(session_id: str):
    sess = ACTIVE_SESSIONS.get(session_id)
    if sess:
        return {
            "session_id": sess["session_id"],
            "candidate_name": sess["candidate_name"],
            "level": sess["level"],
            "is_paused": sess.get("is_paused", False),
            "turns_history": sess.get("turns_history", []),
            "telemetry": sess.get("telemetry", {}),
            "active_topic": sess["get_active_topic"](),
            "session_phase": sess["get_session_phase"]()
        }
    db_sess = await db_service.get_session(session_id)
    if db_sess:
        turns = await db_service.get_turns(session_id)
        return {"session": db_sess, "turns_history": turns}
    raise HTTPException(status_code=404, detail="Session not found")

@app.get("/api/session/{session_id}/turns")
async def get_session_turns(session_id: str):
    turns = await db_service.get_turns(session_id)
    return {"session_id": session_id, "turns": turns}

@app.get("/api/reports")
async def get_all_reports_list():
    reports = await db_service.get_all_reports()
    return {"reports": reports}

@app.get("/api/reports/{session_id}")
async def get_session_reports(session_id: str):
    rep = await db_service.get_final_reports(session_id)
    if rep:
        return rep
    raise HTTPException(status_code=404, detail="Reports not found for session")

@app.get("/api/session/{session_id}/compacted-cards")
async def get_session_compacted_cards(session_id: str):
    cards = await db_service.get_compacted_topic_cards(session_id)
    return {"session_id": session_id, "cards": cards}

@app.get("/api/logs")
async def get_server_logs(limit: int = 250):
    log_file = ROOT_DIR / "logs" / "interview_engine.log"
    if not log_file.exists():
        return {"lines": []}
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = [line.rstrip() for line in f.readlines()]
            return {"lines": lines[-limit:]}
    except Exception as e:
        return {"lines": [f"[ERROR] Could not read log file: {e}"]}

@app.get("/api/vector/pillars")
async def get_vector_pillars():
    return {"pillars": SEED_PILLARS}


# ==============================================================================
# WebSocket Real-Time Voice Interview Orchestrator
# ==============================================================================

@app.websocket("/ws/interview")
async def websocket_interview(websocket: WebSocket):
    await websocket.accept()

    # 1. Accept Initial Session Handshake
    init_data = await websocket.receive_json()
    level = init_data.get("level", "MEDIUM").upper()
    candidate_name = init_data.get("name", "Candidate")

    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    await db_service.create_session(
        session_id=session_id,
        candidate_name=candidate_name,
        seniority_tier=level,
        detected_ecosystem="GENERAL_SYSTEMS"
    )
    log_event("SESSION_START", f"Candidate '{candidate_name}' connected (Session: {session_id}). Tier: {level}")

    tier_map = {
        "STUDENT": SeniorityTier.STUDENT,
        "MEDIUM": SeniorityTier.MID,
        "HARD": SeniorityTier.SENIOR_STAFF
    }
    tier = tier_map.get(level, SeniorityTier.MID)

    # 2. Initialize Cognitive Engines
    policy_router = PolicyRouter(seniority=tier)
    proctor = BehavioralProctorEngine()
    mirt = MIRTEngine(initial_theta={
        "algorithms": 0.0,
        "system_design": 0.0,
        "concurrency": 0.0,
        "databases": 0.0,
        "distributed_systems": 0.0
    })

    # Default starter skills
    initial_skills = [
        {"pillar_id": "SYSTEM_DESIGN", "name": "System Architecture"},
        {"pillar_id": "CONCURRENCY", "name": "Concurrency Models"},
        {"pillar_id": "DISTRIBUTED_CACHING", "name": "Distributed Caching"}
    ]
    policy_router.initialize_session(initial_skills)

    # Session Socratic State
    matched_pillars: List[Dict] = []
    active_topic = "GENERAL"
    session_phase = "INTRO"  # INTRO -> DEEP_DIVE -> WRAPPING_UP
    turns_on_active_topic = 0
    ecosystem_summary: Dict = {}
    pillar_ecosystem_map: Dict = {}

    is_paused = False
    turns_history: List[Dict] = []
    devils_advocate_results: List[int] = []

    telemetry = {
        "current_skill": active_topic,
        "bkt_mastery": 0.40,
        "scaffolding_level": 0,
        "state": "ACTIVE",
        "latency_ms": 0,
        "proctor_bii": 1.0,
        "skills": []
    }

    # Register in global memory directory
    global LATEST_SESSION_ID
    LATEST_SESSION_ID = session_id
    ACTIVE_SESSIONS[session_id] = {
        "session_id": session_id,
        "candidate_name": candidate_name,
        "level": level,
        "is_paused": is_paused,
        "turns_history": turns_history,
        "telemetry": telemetry,
        "get_active_topic": lambda: active_topic,
        "get_session_phase": lambda: session_phase
    }

    async def broadcast_telemetry(active_module: str = ""):
        try:
            curr_fsm = policy_router.state.value if hasattr(policy_router, 'state') else "QUESTION"
            await websocket.send_json({
                "event": "telemetry_update",
                "active_module": active_module,
                "telemetry": {
                    **telemetry,
                    "session_id": session_id,
                    "active_topic": active_topic,
                    "session_phase": session_phase,
                    "fsm_state": curr_fsm,
                    "mirt_radar": get_radar_summary(mirt)
                }
            })
        except Exception:
            pass

    await websocket.send_json({"event": "session_started", "session_id": session_id})
    await broadcast_telemetry("LiveServer")

    # 3. Connect to Google Gemini Live Voice
    live_api_key = os.getenv("GEMINI_LIVE_VOICE_API_KEY") or os.getenv("GEMINI_API_KEY")
    live_model = os.getenv("GEMINI_LIVE_VOICE_MODEL", "gemini-3.8-live")
    live_client = genai.Client(api_key=live_api_key) if (genai and live_api_key) else None

    if not live_client:
        log_event("GEMINI_LIVE_ERROR", "Gemini Client could not be initialized. API key missing.")
        return

    system_instruction = get_system_prompt_for_level(level)
    live_config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(language_code="en-US"),
        input_audio_transcription=types.AudioTranscriptionConfig(language_codes=["en-US", "en-IN"]),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        system_instruction=types.Content(parts=[types.Part.from_text(text=system_instruction)]),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)
        )
    )

    alex_latest_question = "Welcome the candidate warmly and ask them to introduce their technical background."
    alex_finish_timestamp = None

    try:
        async with live_client.aio.live.connect(model=live_model, config=live_config) as session:
            log_event("GEMINI_LIVE", f"Connected to Gemini Live model {live_model}")

            _mic_queue: asyncio.Queue = asyncio.Queue(maxsize=256)
            candidate_transcript_buffer = ""
            alex_turn_complete_event = asyncio.Event()

            # ── Loop 1: Audio Forward Loop (Browser -> Gemini Live) ──
            async def mic_forward_loop():
                try:
                    while True:
                        chunk = await _mic_queue.get()
                        if chunk is None:
                            break
                        if session and not is_paused:
                            await session.send_realtime_input(
                                audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                            )
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    log_event("MIC_FORWARD_ERROR", str(e))

            # ── Loop 2: Gemini Receive Loop (Gemini Live -> Browser) ──
            async def gemini_receive_loop():
                nonlocal alex_latest_question, alex_finish_timestamp, candidate_transcript_buffer
                try:
                    async for response in session.receive():
                        sc = response.server_content
                        if not sc:
                            continue

                        # Handle Alex Spoken Response
                        if sc.model_turn:
                            for part in sc.model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    # Forward raw PCM audio bytes to browser
                                    await websocket.send_bytes(part.inline_data.data)
                                if part.text:
                                    alex_latest_question += part.text
                                    await websocket.send_json({"event": "ai_transcript_chunk", "text": part.text})

                        # Handle Candidate Speech Transcription
                        if hasattr(sc, "input_transcription") and sc.input_transcription:
                            tx = sc.input_transcription.text
                            if tx:
                                candidate_transcript_buffer += tx
                                await websocket.send_json({"event": "candidate_transcript_chunk", "text": tx})

                        # Handle Interruption
                        if sc.interrupted:
                            log_event("GEMINI_LIVE", "Alex was interrupted by candidate speech.")
                            await websocket.send_json({"event": "ai_interrupted"})

                        # Handle Turn Completion
                        if sc.turn_complete:
                            alex_finish_timestamp = time.time()
                            alex_turn_complete_event.set()
                            await websocket.send_json({"event": "turn_complete"})

                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    log_event("GEMINI_RECEIVE_ERROR", str(e))

            mic_task = asyncio.create_task(mic_forward_loop())
            recv_task = asyncio.create_task(gemini_receive_loop())

            # Send Greeting to Alex
            await session.send_client_content(
                turns=[types.Content(role="user", parts=[types.Part.from_text(
                    text=f"The candidate has entered the room. Greet {candidate_name} by name and invite them to share their engineering background."
                )])]
            )
            await websocket.send_json({"event": "ai_turn_start"})

            # ── Background Shadow Pipeline ──
            async def run_shadow_pipeline(user_text: str, question: str):
                nonlocal active_topic, turns_on_active_topic, session_phase
                sub_time = time.time()
                latency_ms = int((sub_time - alex_finish_timestamp) * 1000) if alex_finish_timestamp else 1800
                telemetry["latency_ms"] = latency_ms

                curr_skill = active_topic if active_topic != "GENERAL" else "SYSTEM_DESIGN"
                eco_context = get_evaluator_ecosystem_context(curr_skill, pillar_ecosystem_map)

                # 1. Shadow Evaluator (Gemini 2.5 Flash ~1.5s)
                await broadcast_telemetry("Shadow Evaluator")
                try:
                    eval_res = await evaluate_candidate_response(
                        skill=curr_skill,
                        interviewer_question=question,
                        candidate_answer=user_text,
                        scaffolding_level=policy_router.current_scaffolding_level,
                        ecosystem_context=eco_context
                    )
                except Exception as e:
                    log_event("SHADOW_EVAL_ERROR", str(e))
                    eval_res = {"observation": 1, "depth_score": 0.65, "estimated_difficulty": 0.4, "rubric_items": []}

                obs = eval_res.get("observation", 1)
                depth = eval_res.get("depth_score", 0.65)
                est_diff = eval_res.get("estimated_difficulty", 0.4)
                log_shadow_eval(len(turns_history) + 1, curr_skill, obs, depth, eval_res.get("summary", ""))

                # Send real-time Shadow Evaluator result to frontend
                await websocket.send_json({
                    "event": "shadow_eval_completed",
                    "observation": obs,
                    "depth_score": depth,
                    "estimated_difficulty": est_diff,
                    "summary": eval_res.get("summary", ""),
                    "skill": curr_skill
                })

                # 2. Behavioral Proctor (BII Anti-Cheat)
                await broadcast_telemetry("Behavioral Proctor")
                proctor_turn = proctor.record_turn(
                    transcript=user_text,
                    latency_ms=latency_ms,
                    is_contradiction_probe=False,
                    accepted_contradiction=False
                )
                telemetry["proctor_bii"] = proctor.bii
                log_proctor(proctor.bii, 1.0 - proctor.bii, proctor_turn.verdict)

                # 3. Policy Router FSM & BKT Bayesian Update
                await broadcast_telemetry("Policy Router FSM")
                prev_state = policy_router.state.value
                directive = policy_router.process_candidate_turn(
                    observation=obs,
                    latency_ms=latency_ms,
                    transcript=user_text,
                    estimated_difficulty=est_diff
                )
                log_policy(prev_state, policy_router.state.value, directive.action, directive.prompt_directive)
                telemetry["policy_directive"] = directive.action
                telemetry["fsm_state"] = policy_router.state.value

                # Send real-time Policy Router decision to frontend
                await websocket.send_json({
                    "event": "policy_directive_selected",
                    "action": directive.action,
                    "fsm_state": policy_router.state.value,
                    "directive": directive.prompt_directive
                })

                # 4. MIRT Ability Calibration
                mirt.update_ability(
                    skill=curr_skill,
                    difficulty=est_diff,
                    observation=obs
                )

                # Get node posterior
                node = policy_router.graph.nodes.get(curr_skill)
                prior_val = node.history[-1].prior_mastery if (node and node.history) else 0.40
                post_val = node.p_l if node else 0.40
                telemetry["bkt_mastery"] = round(post_val, 3)

                # 5. Persist Turn Telemetry to PostgreSQL
                turn_idx = len(turns_history) + 1
                await db_service.log_turn_telemetry(
                    session_id=session_id,
                    turn_index=turn_idx,
                    topic=curr_skill,
                    interviewer_prompt=question,
                    candidate_transcript=user_text,
                    latency_ms=latency_ms,
                    evaluator_observation=obs,
                    depth_score=depth,
                    bkt_prior=prior_val,
                    bkt_posterior=post_val,
                    proctor_bii=proctor.bii
                )

                # Record turn in local history
                turns_history.append({
                    "turn_index": turn_idx,
                    "skill": curr_skill,
                    "question": question,
                    "candidate_answer": user_text,
                    "observation": obs,
                    "scaffolding_level": policy_router.current_scaffolding_level,
                    "bkt_posterior": post_val,
                    "latency_ms": latency_ms,
                    "proctor_flags": proctor_turn.flags_triggered
                })

                turns_on_active_topic += 1

                # Check Topic Transition Thresholds (Mastery >= 0.85 or turns >= 3)
                if post_val >= 0.85 or turns_on_active_topic >= 3:
                    card_status = "MASTERED" if post_val >= 0.85 else "INCOMPLETE"
                    await db_service.save_compacted_topic_card(
                        session_id=session_id,
                        topic_code=curr_skill,
                        turns_spent=turns_on_active_topic,
                        final_mastery_p_l=post_val,
                        status=card_status,
                        verdict_summary=f"Evaluated across {turns_on_active_topic} turns with final mastery {post_val:.2f}."
                    )
                    next_skill = policy_router.graph.get_next_recommended_skill()
                    if next_skill:
                        log_event("TOPIC_TRANSITION", f"Advancing from {curr_skill} to {next_skill}")
                        active_topic = next_skill
                        policy_router.current_skill = next_skill
                        turns_on_active_topic = 0
                    else:
                        session_phase = "WRAPPING_UP"

                await broadcast_telemetry("Turn Complete")

            # ── Main WebSocket Incoming Message Loop ──
            while True:
                msg = await websocket.receive()

                # Handle Binary Audio Frames (Microphone PCM)
                if "bytes" in msg and msg["bytes"]:
                    if not is_paused:
                        try:
                            _mic_queue.put_nowait(msg["bytes"])
                        except asyncio.QueueFull:
                            pass
                    continue

                # Handle JSON Control Messages
                if "text" in msg and msg["text"]:
                    data = json.loads(msg["text"])
                    ev = data.get("event") or data.get("action")

                    if ev == "pause_interview":
                        is_paused = True
                        await websocket.send_json({"event": "pause_state_changed", "is_paused": True})
                        log_event("INTERVIEW_PAUSE", "Session paused by user.")
                        continue

                    elif ev == "resume_interview":
                        is_paused = False
                        await websocket.send_json({"event": "pause_state_changed", "is_paused": False})
                        log_event("INTERVIEW_RESUME", "Session resumed by user.")
                        continue

                    elif ev == "finish_interview":
                        log_event("INTERVIEW_FINISH", "Candidate triggered finish interview.")
                        break

                    # Candidate Finished Speaking (either via mic end_of_speech or manual text submit)
                    raw_text = data.get("transcript") or data.get("text") or candidate_transcript_buffer
                    candidate_transcript_buffer = ""

                    user_text = clean_candidate_transcript(raw_text)
                    if not user_text or len(user_text.strip()) < 3:
                        continue

                    log_speech("Candidate", user_text)
                    await websocket.send_json({"event": "candidate_transcript", "text": user_text})

                    # ── Phase 1: INTRO ──
                    if session_phase == "INTRO":
                        log_event("INTRO_PROCESSING", "Processing candidate introduction.")
                        vector_res = await match_candidate_topics(user_text)
                        matched_pillars = vector_res.get("matched_pillars", [])

                        eco_res = detect_ecosystems_from_intro(user_text)
                        ecosystem_summary = eco_res
                        pillar_ecosystem_map = bind_pillars_to_ecosystems(matched_pillars, user_text)

                        # Build Dynamic Knowledge Graph
                        dynamic_graph = policy_router.graph
                        for p in matched_pillars:
                            pid = p["pillar_id"]
                            if pid not in dynamic_graph.nodes:
                                dynamic_graph.add_skill(pid, description=p.get("domain", ""))

                        active_topic = matched_pillars[0]["pillar_id"] if matched_pillars else "SYSTEM_DESIGN"
                        policy_router.current_skill = active_topic

                        # Persist Session Blueprint to DB
                        await db_service.update_session_blueprint(
                            session_id=session_id,
                            intro_blueprint={
                                "intro_text": user_text,
                                "matched_pillars": matched_pillars,
                                "pillar_ecosystem_map": pillar_ecosystem_map,
                                "ecosystem_summary": ecosystem_summary
                            },
                            detected_ecosystem=ecosystem_summary.get("primary_ecosystem", "GENERAL_SYSTEMS")
                        )

                        session_phase = "DEEP_DIVE"
                        eco_dir = get_ecosystem_directive(active_topic, pillar_ecosystem_map)

                        prompt_payload = (
                            f"The candidate introduced themselves as: '{user_text}'.\n"
                            f"Acknowledge their background warmly. Transition seamlessly into their first technical topic: {active_topic}.\n"
                            f"{eco_dir}\n"
                            "Ask an engaging open-ended architectural question to kick off the deep dive."
                        )

                    # ── Phase 2: DEEP_DIVE ──
                    elif session_phase == "DEEP_DIVE":
                        question_asked = alex_latest_question
                        alex_latest_question = ""
                        asyncio.create_task(run_shadow_pipeline(user_text, question_asked))

                        offtopic_guard = check_for_offtopic_candidate_prompts(user_text)
                        eco_dir = get_ecosystem_directive(active_topic, pillar_ecosystem_map)

                        prompt_payload = (
                            f"The candidate answered: '{user_text}'.\n"
                            f"{offtopic_guard}\n"
                            f"[ACTIVE TOPIC: {active_topic}]\n"
                            f"{eco_dir}\n"
                            "Respond Socratically as Alex the interviewer. Drill into edge cases or system trade-offs."
                        )

                    # ── Phase 3: WRAPPING_UP ──
                    else:
                        prompt_payload = (
                            f"The candidate answered: '{user_text}'.\n"
                            "Warmly conclude the interview. Thank them for their time and technical insights."
                        )

                    # Send next prompt payload to Alex
                    await session.send_client_content(
                        turns=[types.Content(role="user", parts=[types.Part.from_text(text=prompt_payload)])]
                    )
                    await websocket.send_json({"event": "ai_turn_start"})

            # Clean up loops
            _mic_queue.put_nowait(None)
            mic_task.cancel()
            recv_task.cancel()

    except WebSocketDisconnect:
        log_event("SESSION_DISCONNECT", f"WebSocket client disconnected for session {session_id}")
    except Exception as e:
        log_event("LIVE_SERVER_ERROR", f"Exception in websocket_interview: {e}")

    # ==========================================================================
    # Final Reports Generation & Persistence
    # ==========================================================================
    if turns_history:
        log_event("REPORT_GENERATION", "Generating final assessment reports...")
        skills_mastery = {
            k: v.p_l for k, v in policy_router.graph.nodes.items() if len(v.history) > 0
        } or {"SYSTEM_DESIGN": 0.65}

        scaffolding_events = [{"level": t.get("scaffolding_level", 0)} for t in turns_history]
        scoring = calculate_master_score(skills_mastery, scaffolding_events, proctor.bii, devils_advocate_results)

        mirt_radar = get_radar_summary(mirt)

        evaluator_md = generate_evaluator_report(
            session_id=session_id,
            candidate_name=candidate_name,
            seniority_level=level,
            turns_history=turns_history,
            skills_mastery=skills_mastery,
            proctor_bii=proctor.bii,
            mirt_radar=mirt_radar,
            ecosystem_info=ecosystem_summary,
            devils_advocate_results=devils_advocate_results
        )

        student_md = await generate_student_report(
            candidate_name=candidate_name,
            seniority_level=level,
            turns_history=turns_history,
            skills_mastery=skills_mastery,
            mirt_radar=mirt_radar,
            ecosystem_info=ecosystem_summary
        )

        # Save to disk
        save_reports_to_disk(session_id, student_md, evaluator_md)

        # Save to PostgreSQL
        await db_service.save_final_reports(
            session_id=session_id,
            student_compass_markdown=student_md,
            evaluator_audit_markdown=evaluator_md,
            hiring_verdict=scoring["verdict"],
            average_mastery=scoring["base_technical"],
            proctor_integrity_score=proctor.bii
        )

        try:
            await websocket.send_json({
                "event": "reports_generated",
                "student_report": student_md,
                "evaluator_report": evaluator_md,
                "hiring_verdict": scoring["verdict"]
            })
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.live_server:app", host="0.0.0.0", port=8000, reload=True)
