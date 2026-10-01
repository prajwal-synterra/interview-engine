"""
PostgreSQL Relational Database Service.
Document Reference: AIS-UPGRADE-2026-V1 / REPORT 7
Manages persistent session blueprints, turn telemetry logs, compacted topic cards, and final reports.
"""

import os
import json
import uuid
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Attempt pure-Python pg8000 first (Windows WDAC safe, 0 DLLs), fallback to psycopg2
try:
    import pg8000.dbapi as pg_driver
    USE_PG8000 = True
except ImportError:
    try:
        import psycopg2 as pg_driver
        USE_PG8000 = False
    except ImportError as e:
        pg_driver = None
        USE_PG8000 = False
        print(f"[DBService Warning]: No PostgreSQL driver available: {e}")

PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "interview-engine")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "0608")


def get_db_connection():
    """Returns a raw database connection using pg8000 or psycopg2."""
    if pg_driver is None:
        raise RuntimeError("No PostgreSQL driver installed.")
    if USE_PG8000:
        return pg_driver.connect(
            user=PG_USER,
            password=PG_PASSWORD,
            host=PG_HOST,
            port=PG_PORT,
            database=PG_DB
        )
    else:
        return pg_driver.connect(
            host=PG_HOST,
            port=PG_PORT,
            database=PG_DB,
            user=PG_USER,
            password=PG_PASSWORD
        )


def rows_to_dicts(cur, rows) -> List[Dict[str, Any]]:
    """Converts DB rows into dictionary format using cursor description."""
    if not cur.description or not rows:
        return []
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in rows]


def row_to_dict(cur, row) -> Optional[Dict[str, Any]]:
    """Converts a single DB row into dictionary format."""
    if not cur.description or not row:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))



from contextlib import contextmanager

@contextmanager
def get_cursor(conn):
    """Context manager for DB cursor supporting pg8000 and psycopg2."""
    cur = conn.cursor()
    try:
        yield cur
    finally:
        try:
            cur.close()
        except Exception:
            pass


def init_db():
    """Initializes tables in the public schema of interview-engine database."""
    conn = get_db_connection()
    try:
        with get_cursor(conn) as cur:
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
        with get_cursor(conn) as cur:
            cur.execute("""
                INSERT INTO interview_sessions (session_id, candidate_name, seniority_tier, intro_blueprint, status)
                VALUES (%s, %s, %s, %s::jsonb, 'IN_PROGRESS')
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
        with get_cursor(conn) as cur:
            cur.execute("""
                UPDATE interview_sessions
                SET intro_blueprint = %s::jsonb, detected_ecosystem = %s
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
        with get_cursor(conn) as cur:
            cur.execute("""
                INSERT INTO compacted_topic_cards (
                    card_id, session_id, topic_code, turns_spent, final_mastery_p_l, status, verdict_summary, strengths_cited, gaps_identified
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb);
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
        with get_cursor(conn) as cur:
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
        with get_cursor(conn) as cur:
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
            """, (
                report_id, session_id, student_report, evaluator_report,
                hiring_verdict, average_mastery, proctor_integrity_score
            ))

            cur.execute("""
                UPDATE interview_sessions
                SET status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP
                WHERE session_id = %s;
            """, (session_id,))
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
        with get_cursor(conn) as cur:
            cur.execute("""
                SELECT topic_code, turns_spent, final_mastery_p_l, status, verdict_summary, strengths_cited, gaps_identified, created_at
                FROM compacted_topic_cards
                WHERE session_id = %s
                ORDER BY created_at ASC;
            """, (session_id,))
            return rows_to_dicts(cur, cur.fetchall())
    except Exception as e:
        print(f"[DBService] Error fetching compacted cards for {session_id}: {e}")
        return []
    finally:
        conn.close()


def get_all_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves all sessions ordered by creation date desc."""
    conn = get_db_connection()
    try:
        with get_cursor(conn) as cur:
            cur.execute("""
                SELECT s.session_id, s.candidate_name, s.seniority_tier, s.detected_ecosystem,
                       s.status, s.created_at, s.completed_at,
                       r.hiring_verdict, r.average_mastery, r.proctor_integrity_score
                FROM interview_sessions s
                LEFT JOIN final_reports r ON s.session_id = r.session_id
                ORDER BY s.created_at DESC
                LIMIT %s;
            """, (limit,))
            rows = rows_to_dicts(cur, cur.fetchall())
            for r in rows:
                if r.get("created_at") and hasattr(r["created_at"], "strftime"):
                    r["created_at"] = r["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                if r.get("completed_at") and hasattr(r["completed_at"], "strftime"):
                    r["completed_at"] = r["completed_at"].strftime("%Y-%m-%d %H:%M:%S")
            return rows
    except Exception as e:
        print(f"[DBService] Error fetching all sessions: {e}")
        return []
    finally:
        conn.close()


def get_session_by_id(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single session record including blueprint."""
    conn = get_db_connection()
    try:
        with get_cursor(conn) as cur:
            cur.execute("""
                SELECT session_id, candidate_name, seniority_tier, detected_ecosystem,
                       status, intro_blueprint, created_at, completed_at
                FROM interview_sessions
                WHERE session_id = %s;
            """, (session_id,))
            row = row_to_dict(cur, cur.fetchone())
            if row:
                if row.get("created_at") and hasattr(row["created_at"], "strftime"):
                    row["created_at"] = row["created_at"].strftime("%Y-%m-%d %H:%M:%S")
                if row.get("completed_at") and hasattr(row["completed_at"], "strftime"):
                    row["completed_at"] = row["completed_at"].strftime("%Y-%m-%d %H:%M:%S")
            return row
    except Exception as e:
        print(f"[DBService] Error fetching session {session_id}: {e}")
        return None
    finally:
        conn.close()


def get_session_turns(session_id: str) -> List[Dict[str, Any]]:
    """Retrieves all turn telemetry logs for a session."""
    conn = get_db_connection()
    try:
        with get_cursor(conn) as cur:
            cur.execute("""
                SELECT turn_id, turn_index, topic, interviewer_prompt, candidate_transcript,
                       latency_ms, evaluator_observation, depth_score, bkt_prior, bkt_posterior,
                       proctor_bii, created_at
                FROM turn_telemetry_logs
                WHERE session_id = %s
                ORDER BY turn_index ASC;
            """, (session_id,))
            rows = rows_to_dicts(cur, cur.fetchall())
            for r in rows:
                if r.get("created_at") and hasattr(r["created_at"], "strftime"):
                    r["created_at"] = r["created_at"].strftime("%H:%M:%S")
            return rows
    except Exception as e:
        print(f"[DBService] Error fetching turns for {session_id}: {e}")
        return []
    finally:
        conn.close()


def get_session_final_reports(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves saved final reports for a session."""
    conn = get_db_connection()
    try:
        with get_cursor(conn) as cur:
            cur.execute("""
                SELECT report_id, session_id, student_compass_markdown, evaluator_audit_markdown,
                       hiring_verdict, average_mastery, proctor_integrity_score, generated_at
                FROM final_reports
                WHERE session_id = %s;
            """, (session_id,))
            row = row_to_dict(cur, cur.fetchone())
            if row and row.get("generated_at") and hasattr(row["generated_at"], "strftime"):
                row["generated_at"] = row["generated_at"].strftime("%Y-%m-%d %H:%M:%S")
            return row
    except Exception as e:
        print(f"[DBService] Error fetching final reports for {session_id}: {e}")
        return None
    finally:
        conn.close()


def get_all_reports() -> List[Dict[str, Any]]:
    """Retrieves all reports joined with session data."""
    conn = get_db_connection()
    try:
        with get_cursor(conn) as cur:
            cur.execute("""
                SELECT r.report_id, r.session_id, r.hiring_verdict, r.average_mastery,
                       r.proctor_integrity_score, r.generated_at,
                       s.candidate_name, s.seniority_tier, s.detected_ecosystem,
                       s.intro_blueprint
                FROM final_reports r
                JOIN interview_sessions s ON r.session_id = s.session_id
                ORDER BY r.generated_at DESC;
            """, ())
            rows = rows_to_dicts(cur, cur.fetchall())
            for r in rows:
                if r.get("generated_at") and hasattr(r["generated_at"], "strftime"):
                    r["generated_at"] = r["generated_at"].strftime("%Y-%m-%d %H:%M:%S")
                bp = r.get("intro_blueprint") or {}
                matched = bp.get("matched_pillars") or []
                if matched:
                    r["primary_domain"] = matched[0].get("name") or matched[0].get("pillar_id")
                else:
                    cand_topics = bp.get("candidate_topics") or []
                    r["primary_domain"] = cand_topics[0] if cand_topics else (r.get("detected_ecosystem") or "Core Systems")
            return rows
    except Exception as e:
        print(f"[DBService] Error fetching all reports: {e}")
        return []
    finally:
        conn.close()


def get_database_stats() -> Dict[str, Any]:
    """Retrieves summary row counts and health stats from PostgreSQL."""
    conn = get_db_connection()
    try:
        with get_cursor(conn) as cur:
            cur.execute("SELECT COUNT(*) FROM interview_sessions;")
            sessions_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM compacted_topic_cards;")
            cards_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM turn_telemetry_logs;")
            turns_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM final_reports;")
            reports_count = cur.fetchone()[0]
            return {
                "sessions_count": sessions_count,
                "compacted_cards_count": cards_count,
                "turn_logs_count": turns_count,
                "final_reports_count": reports_count,
                "status": "ONLINE",
                "host": PG_HOST,
                "database": PG_DB
            }
    except Exception as e:
        return {
            "sessions_count": 0,
            "compacted_cards_count": 0,
            "turn_logs_count": 0,
            "final_reports_count": 0,
            "status": f"OFFLINE ({e})",
            "host": PG_HOST,
            "database": PG_DB
        }
    finally:
        conn.close()

