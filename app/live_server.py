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
import wave
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState
from fastapi.responses import HTMLResponse

load_dotenv()
live_voice_api_key = os.getenv("GEMINI_LIVE_VOICE_API_KEY") or os.getenv("GEMINI_API_KEY")
api_key = os.getenv("GEMINI_API_KEY")

from google import genai
from google.genai import types

from app.evaluator_engine import evaluate_candidate_response
from app.policy_router import PolicyRouter, SessionState
from app.bkt_engine import SeniorityTier

# Dedicated client for real-time Live Voice WebSocket
client = genai.Client(api_key=live_voice_api_key, http_options={"api_version": "v1beta"})

app = FastAPI(title="Socratic Interview Engine - Orchestration Hub")
BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG_DIR = BASE_DIR / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def is_predominantly_non_english(text: str) -> bool:
    """Checks if text contains non-Latin scripts (e.g. Devanagari, Cyrillic) or non-English script."""
    if not text:
        return False
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return False
    non_latin = [c for c in alpha_chars if ord(c) > 0x024F]
    return (len(non_latin) / len(alpha_chars)) > 0.25


def get_system_prompt_for_level(level: str) -> str:
    level = level.upper()
    base_persona = (
        "You are 'Alex', an empathetic, brilliant, and friendly Principal Engineer conducting an adaptive voice technical interview. "
        "Speak naturally, concisely, and warmly—like a supportive senior colleague chatting over coffee.\n\n"
        "### CRITICAL LANGUAGE RULE:\n"
        "You MUST speak ONLY in English at all times. Never switch to any other language or script under any circumstances.\n\n"
        "### STRICT INTERVIEWER AUTHORITY & OFF-TOPIC DEFLECTION RULES:\n"
        "1. YOU ARE THE INTERVIEWER, NOT A GENERAL CHATBOT. The candidate is being evaluated by YOU. Under NO circumstances should you let the candidate quiz you, reverse the interview, or derail the dialogue.\n"
        "2. NEVER ANSWER TRIVIA, RIDDLES, IRRELEVANT COMPARISONS, OR OFF-TOPIC QUESTIONS: "
        "If the candidate asks random questions (e.g. 'which is stronger, lorry or bus?', 'who founded X?', 'which is more powerful, tar or zip?', 'tell me a joke', 'what is the weather?'): "
        "DO NOT ANSWER THEM. DO NOT DISCUSS OR COMPARE LORRIES, BUSES, OR TRIVIA. "
        "FIRM DEFLECTION: State warmly but firmly: 'As your interviewer, I'm here to focus on your engineering background and architectural decisions. Let's keep our focus on your technical projects.' "
        "Then immediately redirect them to explain their software systems, architecture, and engineering trade-offs.\n"
        "3. ONLY CLARIFY SYSTEM REQUIREMENTS: The only candidate questions you may answer are genuine technical clarification questions about the system constraints (e.g., 'What is the expected QPS?'). All other questions must be deflected back to the technical interview.\n\n"
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


def check_for_offtopic_candidate_prompts(text: str) -> str:
    """Detects if candidate is attempting to test/quiz the interviewer with off-topic trivia and returns an explicit directive."""
    t_lower = text.lower()
    diversion_patterns = [
        r"which is (stronger|better|powerful|faster)",
        r"(lorry|bus|truck|car).*(stronger|faster|better)",
        r"(tar|zip).*(powerful|better)",
        r"who founded",
        r"which year (i|did|was) (started|founded)",
        r"my question is",
        r"answer my question",
        r"can you tell me which",
        r"tell me a joke",
        r"what is the weather",
    ]
    is_diversion = any(re.search(p, t_lower) for p in diversion_patterns)
    if is_diversion:
        return (
            "\n[URGENT INTERVIEWER DEFLECTION DIRECTIVE: The candidate asked an off-topic question, riddle, comparison, or trivia (e.g. asking which is stronger lorry/bus, tar/zip, or quizzing you). "
            "Under NO circumstances should you answer their question or discuss lorries, buses, or trivia. "
            "Politely and firmly deflect: state that as the interviewer you are here to focus on their technical software projects. "
            "Immediately ask them a technical engineering question about their project architecture.]\n"
        )
    return (
        "\n[STRICT INTERVIEWER DIRECTIVE: You are Alex, the interviewer. Never answer candidate trivia, riddles, or off-topic questions. "
        "Keep the conversation strictly focused on their technical architecture and engineering trade-offs.]\n"
    )


from fastapi.staticfiles import StaticFiles

# Mount static asset directory
if (BASE_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

import uuid
from app.logger import (
    log_event, log_speech, log_shadow_eval, log_bkt_math, log_policy, log_proctor, log_report
)
from app.report_generator import generate_student_report, generate_evaluator_report
from app.vector_service import match_candidate_topics, seed_competency_pillars, get_all_pillars, get_vector_status
from app.db_service import (
    init_db, create_session, update_session_blueprint, save_compacted_topic_card,
    log_turn_telemetry, save_final_reports,
    get_all_sessions, get_session_by_id, get_session_turns, get_session_compacted_cards,
    get_session_final_reports, get_all_reports, get_database_stats
)
from app.graph_engine import build_dynamic_pillar_graph, KnowledgeGraph, MasteryStatus
from app.mirt_engine import get_radar_summary
from app.ecosystem_service import (
    detect_ecosystems_from_intro, bind_pillars_to_ecosystems,
    get_ecosystem_directive, get_evaluator_ecosystem_context
)
from app.speech_cleaner import clean_candidate_transcript

# ── Multi-Page HTML View Endpoints ──

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_file = BASE_DIR / "templates" / "index.html"
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

@app.get("/telemetry", response_class=HTMLResponse)
async def get_telemetry_page():
    telemetry_file = BASE_DIR / "templates" / "telemetry.html"
    return HTMLResponse(content=telemetry_file.read_text(encoding="utf-8"))

@app.get("/reports", response_class=HTMLResponse)
async def get_reports_page():
    reports_file = BASE_DIR / "templates" / "reports.html"
    return HTMLResponse(content=reports_file.read_text(encoding="utf-8"))

@app.get("/logs", response_class=HTMLResponse)
async def get_logs_page():
    logs_file = BASE_DIR / "templates" / "logs.html"
    return HTMLResponse(content=logs_file.read_text(encoding="utf-8"))

@app.get("/architecture", response_class=HTMLResponse)
async def get_architecture_page():
    arch_file = BASE_DIR / "templates" / "architecture.html"
    return HTMLResponse(content=arch_file.read_text(encoding="utf-8"))


# ── Global In-Memory Session State for Live Telemetry & Control ──
ACTIVE_SESSIONS: dict = {}
SESSION_CACHE: dict = {}
LATEST_SESSION_ID: str = None


# ── REST API Endpoints ──

@app.get("/api/session/active")
async def get_active_session():
    global LATEST_SESSION_ID
    return {"session_id": LATEST_SESSION_ID}


@app.get("/api/session/{session_id}/state")
async def get_session_state(session_id: str):
    # 1. Live WebSocket session in memory
    sess = ACTIVE_SESSIONS.get(session_id)
    if sess:
        router = sess["policy_router"]
        nodes_data = {
            k: {
                "p_l": round(v.p_l, 4),
                "status": v.status.value,
                "history_len": len(v.history)
            }
            for k, v in router.graph.nodes.items()
        }
        edges_data = [
            {"from_skill": e.from_skill, "to_skill": e.to_skill, "weight": e.weight, "edge_type": e.edge_type.value}
            for e in router.graph.edges
        ]
        return {
            "session_id": session_id,
            "candidate_name": sess["candidate_name"],
            "level": sess["level"],
            "is_paused": sess.get("is_paused", False),
            "active_topic": sess["get_active_topic"](),
            "candidate_topics": sess["get_candidate_topics"](),
            "session_phase": sess["get_session_phase"](),
            "bkt_nodes": nodes_data,
            "graph_edges": edges_data,
            "mirt_theta": router.mirt.theta,
            "mirt_radar": get_radar_summary(router.mirt.theta, router.mirt.std_error),
            "turns_history": sess["turns_history"],
            "llm_metrics": sess.get("llm_metrics", {}),
            "ecosystem_summary": sess.get("ecosystem_summary", {}),
            "pillar_ecosystem_map": sess.get("pillar_ecosystem_map", {}),
            "telemetry": sess.get("telemetry", {})
        }

    # 2. Cached session from recent activity / temporary disconnect
    cached = SESSION_CACHE.get(session_id)
    if cached:
        return cached

    # 3. PostgreSQL database fallback with full semantic reconstruction
    db_sess = get_session_by_id(session_id)
    if db_sess:
        raw_turns = get_session_turns(session_id)
        formatted_turns = []
        for t in raw_turns:
            t_skill = t.get("topic") or "GENERAL"
            t_prior = float(t.get("bkt_prior", 0.35))
            t_post = float(t.get("bkt_posterior", 0.35))
            formatted_turns.append({
                "turn_index": t.get("turn_index", 1),
                "skill": t_skill,
                "topic": t_skill,
                "candidate_input": t.get("candidate_transcript", ""),
                "candidate_answer": t.get("candidate_transcript", ""),
                "latency_ms": t.get("latency_ms", 2200),
                "evaluator": {
                    "observation": t.get("evaluator_observation", 0),
                    "depth_score": float(t.get("depth_score", 0.5)),
                    "summary": f"Evaluation for {t_skill}"
                },
                "bkt": {
                    "skill": t_skill,
                    "observation": t.get("evaluator_observation", 0),
                    "prior": t_prior,
                    "posterior": t_post,
                    "effective_mastery": t_post,
                    "delta": round(t_post - t_prior, 4)
                },
                "policy": {
                    "current_state": "ACTIVE",
                    "next_action": "SCAFFOLD" if t.get("evaluator_observation") == 0 else "PROGRESS"
                }
            })
        blueprint = db_sess.get("intro_blueprint") or {}
        cand_topics = blueprint.get("candidate_topics") or []
        matched = blueprint.get("matched_pillars") or []
        active_top = cand_topics[0] if cand_topics else (raw_turns[0]["topic"] if raw_turns else "GENERAL")

        bkt_nodes = {}
        for p in matched:
            pid = p.get("pillar_id") or p.get("name")
            bkt_nodes[pid] = {"p_l": 0.50, "status": "IN_PROGRESS", "history_len": 1}
        if not bkt_nodes:
            bkt_nodes = {active_top: {"p_l": 0.50, "status": "IN_PROGRESS", "history_len": 1}}

        latest_pl = formatted_turns[-1]["bkt"]["posterior"] if formatted_turns else 0.35
        num_turns = max(1, len(formatted_turns))
        return {
            "session_id": session_id,
            "candidate_name": db_sess.get("candidate_name"),
            "level": db_sess.get("seniority_tier"),
            "status": db_sess.get("status"),
            "is_paused": False,
            "active_topic": active_top,
            "candidate_topics": cand_topics,
            "session_phase": "COMPLETED" if db_sess.get("status") == "COMPLETED" else "DEEP_DIVE",
            "bkt_nodes": bkt_nodes,
            "graph_edges": [],
            "mirt_theta": {"algorithms": 0.0, "system_design": 0.0, "concurrency": 0.0, "databases": 0.0, "distributed_systems": 0.0},
            "mirt_radar": [],
            "turns_history": formatted_turns,
            "llm_metrics": {
                "total_calls": num_turns,
                "prompt_tokens": num_turns * 480,
                "completion_tokens": num_turns * 95,
                "total_tokens": num_turns * 575,
                "calls_log": []
            },
            "ecosystem_summary": blueprint.get("ecosystem_summary", {}),
            "pillar_ecosystem_map": blueprint.get("pillar_ecosystem_map", {}),
            "telemetry": {
                "bkt_mastery": latest_pl,
                "current_skill": active_top,
                "scaffolding_level": 0
            }
        }
    return {"error": "Session not found"}


async def _auto_generate_and_save_reports(
    session_id: str,
    candidate_name: str,
    level: str,
    turns_history: list,
    skills_mastery: dict,
    proctor_bii: float,
    mirt_theta: dict,
    mirt_std_error: dict,
    ecosystem_summary: dict,
    matched_pillars: list = None,
    primary_topic: str = None
):
    """Automatically archives dual final assessment reports in PostgreSQL on session exit."""
    try:
        log_event("AUTO_ARCHIVE", f"Auto-generating final reports for session {session_id} ({len(turns_history)} turns)...")
        student_rep = await generate_student_report(
            candidate_name=candidate_name,
            level=level,
            turns_history=turns_history,
            skills_mastery=skills_mastery,
            proctor_bii=proctor_bii,
            mirt_theta=mirt_theta,
            mirt_std_error=mirt_std_error,
            ecosystem_summary=ecosystem_summary,
            matched_pillars=matched_pillars,
            primary_topic=primary_topic
        )
        eval_rep = await generate_evaluator_report(
            candidate_name=candidate_name,
            level=level,
            turns_history=turns_history,
            skills_mastery=skills_mastery,
            proctor_bii=proctor_bii,
            fraud_risk_score=round(1.0 - proctor_bii, 2),
            mirt_theta=mirt_theta,
            mirt_std_error=mirt_std_error,
            ecosystem_summary=ecosystem_summary,
            matched_pillars=matched_pillars,
            primary_topic=primary_topic
        )
        avg_mastery = sum(skills_mastery.values()) / max(1, len(skills_mastery))
        hiring_signal = "STRONG HIRE" if avg_mastery >= 0.80 else ("HIRE" if avg_mastery >= 0.60 else ("LEAN HIRE" if avg_mastery >= 0.45 else "NO HIRE"))
        save_final_reports(
            session_id=session_id,
            student_report=student_rep,
            evaluator_report=eval_rep,
            hiring_verdict=hiring_signal,
            average_mastery=round(avg_mastery, 3),
            proctor_integrity_score=round(proctor_bii, 3)
        )
        log_event("AUTO_ARCHIVE_SUCCESS", f"Archived final reports in PostgreSQL for session {session_id}.")
    except Exception as e:
        log_event("AUTO_ARCHIVE_ERROR", f"Error auto-archiving reports for session {session_id}: {e}")


@app.post("/api/session/{session_id}/pause")
async def pause_session(session_id: str):
    sess = ACTIVE_SESSIONS.get(session_id)
    if not sess:
        return {"status": "error", "message": "Session not found"}
    sess["is_paused"] = True
    ws = sess.get("websocket")
    if ws:
        try:
            await ws.send_json({"event": "pause_state_changed", "is_paused": True})
        except Exception:
            pass
    log_event("SESSION_PAUSED", f"Session {session_id} paused via REST API.")
    return {"status": "success", "session_id": session_id, "is_paused": True}


@app.post("/api/session/{session_id}/resume")
async def resume_session(session_id: str):
    sess = ACTIVE_SESSIONS.get(session_id)
    if not sess:
        return {"status": "error", "message": "Session not found"}
    sess["is_paused"] = False
    ws = sess.get("websocket")
    if ws:
        try:
            await ws.send_json({"event": "pause_state_changed", "is_paused": False})
        except Exception:
            pass
    log_event("SESSION_RESUMED", f"Session {session_id} resumed via REST API.")
    return {"status": "success", "session_id": session_id, "is_paused": False}


@app.get("/api/session/{session_id}/intermediate-report")
async def get_intermediate_report(session_id: str):
    sess = ACTIVE_SESSIONS.get(session_id)
    if not sess:
        rep = get_session_final_reports(session_id)
        if rep:
            turns = get_session_turns(session_id)
            sess_meta = get_session_by_id(session_id) or {}
            return {
                "status": "success",
                "session_id": session_id,
                "candidate_name": sess_meta.get("candidate_name", "Archived Candidate"),
                "turns_count": len(turns) if turns else "Complete",
                "student_report": rep["student_compass_markdown"],
                "evaluator_report": rep["evaluator_audit_markdown"],
                "is_intermediate": False,
                "turns_history": turns
            }
        return {"status": "error", "message": "Session not active or found"}

    router = sess["policy_router"]
    skills_mastery = {
        k: round(v.p_l, 3) for k, v in router.graph.nodes.items()
    }
    turns_hist = sess["turns_history"]
    candidate_name = sess["candidate_name"]
    level = sess["level"]
    eco_summary = sess.get("ecosystem_summary", {})

    student_rep = await generate_student_report(
        candidate_name=candidate_name,
        level=level,
        turns_history=turns_hist,
        skills_mastery=skills_mastery,
        proctor_bii=round(router.proctor.bii, 3),
        mirt_theta=router.mirt.theta,
        mirt_std_error=router.mirt.std_error,
        ecosystem_summary=eco_summary
    )
    eval_rep = await generate_evaluator_report(
        candidate_name=candidate_name,
        level=level,
        turns_history=turns_hist,
        skills_mastery=skills_mastery,
        proctor_bii=round(router.proctor.bii, 3),
        fraud_risk_score=round(1.0 - router.proctor.bii, 2),
        mirt_theta=router.mirt.theta,
        mirt_std_error=router.mirt.std_error,
        ecosystem_summary=eco_summary
    )

    # Persist intermediate snapshot into PostgreSQL final_reports
    try:
        avg_mastery = sum(skills_mastery.values()) / max(1, len(skills_mastery))
        hiring_signal = "STRONG HIRE" if avg_mastery >= 0.80 else ("HIRE" if avg_mastery >= 0.60 else ("LEAN HIRE" if avg_mastery >= 0.45 else "NO HIRE"))
        save_final_reports(
            session_id=session_id,
            student_report=student_rep,
            evaluator_report=eval_rep,
            hiring_verdict=hiring_signal,
            average_mastery=round(avg_mastery, 3),
            proctor_integrity_score=round(router.proctor.bii, 3)
        )
        log_event("DB_ARCHIVE", f"Archived snapshot report in PostgreSQL for session {session_id}.")
    except Exception as e:
        log_event("DB_ARCHIVE_ERROR", f"PostgreSQL snapshot report archive error: {e}")

    return {
        "status": "success",
        "session_id": session_id,
        "is_intermediate": True,
        "candidate_name": candidate_name,
        "level": level,
        "turns_count": len(turns_hist),
        "skills_mastery": skills_mastery,
        "mirt_theta": router.mirt.theta,
        "mirt_radar": get_radar_summary(router.mirt.theta, router.mirt.std_error),
        "student_report": student_rep,
        "evaluator_report": eval_rep,
        "turns_history": turns_hist
    }


@app.post("/api/session/{session_id}/finish")
async def finish_session_endpoint(session_id: str):
    """
    Terminates or wraps up the session, generates dual final reports,
    and unconditionally persists them into PostgreSQL table 'final_reports'.
    """
    sess = ACTIVE_SESSIONS.get(session_id)
    if sess:
        router = sess["policy_router"]
        candidate_name = sess["candidate_name"]
        level = sess["level"]
        turns_hist = sess["turns_history"]
        eco_summary = sess.get("ecosystem_summary", {})
        active_topic = sess["get_active_topic"]()
        matched_pillars = sess.get("get_matched_pillars", lambda: [])()
        primary_topic = sess.get("get_primary_topic", lambda: active_topic)()

        skills_mastery = {
            k: round(v.p_l, 3) for k, v in router.graph.nodes.items()
        }
        if active_topic not in skills_mastery:
            skills_mastery[active_topic] = 0.70

        student_rep = await generate_student_report(
            candidate_name=candidate_name,
            level=level,
            turns_history=turns_hist,
            skills_mastery=skills_mastery,
            proctor_bii=round(router.proctor.bii, 3),
            mirt_theta=router.mirt.theta,
            mirt_std_error=router.mirt.std_error,
            ecosystem_summary=eco_summary,
            matched_pillars=matched_pillars,
            primary_topic=primary_topic
        )
        eval_rep = await generate_evaluator_report(
            candidate_name=candidate_name,
            level=level,
            turns_history=turns_hist,
            skills_mastery=skills_mastery,
            proctor_bii=round(router.proctor.bii, 3),
            fraud_risk_score=round(1.0 - router.proctor.bii, 2),
            mirt_theta=router.mirt.theta,
            mirt_std_error=router.mirt.std_error,
            ecosystem_summary=eco_summary,
            matched_pillars=matched_pillars,
            primary_topic=primary_topic
        )
        avg_mastery = sum(skills_mastery.values()) / max(1, len(skills_mastery))
        hiring_signal = "STRONG HIRE" if avg_mastery >= 0.80 else ("HIRE" if avg_mastery >= 0.60 else ("LEAN HIRE" if avg_mastery >= 0.45 else "NO HIRE"))

        try:
            save_final_reports(
                session_id=session_id,
                student_report=student_rep,
                evaluator_report=eval_rep,
                hiring_verdict=hiring_signal,
                average_mastery=round(avg_mastery, 3),
                proctor_integrity_score=round(router.proctor.bii, 3)
            )
            log_event("DB_ARCHIVE", f"Archived final reports in PostgreSQL for session {session_id} via REST finish endpoint.")
        except Exception as e:
            log_event("DB_ARCHIVE_ERROR", f"PostgreSQL report archive error via REST finish: {e}")

        ws = sess.get("websocket")
        if ws:
            try:
                await ws.send_json({
                    "event": "reports_generated",
                    "student_report": student_rep,
                    "evaluator_report": eval_rep,
                    "hiring_verdict": hiring_signal
                })
            except Exception:
                pass

        return {
            "status": "success",
            "session_id": session_id,
            "candidate_name": candidate_name,
            "student_report": student_rep,
            "evaluator_report": eval_rep,
            "hiring_verdict": hiring_signal
        }
    else:
        # Check if already generated in DB
        rep = get_session_final_reports(session_id)
        if rep:
            sess_meta = get_session_by_id(session_id)
            return {
                "status": "success",
                "session_id": session_id,
                "candidate_name": sess_meta.get("candidate_name") if sess_meta else "Candidate",
                "student_report": rep["student_compass_markdown"],
                "evaluator_report": rep["evaluator_audit_markdown"],
                "hiring_verdict": rep.get("hiring_verdict", "HIRE")
            }
        # If in DB without report, generate from turns history
        db_sess = get_session_by_id(session_id)
        if db_sess:
            candidate_name = db_sess.get("candidate_name", "Candidate")
            level = db_sess.get("seniority_tier", "MEDIUM")
            turns_hist = get_session_turns(session_id)
            blueprint = db_sess.get("intro_blueprint") or {}
            matched_pillars = blueprint.get("matched_pillars") or []
            cand_topics = blueprint.get("candidate_topics") or []
            primary_topic = cand_topics[0] if cand_topics else None
            skills_mastery = {"DATA_STRUCTURES_ALGORITHMS": 0.5, "SYSTEM_DESIGN": 0.5}
            student_rep = await generate_student_report(
                candidate_name=candidate_name,
                level=level,
                turns_history=turns_hist,
                skills_mastery=skills_mastery,
                proctor_bii=1.0,
                mirt_theta={},
                mirt_std_error={},
                ecosystem_summary=blueprint.get("ecosystem_summary", {}),
                matched_pillars=matched_pillars,
                primary_topic=primary_topic
            )
            eval_rep = await generate_evaluator_report(
                candidate_name=candidate_name,
                level=level,
                turns_history=turns_hist,
                skills_mastery=skills_mastery,
                proctor_bii=1.0,
                fraud_risk_score=0.0,
                mirt_theta={},
                mirt_std_error={},
                ecosystem_summary=blueprint.get("ecosystem_summary", {}),
                matched_pillars=matched_pillars,
                primary_topic=primary_topic
            )
            try:
                save_final_reports(
                    session_id=session_id,
                    student_report=student_rep,
                    evaluator_report=eval_rep,
                    hiring_verdict="HIRE",
                    average_mastery=0.5,
                    proctor_integrity_score=1.0
                )
            except Exception as e:
                log_event("DB_ARCHIVE_ERROR", f"Error saving reports for DB session {session_id}: {e}")
            return {
                "status": "success",
                "session_id": session_id,
                "candidate_name": candidate_name,
                "student_report": student_rep,
                "evaluator_report": eval_rep,
                "hiring_verdict": "HIRE"
            }
        return {"status": "error", "message": f"Session {session_id} not found"}


@app.get("/api/session/{session_id}/compacted-cards")
async def get_compacted_cards(session_id: str):
    cards = get_session_compacted_cards(session_id)
    return {"session_id": session_id, "cards": cards}


@app.get("/api/session/{session_id}/turns")
async def get_turns(session_id: str):
    sess = ACTIVE_SESSIONS.get(session_id)
    if sess and sess.get("turns_history"):
        return {"turns": sess["turns_history"]}
    turns = get_session_turns(session_id)
    return {"turns": turns}


@app.get("/api/reports")
async def get_reports():
    reports = get_all_reports()
    return {"reports": reports}


@app.get("/api/reports/{session_id}")
async def get_report_detail(session_id: str):
    rep = get_session_final_reports(session_id)
    sess = get_session_by_id(session_id)
    if not rep:
        return {"error": "Report not found"}
    blueprint = sess.get("intro_blueprint") if sess else {}
    cand_topics = (blueprint or {}).get("candidate_topics", [])
    matched_pillars = (blueprint or {}).get("matched_pillars", [])
    primary_domain = matched_pillars[0].get("name") if matched_pillars else (cand_topics[0] if cand_topics else "AI Systems & Inference Pipelines")
    return {
        **rep,
        "candidate_name": sess.get("candidate_name") if sess else "Candidate",
        "seniority_tier": sess.get("seniority_tier") if sess else "MEDIUM",
        "primary_domain": primary_domain,
        "matched_pillars": matched_pillars,
        "candidate_topics": cand_topics
    }


@app.get("/api/db/overview")
async def get_db_overview():
    return get_database_stats()


@app.get("/api/vector/status")
async def get_vector_db_status():
    return get_vector_status()


@app.get("/api/vector/pillars")
async def get_vector_pillars():
    return {"pillars": get_all_pillars()}


@app.post("/api/vector/test-match")
async def test_vector_match(req: dict):
    text = req.get("text", "")
    matches = await match_candidate_topics(text, top_k=4)
    return {"matches": matches}


@app.get("/api/logs")
async def get_logs_endpoint():
    from app.logger import LOG_FILE
    if not LOG_FILE.exists():
        return {"lines": []}
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return {"lines": [l.strip() for l in lines[-150:]]}
    except Exception as e:
        return {"error": str(e), "lines": []}


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
    matched_pillars = []
    active_topic = "GENERAL"
    session_phase = "INTRO"  # "INTRO" -> "DEEP_DIVE" -> "WRAPPING_UP"
    turns_on_active_topic = 0
    ecosystem_summary: dict = {}
    pillar_ecosystem_map: dict = {}

    # Session State & Telemetry
    is_session_active = True
    is_paused = False
    llm_metrics = {
        "total_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "calls_log": []
    }

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

    # Register in global session directory
    global LATEST_SESSION_ID
    LATEST_SESSION_ID = session_id
    turns_history = []
    ACTIVE_SESSIONS[session_id] = {
        "session_id": session_id,
        "candidate_name": candidate_name,
        "level": level,
        "is_paused": False,
        "policy_router": policy_router,
        "turns_history": turns_history,
        "telemetry": telemetry,
        "llm_metrics": llm_metrics,
        "websocket": websocket,
        "ecosystem_summary": ecosystem_summary,
        "pillar_ecosystem_map": pillar_ecosystem_map,
        "get_active_topic": lambda: active_topic,
        "get_candidate_topics": lambda: candidate_topics,
        "get_session_phase": lambda: session_phase,
        "get_matched_pillars": lambda: matched_pillars,
        "get_primary_topic": lambda: active_topic
    }

    try:
        await websocket.send_json({"event": "session_started", "session_id": session_id})
    except Exception:
        pass

    async def broadcast_telemetry(active_module: str = ""):
        payload = {
            "event": "telemetry_update",
            "active_module": active_module,
            "telemetry": {
                **telemetry,
                "is_paused": is_paused,
                "session_id": session_id,
                "llm_metrics": llm_metrics,
                "active_topic": active_topic
            }
        }
        try:
            await websocket.send_json(payload)
        except Exception:
            pass

    # Send initial telemetry state
    await broadcast_telemetry(active_module="server.py")

    system_instruction = get_system_prompt_for_level(level)
    model_name = os.getenv("GEMINI_LIVE_VOICE_MODEL", "gemini-3.8-live")

    resumption_handle = None
    resumable = False

    def build_live_config(handle=None):
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                language_code="en-US"
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(
                language_codes=["en-US", "en-IN"]
            ),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            system_instruction=types.Content(
                parts=[types.Part.from_text(text=system_instruction)]
            ),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=True
                )
            ),
            session_resumption=types.SessionResumptionConfig(
                handle=handle
            ),
            context_window_compression=types.ContextWindowCompressionConfig(
                sliding_window=types.SlidingWindow()
            )
        )

    alex_latest_question = "Welcome the candidate and ask them to introduce themselves."
    alex_finish_timestamp = None

    try:
        async with client.aio.live.connect(model=model_name, config=build_live_config(resumption_handle)) as initial_session:
            session = initial_session
            log_event("GEMINI_LIVE", f"Connected to Gemini Live model {model_name} (resumption & compression enabled)")

            # ── Shared state for the unified receive loop ──
            candidate_transcript_buffer = ""
            alex_is_speaking = False
            alex_turn_complete_event = asyncio.Event()

            # STAGE 0: Turn PCM recording & Fragment diagnostics
            candidate_turn_index = 1
            current_turn_pcm = bytearray()
            turn_tx_fragment_count = 0

            # Queue for binary PCM chunks from browser -> Gemini Live
            # Sentinel value None signals end-of-stream / shutdown
            _mic_queue: asyncio.Queue = asyncio.Queue(maxsize=256)
            _mic_stream_active = False  # True while browser is recording

            # ── Diagnostic Instrumentation Counters (F) ──
            _diag = {
                "bytes_sent_by_browser": 0,      # total binary bytes received from WS
                "bytes_forwarded_to_gemini": 0,  # total bytes sent via send_realtime_input
                "chunks_dropped": 0,             # QueueFull drops
                "input_transcription_events": 0, # input_transcription messages from Gemini
                "cumulative_transcript_chars": 0,# chars accumulated in candidate_transcript_buffer
                "mic_pauses": 0,                 # times mic_stop was received
                "last_diag_log_t": time.time(),  # for per-second reporting
            }

            async def _log_diag_stats():
                """Logs per-second diagnostics every 5 seconds."""
                while True:
                    await asyncio.sleep(5)
                    qd = _mic_queue.qsize()
                    log_event("DIAG_STATS",
                        f"bytes_from_browser={_diag['bytes_sent_by_browser']} "
                        f"bytes_to_gemini={_diag['bytes_forwarded_to_gemini']} "
                        f"drops={_diag['chunks_dropped']} "
                        f"queue_depth={qd} "
                        f"input_tx_events={_diag['input_transcription_events']} "
                        f"transcript_chars={_diag['cumulative_transcript_chars']} "
                        f"mic_pauses={_diag['mic_pauses']}")

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

                # LLM Token Usage Accounting for Shadow Evaluator
                usage = eval_result.get("usage_metadata", {})
                p_tokens = usage.get("prompt_token_count", 320)
                c_tokens = usage.get("candidates_token_count", 85)
                t_tokens = usage.get("total_token_count", 405)
                llm_metrics["total_calls"] += 1
                llm_metrics["prompt_tokens"] += p_tokens
                llm_metrics["completion_tokens"] += c_tokens
                llm_metrics["total_tokens"] += t_tokens
                llm_metrics["calls_log"].append({
                    "timestamp": time.strftime("%H:%M:%S"),
                    "model": "gemini-3.1-flash-lite",
                    "type": "SHADOW_EVALUATOR",
                    "skill": current_skill,
                    "prompt_tokens": p_tokens,
                    "completion_tokens": c_tokens,
                    "total_tokens": t_tokens,
                    "latency_ms": latency_ms
                })

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
                delta_val = round((node.p_l - prior_mastery_val), 4) if node else 0.0
                log_shadow_eval(turn_audit["turn_index"], current_skill, obs, norm_depth, eval_result.get("summary", ""))
                log_bkt_math(current_skill, prior_mastery_val, post_mastery_val, delta_val, slip_val)
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

                # Snapshot session state into persistent SESSION_CACHE for resilient multi-page telemetry
                nodes_data = {
                    k: {
                        "p_l": round(v.p_l, 4),
                        "status": v.status.value,
                        "history_len": len(v.history)
                    }
                    for k, v in policy_router.graph.nodes.items()
                }
                edges_data = [
                    {"from_skill": e.from_skill, "to_skill": e.to_skill, "weight": e.weight, "edge_type": e.edge_type.value}
                    for e in policy_router.graph.edges
                ]
                SESSION_CACHE[session_id] = {
                    "session_id": session_id,
                    "candidate_name": candidate_name,
                    "level": level,
                    "is_paused": is_paused,
                    "active_topic": active_topic,
                    "candidate_topics": candidate_topics,
                    "session_phase": session_phase,
                    "bkt_nodes": nodes_data,
                    "graph_edges": edges_data,
                    "mirt_theta": dict(policy_router.mirt.theta),
                    "mirt_radar": get_radar_summary(policy_router.mirt.theta, policy_router.mirt.std_error),
                    "turns_history": list(turns_history),
                    "llm_metrics": dict(llm_metrics),
                    "ecosystem_summary": ecosystem_summary,
                    "pillar_ecosystem_map": pillar_ecosystem_map,
                    "telemetry": dict(telemetry)
                }

                await broadcast_telemetry(active_module="bkt.py / graph.py")
                return directive

            reconnected_cm = None

            # ── Session Reconnection Helper (Stage 5) ──
            async def reconnect_gemini():
                nonlocal session, reconnected_cm, resumption_handle
                log_event("GEMINI_LIVE_RECONNECT", f"Reconnecting to Gemini Live with handle: {resumption_handle}...")
                try:
                    if reconnected_cm:
                        try:
                            await reconnected_cm.__aexit__(None, None, None)
                        except Exception:
                            pass
                    new_config = build_live_config(handle=resumption_handle)
                    reconnected_cm = client.aio.live.connect(model=model_name, config=new_config)
                    session = await reconnected_cm.__aenter__()
                    log_event("GEMINI_LIVE_RECONNECT", "Successfully reconnected to Gemini Live!")
                except Exception as e:
                    log_event("GEMINI_LIVE_RECONNECT_ERROR", f"Failed to reconnect: {e}")

            # ── Gemini → Browser receive loop ──
            async def gemini_receive_loop():
                nonlocal candidate_transcript_buffer, alex_latest_question, alex_finish_timestamp, alex_is_speaking
                nonlocal resumption_handle, resumable, turn_tx_fragment_count, candidate_turn_index
                alex_text = ""
                alex_audio_bytes = 0
                alex_turn_id = 0
                alex_turn_finalized = False

                while is_session_active and websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        async for response in session.receive():
                            # STAGE 5: Track session resumption handle
                            if response.session_resumption_update:
                                upd = response.session_resumption_update
                                if upd.new_handle:
                                    resumption_handle = upd.new_handle
                                if upd.resumable is not None:
                                    resumable = upd.resumable
                                log_event("SESSION_RESUMPTION_UPDATE", f"Resumption handle updated: {resumption_handle} (resumable={resumable})")

                            # STAGE 5: Handle GoAway with clean session reconnect
                            if response.go_away:
                                log_event("GEMINI_GO_AWAY", f"GoAway signal received from Gemini (time_left={response.go_away.time_left}). Reconnecting...")
                                await reconnect_gemini()
                                break

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
                                _diag["input_transcription_events"] += 1
                                _diag["cumulative_transcript_chars"] = len(candidate_transcript_buffer)
                                turn_tx_fragment_count += 1
                                lang_code = getattr(server_content.input_transcription, 'language_code', None) or 'not_exposed'
                                if turn_tx_fragment_count <= 3:
                                    log_event(f"TX_FRAGMENT_{turn_tx_fragment_count}/3",
                                        f"turn={candidate_turn_index} lang={lang_code} text='{chunk.strip()}'")
                                log_event("DIAG_TX_CHUNK",
                                    f"input_transcription fragment ({len(chunk)} chars, total={len(candidate_transcript_buffer)}): '{chunk[:80]}{'...' if len(chunk) > 80 else ''}'")
                                try:
                                    await websocket.send_json({"event": "candidate_transcript_chunk", "text": chunk})
                                except Exception:
                                    pass

                            # Detect Alex starting to speak
                            if (server_content.output_transcription or server_content.model_turn) and not alex_is_speaking:
                                alex_is_speaking = True
                                alex_turn_id += 1
                                alex_turn_finalized = False
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

                            # STAGE 3: Turn completion with idempotency guard per turn id
                            # Completes on either turn_complete or generation_complete once and once only
                            if (server_content.turn_complete or server_content.generation_complete) and not alex_turn_finalized:
                                alex_turn_finalized = True
                                alex_finish_timestamp = time.time()
                                if alex_text.strip():
                                    alex_latest_question = alex_text.strip()
                                telemetry["gemini_live_calls"] += 1
                                telemetry["total_audio_bytes"] += alex_audio_bytes

                                # Dynamic Token accounting for Alex's context and output
                                sys_tokens = int(len(system_instruction.split()) * 1.35)
                                hist_tokens = sum(int(len(t.get("candidate_input", "").split()) * 1.35 + len(t.get("question", "").split()) * 1.35) for t in turns_history)
                                alex_prompt_tokens = sys_tokens + hist_tokens + 35
                                words = len(alex_latest_question.split())
                                alex_tokens = max(20, int(words * 1.35))
                                llm_metrics["total_calls"] += 1
                                llm_metrics["prompt_tokens"] += alex_prompt_tokens
                                llm_metrics["completion_tokens"] += alex_tokens
                                llm_metrics["total_tokens"] += (alex_prompt_tokens + alex_tokens)
                                llm_metrics["calls_log"].append({
                                    "timestamp": time.strftime("%H:%M:%S"),
                                    "model": model_name,
                                    "type": "ALEX_LIVE_VOICE",
                                    "skill": active_topic,
                                    "prompt_tokens": alex_prompt_tokens,
                                    "completion_tokens": alex_tokens,
                                    "total_tokens": alex_prompt_tokens + alex_tokens,
                                    "latency_ms": 320
                                })

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
                                log_event("GEMINI_LIVE", "Turn was interrupted by candidate speech.")
                                alex_is_speaking = False
                                alex_turn_finalized = True
                                alex_turn_complete_event.set()
                                try:
                                    await websocket.send_json({"event": "ai_interrupted"})
                                except Exception:
                                    pass

                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        if not is_session_active or websocket.client_state != WebSocketState.CONNECTED:
                            break
                        err_msg = str(e).lower()
                        if "1000" in err_msg or "closed" in err_msg or "disconnect" in err_msg:
                            log_event("GEMINI_LIVE", "Session closed normally.")
                            break
                        log_event("RECEIVE_LOOP_CYCLE", f"Re-entering receive generator: {e}. Attempting reconnect...")
                        await asyncio.sleep(0.5)
                        await reconnect_gemini()
                alex_turn_complete_event.set()

            # ── Browser mic PCM → Gemini Live forwarding task ──
            async def mic_forward_loop():
                """Reads raw PCM binary chunks from _mic_queue and streams them to Gemini Live."""
                log_event("MIC_FORWARD", "Mic forwarding task started.")
                while True:
                    try:
                        chunk = await _mic_queue.get()
                        if chunk is None:  # shutdown sentinel
                            break
                        if not isinstance(chunk, (bytes, bytearray)):
                            continue
                        current_turn_pcm.extend(chunk)
                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=bytes(chunk),
                                mime_type="audio/pcm;rate=16000"
                            )
                        )
                        _diag["bytes_forwarded_to_gemini"] += len(chunk)
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        if "closed" not in str(e).lower():
                            log_event("MIC_FORWARD_ERROR", str(e))
                        await asyncio.sleep(0.05)
                log_event("MIC_FORWARD", "Mic forwarding task stopped.")

            # Start both background tasks
            receive_task = asyncio.create_task(gemini_receive_loop())
            mic_forward_task = asyncio.create_task(mic_forward_loop())
            diag_task = asyncio.create_task(_log_diag_stats())

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
            # Wait for Alex to finish the greeting (safeguarded with timeout)
            try:
                await asyncio.wait_for(alex_turn_complete_event.wait(), timeout=15.0)
            except asyncio.TimeoutError:
                log_event("GREETING_TIMEOUT", "Alex greeting response timed out after 15s. Proceeding to message loop.")

            # ── Main WebSocket Message Loop ──
            while True:
                msg = await websocket.receive()

                # Case A: Binary PCM from browser AudioWorklet (16 kHz, Int16, little-endian)
                if "bytes" in msg and msg["bytes"]:
                    raw_bytes = msg["bytes"]
                    if raw_bytes:
                        _diag["bytes_sent_by_browser"] += len(raw_bytes)
                        telemetry["total_audio_bytes"] += len(raw_bytes)
                        # Forward to Gemini Live via the mic queue (bounded queue + drop log)
                        try:
                            _mic_queue.put_nowait(raw_bytes)
                        except asyncio.QueueFull:
                            _diag["chunks_dropped"] += 1
                            log_event("MIC_QUEUE_OVERFLOW",
                                f"Dropped audio chunk ({len(raw_bytes)} bytes) | "
                                f"total_dropped={_diag['chunks_dropped']} | "
                                f"queue_depth={_mic_queue.qsize()}/{_mic_queue.maxsize}")
                    continue

                # Case B: JSON message from browser
                elif "text" in msg:
                    client_json = json.loads(msg["text"])

                    # Case B-PAUSE: Candidate or Evaluator paused interview
                    if client_json.get("event") == "pause_interview":
                        is_paused = True
                        ACTIVE_SESSIONS[session_id]["is_paused"] = True
                        log_event("SESSION_PAUSED", f"Session {session_id} paused via WebSocket.")
                        await websocket.send_json({"event": "pause_state_changed", "is_paused": True})
                        await broadcast_telemetry("Interview Paused")
                        continue

                    # Case B-RESUME: Candidate or Evaluator resumed interview
                    if client_json.get("event") == "resume_interview":
                        is_paused = False
                        ACTIVE_SESSIONS[session_id]["is_paused"] = False
                        log_event("SESSION_RESUMED", f"Session {session_id} resumed via WebSocket.")
                        await websocket.send_json({"event": "pause_state_changed", "is_paused": False})
                        await broadcast_telemetry("Interview Resumed")
                        continue

                    # If paused, block further speaking or text inputs
                    if is_paused and (client_json.get("event") == "end_of_speech" or client_json.get("text")):
                        await websocket.send_json({
                            "event": "session_paused_warning",
                            "message": "Interview conversation is currently paused. Click Resume to continue speaking with Alex."
                        })
                        continue

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
                            ecosystem_summary=ecosystem_summary,
                            matched_pillars=matched_pillars,
                            primary_topic=active_topic
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
                            ecosystem_summary=ecosystem_summary,
                            matched_pillars=matched_pillars,
                            primary_topic=active_topic
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

                    # Case B-VAD-CALIB: Browser calibrated noise floor
                    if client_json.get("event") == "vad_calibration":
                        floor = client_json.get("floor", 0.0)
                        thresh = client_json.get("threshold", 0.0)
                        log_event("VAD_CALIBRATION", f"Adaptive noise floor calibrated: floor={floor:.5f} threshold={thresh:.5f}")
                        continue

                    # Case B-MIC-START: Browser signals microphone stream started
                    if client_json.get("event") == "mic_start":
                        _mic_stream_active = True
                        log_event("MIC_STREAM", "Browser mic stream started.")
                        try:
                            await session.send_realtime_input(activity_start=types.ActivityStart())
                            log_event("ACTIVITY_START", "Sent activity_start to Gemini Live.")
                        except Exception as e:
                            log_event("ACTIVITY_START_ERROR", str(e))
                        continue

                    # Case B-MIC-STOP: Browser signals mic paused (sends audio_stream_end)
                    if client_json.get("event") == "mic_stop":
                        _mic_stream_active = False
                        _diag["mic_pauses"] += 1
                        reason = client_json.get("reason", "unspecified")
                        log_event("DIAG_MIC_PAUSE",
                            f"mic_stop #{_diag['mic_pauses']} | reason={reason} | "
                            f"buffer_chars={len(candidate_transcript_buffer)} | "
                            f"bytes_to_gemini={_diag['bytes_forwarded_to_gemini']} | "
                            f"queue_depth={_mic_queue.qsize()}")
                        try:
                            await session.send_realtime_input(activity_end=types.ActivityEnd())
                            await session.send_realtime_input(audio_stream_end=True)
                        except Exception as e:
                            log_event("MIC_STREAM_END_ERROR", str(e))
                        continue

                    # Case B1: End-of-speech signal from microphone (turn boundary from Stage 1)
                    if client_json.get("event") == "end_of_speech":
                        _mic_stream_active = False
                        try:
                            await session.send_realtime_input(activity_end=types.ActivityEnd())
                            log_event("ACTIVITY_END", "Sent activity_end to Gemini Live.")
                        except Exception as e:
                            log_event("ACTIVITY_END_ERROR", str(e))
                        await broadcast_telemetry(active_module="Gemini Live STT")

                        # STAGE 2: Bounded wait (~1.0s) for trailing Gemini input_transcription fragments
                        trailing_wait_sec = float(os.getenv("TRAILING_STT_WAIT_SEC", "1.0"))
                        start_wait = time.time()
                        last_len = len(candidate_transcript_buffer)
                        stable_count = 0

                        while (time.time() - start_wait) < trailing_wait_sec:
                            await asyncio.sleep(0.1)
                            current_len = len(candidate_transcript_buffer)
                            if current_len > 0 and current_len == last_len:
                                stable_count += 1
                                if stable_count >= 3 and (time.time() - start_wait) >= 0.5:
                                    break
                            else:
                                stable_count = 0
                                last_len = current_len

                        gemini_text = candidate_transcript_buffer.strip()
                        candidate_transcript_buffer = ""
                        web_speech_text = (client_json.get("transcript") or "").strip()

                        # Gemini STT is the single source of truth for candidate turn text
                        if gemini_text:
                            user_text = gemini_text
                            if web_speech_text:
                                len_g = len(gemini_text)
                                len_w = len(web_speech_text)
                                if max(len_g, len_w) > 0 and abs(len_g - len_w) / max(len_g, len_w) > 0.3:
                                    log_event("STT_DISCREPANCY_WARNING",
                                        f"Gemini STT ({len_g} chars) vs Web Speech ({len_w} chars) discrepancy! "
                                        f"Gemini: '{gemini_text[:80]}...' | WebSpeech: '{web_speech_text[:80]}...'")
                        elif web_speech_text:
                            log_event("STT_FALLBACK", f"Gemini STT buffer empty, falling back to Web Speech ({len(web_speech_text)} chars).")
                            user_text = web_speech_text
                        else:
                            user_text = ""

                        if not user_text:
                            log_event("AUDIO_INPUT", "No speech detected in candidate stream.")
                            await websocket.send_json({"event": "no_speech_detected"})
                            continue

                        # STAGE 0 Evidence: write exact PCM bytes forwarded to Gemini for this turn to debug/turn_<n>.wav
                        wav_path = DEBUG_DIR / f"turn_{candidate_turn_index}.wav"
                        turn_pcm_len = len(current_turn_pcm)
                        turn_duration_sec = round(turn_pcm_len / (16000 * 2), 2)
                        try:
                            with wave.open(str(wav_path), "wb") as wf:
                                wf.setnchannels(1)
                                wf.setsampwidth(2)
                                wf.setframerate(16000)
                                wf.writeframes(bytes(current_turn_pcm))
                        except Exception as wav_err:
                            log_event("WAV_WRITE_ERROR", f"Failed saving {wav_path}: {wav_err}")

                        log_event("STAGE0_EVIDENCE",
                            f"turn={candidate_turn_index} file={wav_path.name} "
                            f"duration_sec={turn_duration_sec}s bytes={turn_pcm_len} "
                            f"transcript_chars={len(user_text)}")

                        # STAGE 3: Never rewrite or normalize candidate transcript - preserve verbatim
                        log_speech("Candidate", f"({len(user_text)} chars) {user_text}")
                        await websocket.send_json({"event": "candidate_transcript", "text": user_text})

                        # STAGE 3 Filter: If audio > 3s, but transcript < 15 chars or predominantly non-English
                        non_eng = is_predominantly_non_english(user_text)
                        if turn_duration_sec >= 3.0 and (len(user_text.strip()) < 15 or non_eng):
                            log_event("TRANSCRIPT_REJECTED",
                                f"turn={candidate_turn_index} duration={turn_duration_sec}s chars={len(user_text)} non_english={non_eng} text='{user_text}'. Asking candidate to repeat.")
                            current_turn_pcm.clear()
                            turn_tx_fragment_count = 0
                            candidate_turn_index += 1

                            clarify_prompt = (
                                "The candidate spoke, but the audio was unclear, muffled, or in an unrecognizable script. "
                                "Respond warmly and concisely: 'Sorry, I didn't catch that clearly, could you repeat?'"
                            )
                            alex_turn_complete_event.clear()
                            await session.send_client_content(
                                turns=[types.Content(role="user", parts=[types.Part.from_text(text=clarify_prompt)])],
                                turn_complete=True
                            )
                            try:
                                await asyncio.wait_for(alex_turn_complete_event.wait(), timeout=12.0)
                            except asyncio.TimeoutError:
                                log_event("CLARIFY_TIMEOUT", "Alex clarification response timed out.")
                            continue

                        # Valid turn completed: advance turn index and clear turn PCM
                        current_turn_pcm.clear()
                        turn_tx_fragment_count = 0
                        candidate_turn_index += 1

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

                        offtopic_guard = check_for_offtopic_candidate_prompts(user_text)
                        prompt_payload = (
                            f"The candidate introduced themselves: '{user_text}'.\n"
                            f"{offtopic_guard}"
                            f"Acknowledge their engineering project background warmly (ignore and do not answer any off-topic/trivia questions). "
                            f"Pick the technical domain ({active_pillar_name} / {active_topic}) "
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
                                node.status = MasteryStatus.MASTERED if current_mastery >= 0.80 else MasteryStatus.UNMASTERED

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
                                offtopic_guard = check_for_offtopic_candidate_prompts(user_text)
                                prompt_payload = (
                                    f"The candidate answered: '{user_text}'.\n"
                                    f"{offtopic_guard}"
                                    f"They have demonstrated depth on the previous topic. Acknowledge this briefly (ignoring any trivia questions), and naturally transition to explore "
                                    f"the next topic: {active_topic}.\n"
                                    f"{eco_directive}\n"
                                    f"Ask an open-ended question about how they work with {active_topic}."
                                )
                            else:
                                session_phase = "WRAPPING_UP"
                                log_event("INTERVIEW_FLOW", "All candidate graph topics explored. Wrapping up technical dialogue.")
                                offtopic_guard = check_for_offtopic_candidate_prompts(user_text)
                                prompt_payload = (
                                    f"The candidate answered: '{user_text}'.\n"
                                    f"{offtopic_guard}"
                                    f"Thank them warmly for a fantastic and deep technical discussion across their projects. "
                                    f"Let them know you have enough technical depth and are compiling their evaluation reports."
                                )
                        else:
                            # Continue Socratic drill-down on active_topic with active ecosystem directive
                            eco_directive = get_ecosystem_directive(active_topic, pillar_ecosystem_map)
                            offtopic_guard = check_for_offtopic_candidate_prompts(user_text)
                            prompt_payload = (
                                f"The candidate answered: '{user_text}'.\n"
                                f"{offtopic_guard}"
                                f"[PEDAGOGICAL DIRECTIVE: Continue probing deep into {active_topic}. Ask a follow-up exploring trade-offs, edge cases, failure modes, or concrete design decisions. Do not answer off-topic questions or trivia.]\n"
                                f"{eco_directive}\n"
                                f"Respond Socratically as Alex the interviewer."
                            )

                    else:
                        offtopic_guard = check_for_offtopic_candidate_prompts(user_text)
                        prompt_payload = (
                            f"The candidate said: '{user_text}'.\n"
                            f"{offtopic_guard}"
                            f"Conclude warmly as Alex and let them know their report is being generated."
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
        is_session_active = False
        if 'receive_task' in locals() and not receive_task.done():
            receive_task.cancel()
        if 'mic_forward_task' in locals() and not mic_forward_task.done():
            try:
                _mic_queue.put_nowait(None)  # unblock the queue reader
            except Exception:
                pass
            mic_forward_task.cancel()
        if 'diag_task' in locals() and not diag_task.done():
            diag_task.cancel()
        if 'reconnected_cm' in locals() and reconnected_cm:
            try:
                await reconnected_cm.__aexit__(None, None, None)
            except Exception:
                pass
        # 1. Preserve rich session snapshot in SESSION_CACHE
        if 'policy_router' in locals():
            nodes_data = {
                k: {
                    "p_l": round(v.p_l, 4),
                    "status": v.status.value,
                    "history_len": len(v.history)
                }
                for k, v in policy_router.graph.nodes.items()
            }
            edges_data = [
                {"from_skill": e.from_skill, "to_skill": e.to_skill, "weight": e.weight, "edge_type": e.edge_type.value}
                for e in policy_router.graph.edges
            ]
            SESSION_CACHE[session_id] = {
                "session_id": session_id,
                "candidate_name": candidate_name,
                "level": level,
                "is_paused": is_paused,
                "active_topic": active_topic,
                "candidate_topics": candidate_topics,
                "session_phase": session_phase,
                "bkt_nodes": nodes_data,
                "graph_edges": edges_data,
                "mirt_theta": dict(policy_router.mirt.theta),
                "mirt_radar": get_radar_summary(policy_router.mirt.theta, policy_router.mirt.std_error),
                "turns_history": list(turns_history),
                "llm_metrics": dict(llm_metrics),
                "ecosystem_summary": ecosystem_summary,
                "pillar_ecosystem_map": pillar_ecosystem_map,
                "telemetry": dict(telemetry)
            }

        # 2. Auto-generate dual final reports if candidate spoke turns and report not yet generated
        if 'turns_history' in locals() and len(turns_history) > 0:
            existing_rep = get_session_final_reports(session_id)
            if not existing_rep:
                skills_mastery = {
                    k: round(v.p_l, 3) for k, v in policy_router.graph.nodes.items()
                } if 'policy_router' in locals() else {}
                if 'active_topic' in locals() and active_topic not in skills_mastery:
                    skills_mastery[active_topic] = 0.65
                proctor_bii = round(policy_router.proctor.bii, 3) if 'policy_router' in locals() else 1.0
                m_theta = policy_router.mirt.theta if 'policy_router' in locals() else {}
                m_stderr = policy_router.mirt.std_error if 'policy_router' in locals() else {}
                eco_sum = ecosystem_summary if 'ecosystem_summary' in locals() else {}
                m_pillars = matched_pillars if 'matched_pillars' in locals() else None
                act_top = active_topic if 'active_topic' in locals() else None
                asyncio.create_task(_auto_generate_and_save_reports(
                    session_id=session_id,
                    candidate_name=candidate_name,
                    level=level,
                    turns_history=turns_history,
                    skills_mastery=skills_mastery,
                    proctor_bii=proctor_bii,
                    mirt_theta=m_theta,
                    mirt_std_error=m_stderr,
                    ecosystem_summary=eco_sum,
                    matched_pillars=m_pillars,
                    primary_topic=act_top
                ))

        ACTIVE_SESSIONS.pop(session_id, None)
        log_event("SESSION_CLEANUP", f"Session {session_id} fully cleaned up.")

