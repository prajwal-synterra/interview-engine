"""
PostgreSQL Relational Database Service.
Document Reference: AIS-UPGRADE-2026-V1 / REPORT 7
Manages persistent session blueprints, turn telemetry logs, compacted topic cards, and final reports.
"""

import os
import json
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "interview-engine")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "0608")


def get_db_connection():
    """Returns a raw psycopg2 database connection."""
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD
    )


def init_db():
    """Initializes tables in the public schema of interview-engine database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Interview Sessions Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS interview_sessions (
                    session_id VARCHAR(64) PRIMARY KEY,
                    candidate_name VARCHAR(100) NOT NULL,
                    seniority_tier VARCHAR(20) NOT NULL,
                    detected_ecosystem VARCHAR(50) DEFAULT 'POLYGLOT',
                    status VARCHAR(20) DEFAULT 'IN_PROGRESS',
                    intro_blueprint JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                );
            """)

            # 2. Compacted Topic Cards Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS compacted_topic_cards (
                    card_id VARCHAR(64) PRIMARY KEY,
                    session_id VARCHAR(64) REFERENCES interview_sessions(session_id) ON DELETE CASCADE,
                    topic_code VARCHAR(100) NOT NULL,
                    turns_spent INT NOT NULL,
                    final_mastery_p_l FLOAT NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    verdict_summary TEXT NOT NULL,
                    strengths_cited JSONB DEFAULT '[]'::jsonb,
                    gaps_identified JSONB DEFAULT '[]'::jsonb,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 3. Turn Telemetry Logs Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS turn_telemetry_logs (
                    turn_id VARCHAR(64) PRIMARY KEY,
                    session_id VARCHAR(64) REFERENCES interview_sessions(session_id) ON DELETE CASCADE,
                    turn_index INT NOT NULL,
                    topic VARCHAR(100) NOT NULL,
                    interviewer_prompt TEXT NOT NULL,
                    candidate_transcript TEXT NOT NULL,
                    latency_ms INT DEFAULT 0,
                    evaluator_observation INT DEFAULT 0,
                    depth_score FLOAT DEFAULT 0.0,
                    bkt_prior FLOAT DEFAULT 0.35,
                    bkt_posterior FLOAT DEFAULT 0.35,
                    proctor_bii FLOAT DEFAULT 1.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 4. Final Assessment Reports Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS final_reports (
                    report_id VARCHAR(64) PRIMARY KEY,
                    session_id VARCHAR(64) UNIQUE REFERENCES interview_sessions(session_id) ON DELETE CASCADE,
                    student_compass_markdown TEXT NOT NULL,
                    evaluator_audit_markdown TEXT NOT NULL,
                    hiring_verdict VARCHAR(50) NOT NULL,
                    average_mastery FLOAT NOT NULL,
                    proctor_integrity_score FLOAT NOT NULL,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.commit()
        print(f"[DBService] PostgreSQL tables initialized successfully on {PG_HOST}:{PG_PORT}/{PG_DB}.")
    except Exception as e:
        conn.rollback()
        print(f"[DBService] Error initializing PostgreSQL tables: {e}")
    finally:
        conn.close()


def create_session(session_id: str, candidate_name: str, seniority_tier: str, intro_blueprint: Optional[Dict[str, Any]] = None):
    """Creates a new candidate session record."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO interview_sessions (session_id, candidate_name, seniority_tier, intro_blueprint, status)
                VALUES (%s, %s, %s, %s, 'IN_PROGRESS')
                ON CONFLICT (session_id) DO UPDATE SET
                    candidate_name = EXCLUDED.candidate_name,
                    seniority_tier = EXCLUDED.seniority_tier,
                    intro_blueprint = COALESCE(EXCLUDED.intro_blueprint, interview_sessions.intro_blueprint);
            """, (session_id, candidate_name, seniority_tier, json.dumps(intro_blueprint) if intro_blueprint else None))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[DBService] Error creating session {session_id}: {e}")
    finally:
        conn.close()


def update_session_blueprint(session_id: str, intro_blueprint: Dict[str, Any], ecosystem: str = "POLYGLOT"):
    """Updates the session with the permanent Intro Blueprint and detected ecosystem."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE interview_sessions
                SET intro_blueprint = %s, detected_ecosystem = %s
                WHERE session_id = %s;
            """, (json.dumps(intro_blueprint), ecosystem, session_id))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[DBService] Error updating blueprint for session {session_id}: {e}")
    finally:
        conn.close()


def save_compacted_topic_card(
    session_id: str,
    topic_code: str,
    turns_spent: int,
    final_mastery_p_l: float,
    status: str,
    verdict_summary: str,
    strengths_cited: Optional[List[str]] = None,
    gaps_identified: Optional[List[str]] = None
) -> str:
    """Inserts a finalized Compacted Topic Card into PostgreSQL."""
    card_id = f"card_{uuid.uuid4().hex[:12]}"
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO compacted_topic_cards (
                    card_id, session_id, topic_code, turns_spent, final_mastery_p_l, status, verdict_summary, strengths_cited, gaps_identified
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                card_id, session_id, topic_code, turns_spent, final_mastery_p_l, status,
                verdict_summary, json.dumps(strengths_cited or []), json.dumps(gaps_identified or [])
            ))
        conn.commit()
        return card_id
    except Exception as e:
        conn.rollback()
        print(f"[DBService] Error saving compacted topic card: {e}")
        return card_id
    finally:
        conn.close()


def log_turn_telemetry(
    session_id: str,
    turn_index: int,
    topic: str,
    interviewer_prompt: str,
    candidate_transcript: str,
    latency_ms: int,
    evaluator_observation: int,
    depth_score: float,
    bkt_prior: float,
    bkt_posterior: float,
    proctor_bii: float
):
    """Persists detailed turn telemetry log."""
    turn_id = f"turn_{uuid.uuid4().hex[:12]}"
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO turn_telemetry_logs (
                    turn_id, session_id, turn_index, topic, interviewer_prompt, candidate_transcript,
                    latency_ms, evaluator_observation, depth_score, bkt_prior, bkt_posterior, proctor_bii
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                turn_id, session_id, turn_index, topic, interviewer_prompt, candidate_transcript,
                latency_ms, evaluator_observation, depth_score, bkt_prior, bkt_posterior, proctor_bii
            ))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"[DBService] Error logging turn telemetry: {e}")
    finally:
        conn.close()


def save_final_reports(
    session_id: str,
    student_report: str,
    evaluator_report: str,
    hiring_verdict: str,
    average_mastery: float,
    proctor_integrity_score: float
):
    """Saves the dual generated assessment reports into PostgreSQL."""
    report_id = f"rep_{uuid.uuid4().hex[:12]}"
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO final_reports (
                    report_id, session_id, student_compass_markdown, evaluator_audit_markdown,
                    hiring_verdict, average_mastery, proctor_integrity_score
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE SET
                    student_compass_markdown = EXCLUDED.student_compass_markdown,
                    evaluator_audit_markdown = EXCLUDED.evaluator_audit_markdown,
                    hiring_verdict = EXCLUDED.hiring_verdict,
                    average_mastery = EXCLUDED.average_mastery,
                    proctor_integrity_score = EXCLUDED.proctor_integrity_score;

                UPDATE interview_sessions
                SET status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP
                WHERE session_id = %s;
            """, (
                report_id, session_id, student_report, evaluator_report,
                hiring_verdict, average_mastery, proctor_integrity_score, session_id
            ))
        conn.commit()
        print(f"[DBService] Dual reports archived in PostgreSQL for session {session_id}.")
    except Exception as e:
        conn.rollback()
        print(f"[DBService] Error saving final reports: {e}")
    finally:
        conn.close()


def get_session_compacted_cards(session_id: str) -> List[Dict[str, Any]]:
    """Retrieves all compacted topic cards for a session."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT topic_code, turns_spent, final_mastery_p_l, status, verdict_summary, strengths_cited, gaps_identified, created_at
                FROM compacted_topic_cards
                WHERE session_id = %s
                ORDER BY created_at ASC;
            """, (session_id,))
            return list(cur.fetchall())
    except Exception as e:
        print(f"[DBService] Error fetching compacted cards for {session_id}: {e}")
        return []
    finally:
        conn.close()
