"""
End-to-End Verification Test for Vector DB (Dynoxide) and PostgreSQL.
Tests real semantic search, intro blueprint storage, turn telemetry, compaction, and report archiving.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import json
import websockets
import psycopg2
from psycopg2.extras import RealDictCursor


def verify_postgres_records():
    conn = psycopg2.connect(
        host="127.0.0.1", port=5432, dbname="interview-engine", user="postgres", password="0608"
    )
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check sessions
        cur.execute("SELECT session_id, candidate_name, seniority_tier, intro_blueprint, status FROM interview_sessions ORDER BY created_at DESC LIMIT 1;")
        sess = cur.fetchone()
        print("\n=== POSTGRESQL VERIFICATION ===")
        print("Latest Session:", sess)

        if sess:
            sid = sess["session_id"]
            # Check turn telemetry logs
            cur.execute("SELECT turn_index, topic, latency_ms, depth_score, bkt_prior, bkt_posterior FROM turn_telemetry_logs WHERE session_id = %s;", (sid,))
            turns = cur.fetchall()
            print(f"Turn Telemetry Logs for {sid}: {len(turns)} rows")
            for t in turns:
                print(f"  Turn {t['turn_index']}: {t['topic']} | Depth: {t['depth_score']} | BKT: {t['bkt_prior']} -> {t['bkt_posterior']}")

            # Check compacted topic cards
            cur.execute("SELECT topic_code, turns_spent, final_mastery_p_l, status, verdict_summary FROM compacted_topic_cards WHERE session_id = %s;", (sid,))
            cards = cur.fetchall()
            print(f"Compacted Topic Cards for {sid}: {len(cards)} rows")
            for c in cards:
                print(f"  Card: {c['topic_code']} | Mastery: {c['final_mastery_p_l']} | Status: {c['status']}")

            # Check final reports
            cur.execute("SELECT hiring_verdict, average_mastery, proctor_integrity_score, evaluator_audit_markdown FROM final_reports WHERE session_id = %s;", (sid,))
            rep = cur.fetchone()
            if rep:
                print("Final Report Archived in DB:", {
                    "hiring_verdict": rep.get("hiring_verdict"),
                    "average_mastery": rep.get("average_mastery"),
                    "proctor_integrity_score": rep.get("proctor_integrity_score")
                })
                md = rep.get("evaluator_audit_markdown", "")
                if "## 4. Multidimensional Item Response Theory (MIRT) Ability Radar" in md:
                    mirt_section = md.split("## 4. Multidimensional Item Response Theory (MIRT) Ability Radar")[1].split("## 5.")[0]
                    print("\n--- ARCHIVED REAL MIRT ABILITY RADAR IN POSTGRESQL ---")
                    print(mirt_section.replace("θ", "theta").strip())
    conn.close()


async def run_live_e2e():
    uri = "ws://127.0.0.1:8000/ws/interview"
    print("\n[E2E Test] Connecting to live server WebSocket:", uri)
    async with websockets.connect(uri) as ws:
        # 1. Handshake
        await ws.send(json.dumps({"name": "Prajwal", "level": "MEDIUM"}))
        print("[E2E Test] Handshake sent.")

        # 2. Wait for Alex greeting turn complete
        while True:
            msg = await ws.recv()
            if isinstance(msg, str):
                data = json.loads(msg)
                if data.get("event") == "turn_complete":
                    print("[E2E Test] Alex finished greeting!")
                    break

        # 3. Candidate introduces themselves mentioning polyglot projects (Java + Python)
        custom_intro = "Hello, I am Prajwal. In Java, I built an asynchronous real-time message stream with Netty and Redis caching. In Python, I built an ML inference pipeline using PyTorch and FastAPI."
        print(f"[E2E Test] Candidate speaking intro: '{custom_intro}'")
        await ws.send(json.dumps({"text": custom_intro}))

        # 4. Wait for Alex's question on the Vector-DB matched topic
        while True:
            msg = await ws.recv()
            if isinstance(msg, str):
                data = json.loads(msg)
                if data.get("event") == "turn_complete":
                    print("[E2E Test] Alex asked first Socratic probe on matched topic!")
                    break

        # 5. Candidate answers technical probe
        answer = "We set a 300 second TTL on Redis keys and used write-through invalidation whenever user state updates in PostgreSQL."
        print(f"[E2E Test] Candidate answering: '{answer}'")
        await ws.send(json.dumps({"text": answer}))

        # 6. Wait for Alex second probe
        while True:
            msg = await ws.recv()
            if isinstance(msg, str):
                data = json.loads(msg)
                if data.get("event") == "turn_complete":
                    print("[E2E Test] Alex completed second turn!")
                    break

        # 7. Finish interview to trigger report generation and database archiving
        print("[E2E Test] Sending finish_interview...")
        await ws.send(json.dumps({"event": "finish_interview"}))

        while True:
            msg = await ws.recv()
            if isinstance(msg, str):
                data = json.loads(msg)
                if data.get("event") == "reports_generated":
                    print("[E2E Test] Dual reports generated successfully by server!")
                    break

        # Wait a moment for background DB tasks to complete
        await asyncio.sleep(1.0)


if __name__ == "__main__":
    asyncio.run(run_live_e2e())
    verify_postgres_records()
