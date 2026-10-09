"""
Database Persistence Service.
Implements the 4-table persistence model defined in AIS-ARCH-2026-V3-MASTER:
1. interview_sessions
2. turn_telemetry_logs
3. compacted_topic_cards
4. final_reports

Connects to PostgreSQL using pg8000 (pure Python, immune to Windows DLL / AppLocker restrictions)
via asyncio.to_thread for high-throughput non-blocking operations, with a transparent SQLite fallback.
"""

import os
import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
from dotenv import load_dotenv

# Ensure .env is resolved reliably from workspace root
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT_DIR, ".env")
load_dotenv(ENV_PATH)

try:
    import pg8000.dbapi
except ImportError:
    pg8000 = None

try:
    import aiosqlite
except ImportError:
    aiosqlite = None


DATABASE_URL = os.getenv("DATABASE_URL")
SQLITE_DB_PATH = os.path.join(ROOT_DIR, "interview_engine.db")


class DatabaseService:
    """Unified Async Database Service supporting PostgreSQL and SQLite fallback."""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or DATABASE_URL
        self.is_sqlite = False
        self.pg_creds: Optional[Dict[str, Any]] = None

        if self.db_url and pg8000:
            try:
                parsed = urlparse(self.db_url)
                if parsed.scheme in ("postgresql", "postgres"):
                    self.pg_creds = {
                        "user": parsed.username or "postgres",
                        "password": parsed.password or "",
                        "host": parsed.hostname or "localhost",
                        "port": parsed.port or 5432,
                        "database": parsed.path.lstrip("/") or "postgres"
                    }
            except Exception as e:
                print(f"[DatabaseService Warning] Failed to parse DATABASE_URL: {e}")

    def _sync_pg_execute(self, query: str, params: tuple = (), fetch: str = "none") -> Any:
        """Executes a query against PostgreSQL synchronously (called inside asyncio.to_thread)."""
        if not self.pg_creds or not pg8000:
            raise RuntimeError("PostgreSQL credentials or pg8000 driver not available")

        conn = pg8000.dbapi.connect(
            user=self.pg_creds["user"],
            password=self.pg_creds["password"],
            host=self.pg_creds["host"],
            port=self.pg_creds["port"],
            database=self.pg_creds["database"]
        )
        try:
            cur = conn.cursor()
            if params is not None:
                cur.execute(query, params)
            else:
                cur.execute(query)
            if fetch == "one":
                row = cur.fetchone()
                if row and cur.description:
                    cols = [d[0] for d in cur.description]
                    return dict(zip(cols, row))
                return None
            elif fetch == "all":
                rows = cur.fetchall()
                if rows and cur.description:
                    cols = [d[0] for d in cur.description]
                    return [dict(zip(cols, r)) for r in rows]
                return []
            conn.commit()
            return True
        finally:
            conn.close()

    async def initialize(self):
        """Initializes connection and ensures all 4 tables exist."""
        if self.pg_creds and pg8000:
            try:
                # Test connectivity
                await asyncio.to_thread(self._sync_pg_execute, "SELECT 1;", (), "one")
                self.is_sqlite = False
                print(f"[DatabaseService] Connected to PostgreSQL successfully (db: {self.pg_creds['database']}).")
            except Exception as e:
                print(f"[DatabaseService Warning] PostgreSQL connection failed ({e}). Falling back to local SQLite.")
                self.is_sqlite = True
        else:
            self.is_sqlite = True

        if self.is_sqlite:
            print(f"[DatabaseService] Using asynchronous SQLite database: {SQLITE_DB_PATH}")

        await self._create_tables()

    async def _create_tables(self):
        """Creates the 4 core relational tables if they do not exist."""
        if not self.is_sqlite:
            # PostgreSQL schema creation
            schema_sql = """
                CREATE TABLE IF NOT EXISTS interview_sessions (
                    session_id VARCHAR(64) PRIMARY KEY,
                    candidate_name VARCHAR(100) NOT NULL,
                    seniority_tier VARCHAR(20) NOT NULL,
                    detected_ecosystem VARCHAR(50),
                    status VARCHAR(20) DEFAULT 'IN_PROGRESS',
                    intro_blueprint JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS turn_telemetry_logs (
                    turn_id VARCHAR(64) PRIMARY KEY,
                    session_id VARCHAR(64) REFERENCES interview_sessions(session_id) ON DELETE CASCADE,
                    turn_index INT NOT NULL,
                    topic VARCHAR(100) NOT NULL,
                    interviewer_prompt TEXT,
                    candidate_transcript TEXT,
                    latency_ms INT DEFAULT 0,
                    evaluator_observation INT DEFAULT 0,
                    depth_score FLOAT DEFAULT 0.0,
                    bkt_prior FLOAT DEFAULT 0.0,
                    bkt_posterior FLOAT DEFAULT 0.0,
                    proctor_bii FLOAT DEFAULT 1.0,
                    evaluator_feedback TEXT,
                    scaffolding_level INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS compacted_topic_cards (
                    card_id VARCHAR(64) PRIMARY KEY,
                    session_id VARCHAR(64) REFERENCES interview_sessions(session_id) ON DELETE CASCADE,
                    topic_code VARCHAR(100) NOT NULL,
                    turns_spent INT DEFAULT 0,
                    final_mastery_p_l FLOAT DEFAULT 0.0,
                    status VARCHAR(20) DEFAULT 'INCOMPLETE',
                    verdict_summary TEXT,
                    strengths_cited JSONB,
                    gaps_identified JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS final_reports (
                    report_id VARCHAR(64) PRIMARY KEY,
                    session_id VARCHAR(64) UNIQUE REFERENCES interview_sessions(session_id) ON DELETE CASCADE,
                    student_compass_markdown TEXT,
                    evaluator_audit_markdown TEXT,
                    hiring_verdict VARCHAR(50) NOT NULL,
                    average_mastery FLOAT DEFAULT 0.0,
                    proctor_integrity_score FLOAT DEFAULT 1.0,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """
            await asyncio.to_thread(self._sync_pg_execute, schema_sql)
        else:
            if not aiosqlite:
                raise RuntimeError("aiosqlite is not installed. Please install aiosqlite or provide a valid DATABASE_URL.")
            async with aiosqlite.connect(SQLITE_DB_PATH) as db:
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS interview_sessions (
                        session_id TEXT PRIMARY KEY,
                        candidate_name TEXT NOT NULL,
                        seniority_tier TEXT NOT NULL,
                        detected_ecosystem TEXT,
                        status TEXT DEFAULT 'IN_PROGRESS',
                        intro_blueprint TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        completed_at TEXT
                    );
                """)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS turn_telemetry_logs (
                        turn_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        turn_index INTEGER NOT NULL,
                        topic TEXT NOT NULL,
                        interviewer_prompt TEXT,
                        candidate_transcript TEXT,
                        latency_ms INTEGER DEFAULT 0,
                        evaluator_observation INTEGER DEFAULT 0,
                        depth_score REAL DEFAULT 0.0,
                        bkt_prior REAL DEFAULT 0.0,
                        bkt_posterior REAL DEFAULT 0.0,
                        proctor_bii REAL DEFAULT 1.0,
                        evaluator_feedback TEXT,
                        scaffolding_level INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id)
                    );
                """)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS compacted_topic_cards (
                        card_id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        topic_code TEXT NOT NULL,
                        turns_spent INTEGER DEFAULT 0,
                        final_mastery_p_l REAL DEFAULT 0.0,
                        status TEXT DEFAULT 'INCOMPLETE',
                        verdict_summary TEXT,
                        strengths_cited TEXT,
                        gaps_identified TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id)
                    );
                """)
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS final_reports (
                        report_id TEXT PRIMARY KEY,
                        session_id TEXT UNIQUE NOT NULL,
                        student_compass_markdown TEXT,
                        evaluator_audit_markdown TEXT,
                        hiring_verdict TEXT NOT NULL,
                        average_mastery REAL DEFAULT 0.0,
                        proctor_integrity_score REAL DEFAULT 1.0,
                        generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES interview_sessions(session_id)
                    );
                """)
                await db.commit()

    # ==========================================================================
    # 1. Sessions CRUD
    # ==========================================================================

    async def create_session(
        self,
        session_id: str,
        candidate_name: str,
        seniority_tier: str,
        detected_ecosystem: str = "GENERAL_SYSTEMS",
        intro_blueprint: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Creates a new interview session record."""
        blueprint_json = json.dumps(intro_blueprint or {})

        if not self.is_sqlite:
            query = """
                INSERT INTO interview_sessions (session_id, candidate_name, seniority_tier, detected_ecosystem, intro_blueprint)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (session_id) DO UPDATE SET
                    candidate_name = EXCLUDED.candidate_name,
                    seniority_tier = EXCLUDED.seniority_tier,
                    detected_ecosystem = EXCLUDED.detected_ecosystem,
                    intro_blueprint = EXCLUDED.intro_blueprint;
            """
            await asyncio.to_thread(self._sync_pg_execute, query, (session_id, candidate_name, seniority_tier, detected_ecosystem, blueprint_json))
        else:
            async with aiosqlite.connect(SQLITE_DB_PATH) as db:
                await db.execute("""
                    INSERT INTO interview_sessions (session_id, candidate_name, seniority_tier, detected_ecosystem, intro_blueprint)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT (session_id) DO UPDATE SET
                        candidate_name = excluded.candidate_name,
                        seniority_tier = excluded.seniority_tier,
                        detected_ecosystem = excluded.detected_ecosystem,
                        intro_blueprint = excluded.intro_blueprint;
                """, (session_id, candidate_name, seniority_tier, detected_ecosystem, blueprint_json))
                await db.commit()

        return {
            "session_id": session_id,
            "candidate_name": candidate_name,
            "seniority_tier": seniority_tier,
            "detected_ecosystem": detected_ecosystem,
            "status": "IN_PROGRESS"
        }

    async def update_session_blueprint(
        self,
        session_id: str,
        intro_blueprint: Dict,
        detected_ecosystem: Optional[str] = None,
        candidate_name: Optional[str] = None
    ) -> bool:
        """Updates the session blueprint and candidate name after candidate intro vector matching."""
        blueprint_json = json.dumps(intro_blueprint)

        if not self.is_sqlite:
            set_clauses = ["intro_blueprint = %s::jsonb"]
            params = [blueprint_json]
            if detected_ecosystem:
                set_clauses.append("detected_ecosystem = %s")
                params.append(detected_ecosystem)
            if candidate_name:
                set_clauses.append("candidate_name = %s")
                params.append(candidate_name)
            params.append(session_id)
            query = f"UPDATE interview_sessions SET {', '.join(set_clauses)} WHERE session_id = %s;"
            await asyncio.to_thread(self._sync_pg_execute, query, tuple(params))
        else:
            async with aiosqlite.connect(SQLITE_DB_PATH) as db:
                set_clauses = ["intro_blueprint = ?"]
                params = [blueprint_json]
                if detected_ecosystem:
                    set_clauses.append("detected_ecosystem = ?")
                    params.append(detected_ecosystem)
                if candidate_name:
                    set_clauses.append("candidate_name = ?")
                    params.append(candidate_name)
                params.append(session_id)
                query = f"UPDATE interview_sessions SET {', '.join(set_clauses)} WHERE session_id = ?;"
                await db.execute(query, tuple(params))
                await db.commit()

        return True

    # ==========================================================================
    # 2. Turn Telemetry CRUD
    # ==========================================================================

    async def log_turn_telemetry(
        self,
        session_id: str,
        turn_index: int,
        topic: str,
        interviewer_prompt: str,
        candidate_transcript: str,
        latency_ms: int = 0,
        evaluator_observation: int = 0,
        depth_score: float = 0.0,
        bkt_prior: float = 0.0,
        bkt_posterior: float = 0.0,
        proctor_bii: float = 1.0,
        evaluator_feedback: str = "",
        scaffolding_level: int = 0
    ) -> str:
        """Logs turn-by-turn telemetry for forensic review."""
        turn_id = f"turn_{uuid.uuid4().hex[:12]}"

        if not self.is_sqlite:
            query = """
                INSERT INTO turn_telemetry_logs (
                    turn_id, session_id, turn_index, topic, interviewer_prompt,
                    candidate_transcript, latency_ms, evaluator_observation,
                    depth_score, bkt_prior, bkt_posterior, proctor_bii,
                    evaluator_feedback, scaffolding_level
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """
            await asyncio.to_thread(self._sync_pg_execute, query, (
                turn_id, session_id, turn_index, topic, interviewer_prompt,
                candidate_transcript, latency_ms, evaluator_observation,
                depth_score, bkt_prior, bkt_posterior, proctor_bii,
                evaluator_feedback, scaffolding_level
            ))
        else:
            async with aiosqlite.connect(SQLITE_DB_PATH) as db:
                await db.execute("""
                    INSERT INTO turn_telemetry_logs (
                        turn_id, session_id, turn_index, topic, interviewer_prompt,
                        candidate_transcript, latency_ms, evaluator_observation,
                        depth_score, bkt_prior, bkt_posterior, proctor_bii,
                        evaluator_feedback, scaffolding_level
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (turn_id, session_id, turn_index, topic, interviewer_prompt,
                      candidate_transcript, latency_ms, evaluator_observation,
                      depth_score, bkt_prior, bkt_posterior, proctor_bii,
                      evaluator_feedback, scaffolding_level))
                await db.commit()

        return turn_id

    # ==========================================================================
    # 3. Compacted Topic Cards CRUD
    # ==========================================================================

    async def save_compacted_topic_card(
        self,
        session_id: str,
        topic_code: str,
        turns_spent: int,
        final_mastery_p_l: float,
        status: str,
        verdict_summary: str,
        strengths_cited: Optional[List[str]] = None,
        gaps_identified: Optional[List[str]] = None
    ) -> str:
        """Saves topic card summary when transitioning away from a technical pillar."""
        card_id = f"card_{uuid.uuid4().hex[:12]}"
        strengths_json = json.dumps(strengths_cited or [])
        gaps_json = json.dumps(gaps_identified or [])

        if not self.is_sqlite:
            query = """
                INSERT INTO compacted_topic_cards (
                    card_id, session_id, topic_code, turns_spent,
                    final_mastery_p_l, status, verdict_summary, strengths_cited, gaps_identified
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb);
            """
            await asyncio.to_thread(self._sync_pg_execute, query, (
                card_id, session_id, topic_code, turns_spent,
                final_mastery_p_l, status, verdict_summary, strengths_json, gaps_json
            ))
        else:
            async with aiosqlite.connect(SQLITE_DB_PATH) as db:
                await db.execute("""
                    INSERT INTO compacted_topic_cards (
                        card_id, session_id, topic_code, turns_spent,
                        final_mastery_p_l, status, verdict_summary, strengths_cited, gaps_identified
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (card_id, session_id, topic_code, turns_spent,
                      final_mastery_p_l, status, verdict_summary, strengths_json, gaps_json))
                await db.commit()

        return card_id

    # ==========================================================================
    # 4. Final Reports CRUD (Atomic UPSERT)
    # ==========================================================================

    async def save_final_reports(
        self,
        session_id: str,
        student_compass_markdown: str,
        evaluator_audit_markdown: str,
        hiring_verdict: str,
        average_mastery: float,
        proctor_integrity_score: float
    ) -> str:
        """Saves final reports and marks the interview session COMPLETED."""
        report_id = f"rep_{uuid.uuid4().hex[:12]}"

        if not self.is_sqlite:
            query_reports = """
                INSERT INTO final_reports (
                    report_id, session_id, student_compass_markdown, evaluator_audit_markdown,
                    hiring_verdict, average_mastery, proctor_integrity_score
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (session_id) DO UPDATE SET
                    student_compass_markdown = EXCLUDED.student_compass_markdown,
                    evaluator_audit_markdown = EXCLUDED.evaluator_audit_markdown,
                    hiring_verdict = EXCLUDED.hiring_verdict,
                    average_mastery = EXCLUDED.average_mastery,
                    proctor_integrity_score = EXCLUDED.proctor_integrity_score,
                    generated_at = CURRENT_TIMESTAMP;
            """
            query_session = """
                UPDATE interview_sessions
                SET status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP
                WHERE session_id = %s;
            """
            await asyncio.to_thread(self._sync_pg_execute, query_reports, (
                report_id, session_id, student_compass_markdown, evaluator_audit_markdown,
                hiring_verdict, average_mastery, proctor_integrity_score
            ))
            await asyncio.to_thread(self._sync_pg_execute, query_session, (session_id,))
        else:
            async with aiosqlite.connect(SQLITE_DB_PATH) as db:
                await db.execute("""
                    INSERT INTO final_reports (
                        report_id, session_id, student_compass_markdown, evaluator_audit_markdown,
                        hiring_verdict, average_mastery, proctor_integrity_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (session_id) DO UPDATE SET
                        student_compass_markdown = excluded.student_compass_markdown,
                        evaluator_audit_markdown = excluded.evaluator_audit_markdown,
                        hiring_verdict = excluded.hiring_verdict,
                        average_mastery = excluded.average_mastery,
                        proctor_integrity_score = excluded.proctor_integrity_score,
                        generated_at = CURRENT_TIMESTAMP;
                """, (report_id, session_id, student_compass_markdown, evaluator_audit_markdown,
                      hiring_verdict, average_mastery, proctor_integrity_score))

                await db.execute("""
                    UPDATE interview_sessions
                    SET status = 'COMPLETED', completed_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?;
                """, (session_id,))
                await db.commit()

        return report_id

    # ==========================================================================
    # 5. Retrieval Queries
    # ==========================================================================

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves session metadata."""
        if not self.is_sqlite:
            query = "SELECT * FROM interview_sessions WHERE session_id = %s;"
            return await asyncio.to_thread(self._sync_pg_execute, query, (session_id,), "one")
        else:
            async with aiosqlite.connect(SQLITE_DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM interview_sessions WHERE session_id = ?;", (session_id,)) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None

    async def get_turns(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieves turn history ordered by turn_index."""
        if not self.is_sqlite:
            query = "SELECT * FROM turn_telemetry_logs WHERE session_id = %s ORDER BY turn_index ASC;"
            return await asyncio.to_thread(self._sync_pg_execute, query, (session_id,), "all")
        else:
            async with aiosqlite.connect(SQLITE_DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM turn_telemetry_logs WHERE session_id = ? ORDER BY turn_index ASC;",
                    (session_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(r) for r in rows]

    async def get_final_reports(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves completed reports for a session."""
        if not self.is_sqlite:
            query = "SELECT * FROM final_reports WHERE session_id = %s;"
            return await asyncio.to_thread(self._sync_pg_execute, query, (session_id,), "one")
        else:
            async with aiosqlite.connect(SQLITE_DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("SELECT * FROM final_reports WHERE session_id = ?;", (session_id,)) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None

    async def get_all_reports(self) -> List[Dict[str, Any]]:
        """Retrieves summary of all candidate sessions with reports and turns count."""
        if not self.is_sqlite:
            query = """
                SELECT 
                    s.session_id,
                    s.candidate_name,
                    s.seniority_tier,
                    s.detected_ecosystem,
                    s.status,
                    s.created_at,
                    s.completed_at,
                    r.report_id,
                    COALESCE(r.hiring_verdict, CASE WHEN COUNT(t.turn_id) > 0 THEN 'EVALUATED' ELSE 'IN_PROGRESS' END) as hiring_verdict,
                    COALESCE(r.average_mastery, 0.0) as average_mastery,
                    COALESCE(r.proctor_integrity_score, 1.0) as proctor_integrity_score,
                    r.generated_at,
                    COUNT(t.turn_id) as turns_count
                FROM interview_sessions s
                LEFT JOIN final_reports r ON s.session_id = r.session_id
                LEFT JOIN turn_telemetry_logs t ON s.session_id = t.session_id
                GROUP BY s.session_id, s.candidate_name, s.seniority_tier, s.detected_ecosystem, s.status, s.created_at, s.completed_at, r.report_id, r.hiring_verdict, r.average_mastery, r.proctor_integrity_score, r.generated_at
                ORDER BY s.created_at DESC;
            """
            return await asyncio.to_thread(self._sync_pg_execute, query, (), "all")
        else:
            async with aiosqlite.connect(SQLITE_DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT 
                        s.session_id,
                        s.candidate_name,
                        s.seniority_tier,
                        s.detected_ecosystem,
                        s.status,
                        s.created_at,
                        s.completed_at,
                        r.report_id,
                        COALESCE(r.hiring_verdict, CASE WHEN COUNT(t.turn_id) > 0 THEN 'EVALUATED' ELSE 'IN_PROGRESS' END) as hiring_verdict,
                        COALESCE(r.average_mastery, 0.0) as average_mastery,
                        COALESCE(r.proctor_integrity_score, 1.0) as proctor_integrity_score,
                        r.generated_at,
                        COUNT(t.turn_id) as turns_count
                    FROM interview_sessions s
                    LEFT JOIN final_reports r ON s.session_id = r.session_id
                    LEFT JOIN turn_telemetry_logs t ON s.session_id = t.session_id
                    GROUP BY s.session_id, s.candidate_name, s.seniority_tier, s.detected_ecosystem, s.status, s.created_at, s.completed_at, r.report_id, r.hiring_verdict, r.average_mastery, r.proctor_integrity_score, r.generated_at
                    ORDER BY s.created_at DESC;
                """) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(r) for r in rows]

    async def get_compacted_topic_cards(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieves compacted topic cards for a session."""
        if not self.is_sqlite:
            query = "SELECT * FROM compacted_topic_cards WHERE session_id = %s ORDER BY created_at ASC;"
            return await asyncio.to_thread(self._sync_pg_execute, query, (session_id,), "all")
        else:
            async with aiosqlite.connect(SQLITE_DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM compacted_topic_cards WHERE session_id = ? ORDER BY created_at ASC;",
                    (session_id,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(r) for r in rows]

