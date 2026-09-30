"""
Live Socratic Audio Server & Multi-Agent Orchestration Hub.
Coordinates:
1. Gemini Live Audio API (Bidirectional audio-in/audio-out, native VAD & STT)
2. Shadow Evaluator (Gemini 2.5 Flash REST, async rubric evaluations)
3. BKT Mathematical Brain (bkt_engine.py)
4. Policy Router & Finite State Machine (policy_router.py)
5. Knowledge Graph (graph_engine.py)
6. Behavioral Proctor (proctor_engine.py)
7. Real-time Telemetry WebSocket stream
Document Reference: AIS-ARCH-2026-V3-MASTER
"""

import os
import time
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

from google import genai
from google.genai import types

from app.evaluator_engine import evaluate_candidate_response
from app.policy_router import PolicyRouter, SessionState
from app.bkt_engine import SeniorityTier

client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})

app = FastAPI(title="Socratic Interview Engine - Orchestration Hub")
BASE_DIR = Path(__file__).resolve().parent.parent


def get_system_prompt_for_level(level: str) -> str:
    level = level.upper()
    base_persona = (
        "You are 'Alex', an empathetic, brilliant, and friendly Principal Engineer conducting an adaptive voice technical interview. "
        "Speak naturally, concisely, and warmly—like a supportive senior colleague chatting over coffee.\n\n"
        "### PHASES:\n"
        "1. PHASE 1 (ICEBREAKER & INTRO): Start with a warm greeting. Welcome the candidate by name, ask them to introduce themselves and share what they enjoy building.\n"
        "2. PHASE 2 (CASUAL TALK): Chat casually for 1-2 turns to relax them.\n"
        "3. PHASE 3 (TRANSITION): Transition naturally to the technical exploration based on their level.\n"
        "4. PHASE 4 (SOCRATIC EXPLORATION): Ask open-ended questions about how things work under the hood. Keep questions concise so the candidate has room to speak.\n\n"
    )

    if level == "STUDENT":
        tier = (
            "### LEVEL: STUDENT / FRESHER\n"
            "- Tone: Encouraging and patient.\n"
            "- Focus: Fundamentals, simple data structures, basic web/API concepts, ML projects.\n"
        )
    elif level == "HARD":
        tier = (
            "### LEVEL: HARD / SENIOR / STAFF\n"
            "- Tone: Peer-to-peer, intellectually rigorous.\n"
            "- Focus: Distributed consensus, race conditions, memory bottlenecks, high-scale trade-offs.\n"
        )
    else:  # MEDIUM
        tier = (
            "### LEVEL: MEDIUM / MID-LEVEL (3-5 yrs)\n"
            "- Tone: Collaborative, professional.\n"
            "- Focus: System design, caching (Redis), database indexing, REST vs gRPC.\n"
        )

    return base_persona + tier


@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_file = BASE_DIR / "templates" / "index.html"
    if not index_file.exists():
        index_file = BASE_DIR / "app" / "index.html"
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))


import uuid
from app.logger import (
    log_event, log_speech, log_shadow_eval, log_bkt_math, log_policy, log_proctor, log_report
)
from app.report_generator import generate_student_report, generate_evaluator_report
from app.vector_service import match_candidate_topics, seed_competency_pillars
from app.db_service import (
    init_db, create_session, update_session_blueprint, save_compacted_topic_card,
    log_turn_telemetry, save_final_reports
)
from app.graph_engine import build_dynamic_pillar_graph, KnowledgeGraph, MasteryStatus
from app.ecosystem_service import (
    detect_ecosystems_from_intro, bind_pillars_to_ecosystems,
    get_ecosystem_directive, get_evaluator_ecosystem_context
)

@app.on_event("startup")
def startup_event():
    try:
        init_db()
        seed_competency_pillars()
    except Exception as e:
        print(f"[Startup Warning]: {e}")


def extract_topics_from_text(text: str) -> list[str]:
    """Extracts technical competency domains mentioned in candidate's introduction."""
    text_lower = text.lower()
    topics = []
    keywords = {
        "AI_SYSTEMS": ["ai", "agent", "llm", "gemini", "gpt", "rag", "langchain", "prompt", "interview agent"],
        "WEBSOCKETS_STREAMING": ["websocket", "streaming", "realtime", "audio stream", "socket", "low latency", "pcm", "audio"],
        "API_DESIGN": ["api", "rest", "fastapi", "flask", "endpoint", "graphql", "backend", "grpc"],
        "DATA_STRUCTURES": ["data structure", "array", "linked list", "tree", "graph", "hash map", "stack", "queue"],
        "SYSTEM_DESIGN": ["system design", "architecture", "microservice", "scalability", "load balancer", "cache", "redis"],
        "DATABASES": ["database", "sql", "postgresql", "mysql", "mongodb", "indexing", "query", "nosql"],
        "CONCURRENCY": ["concurrency", "thread", "async", "asyncio", "parallel", "multithreading", "lock", "mutex"],
        "ML_PIPELINES": ["machine learning", "model", "training", "pipeline", "classification", "nlp"]
    }
    for topic, words in keywords.items():
        if any(w in text_lower for w in words):
            topics.append(topic)
    if not topics:
        topics = ["AI_SYSTEMS", "DATA_STRUCTURES", "SYSTEM_DESIGN"]
    return topics


@app.websocket("/ws/interview")
async def websocket_interview(websocket: WebSocket):
    await websocket.accept()

    init_data = await websocket.receive_json()
    level = init_data.get("level", "MEDIUM").upper()
    candidate_name = init_data.get("name", "Candidate")

    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    try:
        create_session(session_id, candidate_name, level)
    except Exception as e:
        log_event("DB_SESSION_ERROR", str(e))

    log_event("SESSION_START", f"Candidate '{candidate_name}' connected (Session: {session_id}). Tier: {level}")

    tier_map = {
        "STUDENT": SeniorityTier.STUDENT,
        "MEDIUM": SeniorityTier.MID,
        "HARD": SeniorityTier.SENIOR_STAFF
    }
    tier = tier_map.get(level, SeniorityTier.MID)

    # Initialize Deterministic Algorithmic Brain
    policy_router = PolicyRouter(seniority=tier)
    if tier == SeniorityTier.STUDENT:
        initial_skills = [("ML_PIPELINES", 0.40), ("DATA_STRUCTURES", 0.45), ("WEB_FUNDAMENTALS", 0.35)]
    elif tier == SeniorityTier.SENIOR_STAFF:
        initial_skills = [("DISTRIBUTED_CONSENSUS", 0.25), ("CONCURRENCY", 0.30), ("SYSTEM_DESIGN", 0.35)]
    else:
        initial_skills = [("SYSTEM_DESIGN", 0.35), ("ML_PIPELINES", 0.35), ("API_DESIGN", 0.40)]

    policy_router.initialize_session(initial_skills)

    # Session Socratic State
    candidate_topics = []
    active_topic = "GENERAL"
    session_phase = "INTRO"  # "INTRO" -> "DEEP_DIVE" -> "WRAPPING_UP"
    turns_on_active_topic = 0
    ecosystem_summary: dict = {}
    pillar_ecosystem_map: dict = {}

    # Session Telemetry State
    telemetry = {
        "gemini_live_calls": 0,
        "gemini_rest_calls": 0,
        "total_audio_bytes": 0,
        "current_skill": policy_router.current_skill or "ONBOARDING",
        "bkt_mastery": 0.35,
        "scaffolding_level": 0,
        "state": "ACTIVE",
        "fraud_risk_score": 0.05,
        "fraud_status": "NOMINAL",
        "latency_ms": 0,
        "latest_rubric": None,
        "skills": [
            {"code": k, "mastery": round(v.p_l, 2), "status": v.status.value}
            for k, v in policy_router.graph.nodes.items()
        ]
    }

    async def broadcast_telemetry(active_module: str = ""):
        payload = {
            "event": "telemetry_update",
            "active_module": active_module,
            "telemetry": telemetry
        }
        try:
            await websocket.send_json(payload)
        except Exception:
            pass

    # Send initial telemetry state
    await broadcast_telemetry(active_module="server.py")

    system_instruction = get_system_prompt_for_level(level)
    model_name = "gemini-3.1-flash-live-preview"

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        system_instruction=types.Content(
            parts=[types.Part.from_text(text=system_instruction)]
        ),
    )

    alex_latest_question = "Welcome the candidate and ask them to introduce themselves."
    alex_finish_timestamp = None

    try:
        async with client.aio.live.connect(model=model_name, config=config) as session:
            log_event("GEMINI_LIVE", f"Connected to Gemini Live model {model_name}")

            # ── Shared state for the unified receive loop ──
            candidate_transcript_buffer = ""
            alex_is_speaking = False
            alex_turn_complete_event = asyncio.Event()
            turns_history = []

            async def run_shadow_pipeline(user_text: str, question: str):
                """Runs Shadow Evaluator REST, BKT, Policy Router, and Proctor in the background."""
                nonlocal alex_finish_timestamp, pillar_ecosystem_map, ecosystem_summary
                candidate_submit_time = time.time()
                latency_ms = int((candidate_submit_time - alex_finish_timestamp) * 1000) if alex_finish_timestamp else 2200
                telemetry["latency_ms"] = latency_ms

                current_skill = active_topic if active_topic != "GENERAL" else (policy_router.current_skill or "AI_SYSTEMS")
                if current_skill not in policy_router.graph.nodes:
                    policy_router.graph.add_skill(current_skill, description=f"Domain: {current_skill}")
                prev_state = policy_router.state.value

                # 1. Run Shadow Evaluator (Gemini 2.5 Flash REST API) with Active Ecosystem Context
                await broadcast_telemetry(active_module="Gemini REST Evaluator")
                eco_context = get_evaluator_ecosystem_context(current_skill, pillar_ecosystem_map)
                try:
                    eval_result = await evaluate_candidate_response(
                        skill=current_skill,
                        interviewer_question=question,
                        candidate_answer=user_text,
                        scaffolding_level=policy_router.current_scaffolding_level,
                        ecosystem_context=eco_context
                    )
                except Exception as e:
                    log_event("SHADOW_EVAL_ERROR", str(e))
                    eval_result = {"observation": 1, "depth_score": 0.6, "estimated_difficulty": 0.4, "rubric_items": []}

                telemetry["gemini_rest_calls"] += 1
                telemetry["latest_rubric"] = eval_result
                obs = eval_result.get("observation", 1)
                est_diff = eval_result.get("estimated_difficulty")

                node = policy_router.graph.nodes.get(current_skill)
                prior_val = round(node.p_l, 4) if node else 0.35

                # 2. Update Deterministic Policy Router, BKT & Real 5D MIRT Ability
                await broadcast_telemetry(active_module="Policy Router & BKT")
                directive = policy_router.process_candidate_turn(
                    observation=obs,
                    latency_ms=latency_ms,
                    transcript=user_text,
                    estimated_difficulty=est_diff
                )
                telemetry["mirt_theta"] = dict(policy_router.mirt.theta)

                last_rec = node.history[-1] if (node and node.history) else None

                # Build Comprehensive Turn Audit Record for Deep Inspection
                prior_mastery_val = round(last_rec.prior_mastery, 4) if last_rec else prior_val
                post_mastery_val = round(last_rec.posterior_mastery, 4) if last_rec else (round(node.p_l, 4) if node else prior_val)
                slip_val = round(last_rec.slip_used, 4) if last_rec else (node.config.p_s if node else 0.1)
                transit_val = node.config.p_t if node else 0.1
                raw_depth = eval_result.get("depth_score", 0.5)
                norm_depth = round(raw_depth / 100.0, 2) if raw_depth > 1.0 else round(float(raw_depth), 2)

                turn_audit = {
                    "turn_index": len(turns_history) + 1,
                    "timestamp": time.strftime("%H:%M:%S"),
                    "skill": current_skill,
                    "question": question,
                    "candidate_input": user_text,
                    "candidate_answer": user_text,
                    "latency_ms": latency_ms,
                    "evaluator": {
                        "observation": obs,
                        "observation_label": "PASSED (1)" if obs == 1 else "STRUGGLING (0)",
                        "depth_score": norm_depth,
                        "summary": eval_result.get("summary", ""),
                        "rubric_items": eval_result.get("rubric_items", []),
                        "recommended_probe": eval_result.get("recommended_probe", ""),
                        "raw_json": eval_result
                    },
                    "bkt": {
                        "skill": current_skill,
                        "step": len(node.history) if node else 1,
                        "observation": obs,
                        "prior": prior_mastery_val,
                        "posterior": post_mastery_val,
                        "prior_mastery": prior_mastery_val,
                        "posterior_mastery": post_mastery_val,
                        "effective_mastery": round(node.p_l, 4) if node else post_mastery_val,
                        "delta": round((node.p_l - prior_mastery_val), 4) if node else 0.0,
                        "slip_used": slip_val,
                        "transit": transit_val,
                        "p_t": transit_val,
                        "p_g": node.config.p_g if node else 0.25,
                        "p_s": slip_val,
                        "decay_rate": node.config.decay_rate if node else 0.8,
                        "status": node.status.value if node else "IN_PROGRESS",
                        "formula": f"P(L_t | obs={obs}) = [P(L_{prior_mastery_val}) * {'(1 - Ps)' if obs == 1 else 'Ps'}] / P(obs)"
                    },
                    "policy": {
                        "previous_state": prev_state,
                        "current_state": directive.current_state.value,
                        "next_action": directive.next_action,
                        "scaffolding_level": directive.scaffolding_level,
                        "prompt_directive": directive.prompt_directive or "No prompt directive required."
                    },
                    "proctor": {
                        "bii": round(policy_router.proctor.bii, 3),
                        "risk_score": round(1.0 - policy_router.proctor.bii, 2),
                        "fraud_risk_score": round(1.0 - policy_router.proctor.bii, 2),
                        "status": "FLAGGED" if policy_router.proctor.bii < 0.35 else "NOMINAL",
                        "latency_ms": latency_ms
                    }
                }
                turns_history.append(turn_audit)

                # Log all calculations to logs/interview_engine.log
                log_shadow_eval(turn_audit["turn_index"], current_skill, obs, norm_depth, eval_result.get("summary", ""))
                log_bkt_math(current_skill, prior_mastery_val, post_mastery_val, round(node.p_l - prior_mastery_val, 4), slip_val)
                log_policy(prev_state, directive.current_state.value, directive.next_action, directive.prompt_directive or "Normal Progression")
                log_proctor(policy_router.proctor.bii, 1.0 - policy_router.proctor.bii, "NOMINAL" if policy_router.proctor.bii >= 0.35 else "FLAGGED")

                # Persist turn telemetry to PostgreSQL database
                try:
                    log_turn_telemetry(
                        session_id=session_id,
                        turn_index=turn_audit["turn_index"],
                        topic=current_skill,
                        interviewer_prompt=question,
                        candidate_transcript=user_text,
                        latency_ms=latency_ms,
                        evaluator_observation=obs,
                        depth_score=norm_depth,
                        bkt_prior=prior_mastery_val,
                        bkt_posterior=post_mastery_val,
                        proctor_bii=round(policy_router.proctor.bii, 3)
                    )
                except Exception as e:
                    log_event("DB_LOG_ERROR", f"PostgreSQL turn telemetry error: {e}")

                # Update Telemetry snapshot
                if current_skill in policy_router.graph.nodes:
                    node = policy_router.graph.nodes[current_skill]
                    telemetry["bkt_mastery"] = round(node.p_l, 2)
                telemetry["current_skill"] = current_skill
                telemetry["scaffolding_level"] = directive.scaffolding_level
                telemetry["state"] = directive.current_state.value
                telemetry["fraud_risk_score"] = round(1.0 - policy_router.proctor.bii, 2)
                telemetry["fraud_status"] = "FLAGGED" if policy_router.proctor.bii < 0.35 else "NOMINAL"
                telemetry["skills"] = [
                    {"code": k, "mastery": round(v.p_l, 2), "status": v.status.value}
                    for k, v in policy_router.graph.nodes.items()
                ]
                telemetry["latest_turn_audit"] = turn_audit
                telemetry["turns_history"] = turns_history

                await broadcast_telemetry(active_module="bkt.py / graph.py")
                return directive

            # ── Unified Continuous Receive Loop ──
            async def gemini_receive_loop():
                nonlocal candidate_transcript_buffer, alex_latest_question, alex_finish_timestamp, alex_is_speaking
                alex_text = ""
                alex_audio_bytes = 0

                while True:
                    try:
                        async for response in session.receive():
                            server_content = response.server_content
                            if not server_content:
                                continue

                            # Candidate transcription
                            if server_content.interim_input_transcription and server_content.interim_input_transcription.text:
                                interim_chunk = server_content.interim_input_transcription.text
                                try:
                                    await websocket.send_json({"event": "candidate_interim_transcript", "text": interim_chunk})
                                except Exception:
                                    pass

                            if server_content.input_transcription and server_content.input_transcription.text:
                                chunk = server_content.input_transcription.text
                                candidate_transcript_buffer += chunk
                                try:
                                    await websocket.send_json({"event": "candidate_transcript_chunk", "text": chunk})
                                except Exception:
                                    pass

                            # Detect Alex starting to speak
                            if (server_content.output_transcription or server_content.model_turn) and not alex_is_speaking:
                                alex_is_speaking = True
                                alex_turn_complete_event.clear()
                                try:
                                    await websocket.send_json({"event": "ai_turn_start"})
                                except Exception:
                                    pass

                            # Alex output text
                            if server_content.output_transcription and server_content.output_transcription.text:
                                text_chunk = server_content.output_transcription.text
                                alex_text += text_chunk
                                try:
                                    await websocket.send_json({"event": "ai_transcript_chunk", "text": text_chunk})
                                except Exception:
                                    pass

                            # Alex audio
                            if server_content.model_turn:
                                for part in server_content.model_turn.parts:
                                    if part.inline_data and part.inline_data.data:
                                        chunk_data = part.inline_data.data
                                        alex_audio_bytes += len(chunk_data)
                                        try:
                                            await websocket.send_bytes(chunk_data)
                                        except Exception:
                                            pass

                            # Alex turn complete
                            if server_content.turn_complete or server_content.generation_complete:
                                alex_finish_timestamp = time.time()
                                if alex_text.strip():
                                    alex_latest_question = alex_text.strip()
                                telemetry["gemini_live_calls"] += 1
                                telemetry["total_audio_bytes"] += alex_audio_bytes
                                log_speech("Alex", alex_latest_question)

                                try:
                                    await websocket.send_json({"event": "turn_complete", "full_text": alex_text.strip()})
                                except Exception:
                                    pass

                                await broadcast_telemetry(active_module="Gemini Live API")
                                alex_is_speaking = False
                                alex_text = ""
                                alex_audio_bytes = 0
                                alex_turn_complete_event.set()

                            if server_content.interrupted:
                                log_event("GEMINI_LIVE", "Turn was interrupted")
                                alex_is_speaking = False
                                alex_turn_complete_event.set()

                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        err_msg = str(e).lower()
                        if "1000" in err_msg or "closed" in err_msg or "disconnect" in err_msg:
                            log_event("GEMINI_LIVE", "Session closed normally.")
                            break
                        log_event("RECEIVE_LOOP_CYCLE", f"Re-entering receive generator: {e}")
                        await asyncio.sleep(0.5)

            # Start the unified receive loop as a background task
            receive_task = asyncio.create_task(gemini_receive_loop())

            # Turn 1: Initial Greeting
            greeting_prompt = (
                f"The candidate has arrived. Their name is {candidate_name} and they chose {level} level. "
                "Greet them warmly, introduce yourself as Alex, and ask them to introduce themselves and share what technical projects they enjoy building."
            )
            log_event("INTERVIEW_FLOW", "Phase 1: Asking candidate to introduce themselves.")
            await session.send_client_content(
                turns=[types.Content(role="user", parts=[types.Part.from_text(text=greeting_prompt)])],
                turn_complete=True
            )
            # Wait for Alex to finish the greeting
            await alex_turn_complete_event.wait()

            # ── Main WebSocket Message Loop ──
            while True:
                msg = await websocket.receive()

                # Case A: Audio bytes from mic - candidate is talking
                if "bytes" in msg and msg["bytes"]:
                    telemetry["total_audio_bytes"] += len(msg["bytes"])
                    # We do NOT stream raw audio into Gemini Live directly to prevent Gemini's VAD from cutting off the candidate!
                    continue

                # Case B: JSON message from browser
                elif "text" in msg:
                    client_json = json.loads(msg["text"])

                    # Case B0: Candidate requested Interview Wrap-up & Report Generation
                    if client_json.get("event") == "finish_interview":
                        log_event("SESSION", f"Generating final assessment reports for {candidate_name}...")
                        skills_mastery = {
                            k: round(v.p_l, 3) for k, v in policy_router.graph.nodes.items()
                        }
                        if active_topic not in skills_mastery:
                            skills_mastery[active_topic] = 0.70

                        student_rep = await generate_student_report(
                            candidate_name=candidate_name,
                            level=level,
                            turns_history=turns_history,
                            skills_mastery=skills_mastery,
                            proctor_bii=round(policy_router.proctor.bii, 3),
                            mirt_theta=policy_router.mirt.theta,
                            mirt_std_error=policy_router.mirt.std_error,
                            ecosystem_summary=ecosystem_summary
                        )
                        eval_rep = await generate_evaluator_report(
                            candidate_name=candidate_name,
                            level=level,
                            turns_history=turns_history,
                            skills_mastery=skills_mastery,
                            proctor_bii=round(policy_router.proctor.bii, 3),
                            fraud_risk_score=round(1.0 - policy_router.proctor.bii, 2),
                            mirt_theta=policy_router.mirt.theta,
                            mirt_std_error=policy_router.mirt.std_error,
                            ecosystem_summary=ecosystem_summary
                        )
                        log_report("Student Career Compass", "reports/")
                        log_report("Evaluator Forensic Audit", "reports/")

                        # Persist final assessment reports to PostgreSQL database
                        try:
                            avg_mastery = sum(skills_mastery.values()) / max(1, len(skills_mastery))
                            hiring_signal = "STRONG HIRE" if avg_mastery >= 0.80 else ("HIRE" if avg_mastery >= 0.60 else ("LEAN HIRE" if avg_mastery >= 0.45 else "NO HIRE"))
                            save_final_reports(
                                session_id=session_id,
                                student_report=student_rep,
                                evaluator_report=eval_rep,
                                hiring_verdict=hiring_signal,
                                average_mastery=round(avg_mastery, 3),
                                proctor_integrity_score=round(policy_router.proctor.bii, 3)
                            )
                            log_event("DB_ARCHIVE", f"Archived final reports in PostgreSQL for session {session_id}.")
                        except Exception as e:
                            log_event("DB_ARCHIVE_ERROR", f"PostgreSQL report archive error: {e}")

                        await websocket.send_json({
                            "event": "reports_generated",
                            "student_report": student_rep,
                            "evaluator_report": eval_rep
                        })
                        continue

                    # Case B1: End-of-speech signal from microphone
                    if client_json.get("event") == "end_of_speech":
                        await broadcast_telemetry(active_module="Gemini Live STT")

                        user_text = ""
                        if client_json.get("transcript") and client_json["transcript"].strip():
                            user_text = client_json["transcript"].strip()
                        elif candidate_transcript_buffer.strip():
                            user_text = candidate_transcript_buffer.strip()
                        else:
                            # Wait up to 0.8s only if no transcript was provided yet
                            for _ in range(8):
                                if candidate_transcript_buffer.strip():
                                    user_text = candidate_transcript_buffer.strip()
                                    break
                                await asyncio.sleep(0.1)

                        candidate_transcript_buffer = ""

                        if not user_text:
                            log_event("AUDIO_INPUT", "No speech detected in candidate stream.")
                            await websocket.send_json({"event": "no_speech_detected"})
                            continue

                        log_speech("Candidate", user_text)
                        await websocket.send_json({"event": "candidate_transcript", "text": user_text})

                    # Case B2: Manual text input from chat box
                    elif client_json.get("text"):
                        user_text = client_json["text"].strip()
                        if not user_text:
                            continue
                        log_speech("Candidate (Typed)", user_text)
                    else:
                        continue

                    # ── Socratic Orchestration Pipeline ──
                    # 1. Background Quarantined Shadow Evaluator & Math calculation
                    asyncio.create_task(run_shadow_pipeline(user_text, alex_latest_question))

                    # 2. Topic Management & Socratic Dialogue Progression
                    if session_phase == "INTRO":
                        # Vector DB Semantic Search against Dynoxide
                        matched_pillars = await match_candidate_topics(user_text, top_k=3)
                        candidate_topics = [p["pillar_id"] for p in matched_pillars]

                        # Feature 3: Multi-Ecosystem Detection & Project Binding
                        ecosystem_summary = detect_ecosystems_from_intro(user_text)
                        pillar_ecosystem_map = bind_pillars_to_ecosystems(matched_pillars, user_text)

                        # Feature 1: Dynamic Knowledge Graph Topology Construction
                        dynamic_graph = build_dynamic_pillar_graph(matched_pillars, seniority=tier)
                        policy_router.initialize_session(custom_graph=dynamic_graph)
                        active_topic = policy_router.current_skill or candidate_topics[0]
                        active_pillar_name = next((p.get("name") for p in matched_pillars if p.get("pillar_id") == active_topic), active_topic)

                        # Save Permanent Intro Blueprint into PostgreSQL
                        intro_blueprint = {
                            "intro_text": user_text,
                            "matched_pillars": matched_pillars,
                            "candidate_topics": candidate_topics,
                            "ecosystem_summary": ecosystem_summary,
                            "pillar_ecosystem_map": pillar_ecosystem_map
                        }
                        try:
                            update_session_blueprint(session_id, intro_blueprint)
                        except Exception as e:
                            log_event("DB_BLUEPRINT_ERROR", str(e))

                        session_phase = "DEEP_DIVE"
                        turns_on_active_topic = 0
                        eco_directive = get_ecosystem_directive(active_topic, pillar_ecosystem_map)
                        log_event("VECTOR_DB_MATCH", f"Dynoxide Matched: {[p['name'] for p in matched_pillars]}. Focus: {active_pillar_name}")
                        log_event("DYNAMIC_GRAPH_INIT", f"KnowledgeGraph Nodes: {list(policy_router.graph.nodes.keys())} | Edges: {len(policy_router.graph.edges)}")
                        log_event("ECOSYSTEM_BINDING", f"Active Topic: {active_topic} | Dialect: {pillar_ecosystem_map.get(active_topic, 'GENERAL')}")

                        prompt_payload = (
                            f"The candidate introduced themselves: '{user_text}'.\n"
                            f"Acknowledge their background warmly. Pick the technical domain ({active_pillar_name} / {active_topic}) "
                            f"and ask an open-ended technical question exploring their architectural decisions and how it works under the hood.\n"
                            f"{eco_directive}"
                        )

                    elif session_phase == "DEEP_DIVE":
                        turns_on_active_topic += 1
                        node = policy_router.graph.nodes.get(active_topic)
                        current_mastery = node.p_l if node else 0.50

                        # Check if depth is reached on current topic
                        if current_mastery >= 0.80 or turns_on_active_topic >= 3:
                            # Epistemic Compaction: Save Topic Card to PostgreSQL
                            status_label = "MASTERED" if current_mastery >= 0.80 else "INCOMPLETE"
                            verdict_summary = f"Explored {active_topic} across {turns_on_active_topic} turns. Final mastery {round(current_mastery*100)}%."
                            if node:
                                node.status = MasteryStatus.MASTERED if current_mastery >= 0.80 else MasteryStatus.DEFICIENT

                            # Graph Message Passing: Propagate mastery to dependent neighbors!
                            propagated_boosts = policy_router.graph.propagate_mastery(active_topic)
                            if propagated_boosts:
                                log_event("GRAPH_PROPAGATE", f"Mastery of {active_topic} boosted priors: {propagated_boosts}")

                            try:
                                save_compacted_topic_card(
                                    session_id=session_id,
                                    topic_code=active_topic,
                                    turns_spent=turns_on_active_topic,
                                    final_mastery_p_l=round(current_mastery, 3),
                                    status=status_label,
                                    verdict_summary=verdict_summary
                                )
                                log_event("EPISTEMIC_COMPACT", f"Saved Compacted Topic Card for {active_topic} to PostgreSQL ({status_label}).")
                            except Exception as e:
                                log_event("DB_COMPACT_ERROR", str(e))

                            # Feature 1: Real Graph-Driven Topic Recommendation!
                            next_skill = policy_router.graph.get_next_recommended_skill()
                            if next_skill:
                                active_topic = next_skill
                                policy_router.current_skill = active_topic
                                turns_on_active_topic = 0
                                eco_directive = get_ecosystem_directive(active_topic, pillar_ecosystem_map)
                                log_event("GRAPH_ROUTE_TRANSITION", f"Depth reached. Graph routing next topic: {active_topic} | Dialect: {pillar_ecosystem_map.get(active_topic, 'GENERAL')}")
                                prompt_payload = (
                                    f"The candidate answered: '{user_text}'.\n"
                                    f"They have demonstrated depth on the previous topic. Acknowledge this briefly, and naturally transition to explore "
                                    f"the next topic: {active_topic}.\n"
                                    f"{eco_directive}\n"
                                    f"Ask an open-ended question about how they work with {active_topic}."
                                )
                            else:
                                session_phase = "WRAPPING_UP"
                                log_event("INTERVIEW_FLOW", "All candidate graph topics explored. Wrapping up technical dialogue.")
                                prompt_payload = (
                                    f"The candidate answered: '{user_text}'.\n"
                                    f"Thank them warmly for a fantastic and deep technical discussion across their projects. "
                                    f"Let them know you have enough technical depth and are compiling their evaluation reports."
                                )
                        else:
                            # Continue Socratic drill-down on active_topic with active ecosystem directive
                            eco_directive = get_ecosystem_directive(active_topic, pillar_ecosystem_map)
                            prompt_payload = (
                                f"The candidate answered: '{user_text}'.\n"
                                f"[PEDAGOGICAL DIRECTIVE: Continue probing deep into {active_topic}. Ask a follow-up exploring trade-offs, edge cases, failure modes, or concrete design decisions.]\n"
                                f"{eco_directive}\n"
                                f"Respond Socratically as Alex the interviewer."
                            )

                    else:
                        prompt_payload = (
                            f"The candidate said: '{user_text}'. Conclude warmly as Alex and let them know their report is being generated."
                        )

                    # Send to Gemini Live for Alex's conversational voice response
                    await broadcast_telemetry(active_module="Gemini Live API")
                    alex_turn_complete_event.clear()
                    await session.send_client_content(
                        turns=[types.Content(role="user", parts=[types.Part.from_text(text=prompt_payload)])],
                        turn_complete=True
                    )
                    try:
                        await asyncio.wait_for(alex_turn_complete_event.wait(), timeout=18.0)
                    except asyncio.TimeoutError:
                        log_event("VOICE_TIMEOUT", "Alex voice turn timed out after 18s.")
                    continue

    except WebSocketDisconnect:
        log_event("SESSION_DISCONNECT", f"Candidate {candidate_name} disconnected.")
    except Exception as e:
        if "disconnect" not in str(e).lower():
            log_event("SESSION_ERROR", f"Session exception: {e}")
    finally:
        if 'receive_task' in locals() and not receive_task.done():
            receive_task.cancel()

