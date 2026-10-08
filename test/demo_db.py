"""
Phase 10 Demo: Database Persistence Engine Verification
Tests:
1. Database initialization and table creation (PostgreSQL or SQLite fallback)
2. Creating an interview session and updating dynamic blueprint
3. Logging turn-by-turn telemetry (Alex questions, candidate STT transcripts, BKT posteriors)
4. Saving a compacted topic card (Topic completion)
5. Saving final reports (UPSERT into final_reports + session COMPLETED status update)
6. Verifying data integrity via retrieval queries
"""

import sys
import os
import asyncio

# Add root folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db_service import DatabaseService


def print_header(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def main():
    print_header("PHASE 10: DATABASE SERVICE TEST")

    db = DatabaseService()
    await db.initialize()

    session_id = "sess_demo_v4_test"
    candidate_name = "Maya Lin"
    seniority = "SENIOR"

    # 1. Create Session
    print_header("1. CREATING INTERVIEW SESSION")
    sess = await db.create_session(
        session_id=session_id,
        candidate_name=candidate_name,
        seniority_tier=seniority,
        detected_ecosystem="PYTHON"
    )
    print("Created Session:", sess)

    # 2. Update Blueprint (after Vector Topic Matching)
    print_header("2. UPDATING SESSION BLUEPRINT (VECTOR MATCHING RESULT)")
    blueprint = {
        "intro_text": "I build distributed stream processing engines in Python and Go.",
        "matched_pillars": ["EVENT_STREAMING_MESSAGING", "ASYNC_CONCURRENCY", "DISTRIBUTED_CACHING"],
        "pillar_ecosystem_map": {
            "EVENT_STREAMING_MESSAGING": "PYTHON",
            "ASYNC_CONCURRENCY": "PYTHON"
        }
    }
    await db.update_session_blueprint(session_id, blueprint, detected_ecosystem="PYTHON")
    print("Session blueprint successfully updated.")

    # 3. Log 3 Turns of Telemetry
    print_header("3. LOGGING TURN-BY-TURN TELEMETRY")
    t1_id = await db.log_turn_telemetry(
        session_id=session_id,
        turn_index=1,
        topic="DISTRIBUTED_CACHING",
        interviewer_prompt="How do you handle cache stampedes when a key expires?",
        candidate_transcript="I use singleflight mutexes or probabilistic early expiration.",
        latency_ms=1350,
        evaluator_observation=1,
        depth_score=0.85,
        bkt_prior=0.45,
        bkt_posterior=0.74,
        proctor_bii=0.98
    )
    print(f"Logged Turn 1 -> ID: {t1_id}")

    t2_id = await db.log_turn_telemetry(
        session_id=session_id,
        turn_index=2,
        topic="DISTRIBUTED_CACHING",
        interviewer_prompt="What happens if the single worker holding the lock crashes?",
        candidate_transcript="We configure TTL leases and renew via heartbeat goroutine/thread.",
        latency_ms=1600,
        evaluator_observation=1,
        depth_score=0.90,
        bkt_prior=0.74,
        bkt_posterior=0.91,
        proctor_bii=0.98
    )
    print(f"Logged Turn 2 -> ID: {t2_id}")

    # 4. Save Compacted Topic Card
    print_header("4. SAVING COMPACTED TOPIC CARD")
    card_id = await db.save_compacted_topic_card(
        session_id=session_id,
        topic_code="DISTRIBUTED_CACHING",
        turns_spent=2,
        final_mastery_p_l=0.91,
        status="MASTERED",
        verdict_summary="Candidate demonstrates deep expertise in stampede mitigation and lease renewal.",
        strengths_cited=["Singleflight deduplication", "Heartbeat lease renewal"],
        gaps_identified=[]
    )
    print(f"Saved Topic Card -> ID: {card_id}")

    # 5. Save Final Reports (Atomic UPSERT)
    print_header("5. SAVING FINAL REPORTS (ATOMIC UPSERT)")
    mock_student_md = "# Career Compass for Maya Lin\n\nSolid distributed systems foundation."
    mock_evaluator_md = "# Forensic Evaluation\n\nVerdict: STRONG_HIRE. Score: 88.5."
    rep_id = await db.save_final_reports(
        session_id=session_id,
        student_compass_markdown=mock_student_md,
        evaluator_audit_markdown=mock_evaluator_md,
        hiring_verdict="STRONG_HIRE",
        average_mastery=0.91,
        proctor_integrity_score=0.98
    )
    print(f"Saved Final Reports -> ID: {rep_id}")

    # 6. Verify Records
    print_header("6. VERIFYING RETRIEVAL FROM DATABASE")
    saved_sess = await db.get_session(session_id)
    print("Session Status:", saved_sess.get("status"))
    print("Completed At:  ", saved_sess.get("completed_at"))

    turns = await db.get_turns(session_id)
    print(f"Retrieved {len(turns)} Turn Records:")
    for t in turns:
        print(f"  Turn {t['turn_index']}: [{t['topic']}] P(L): {t['bkt_posterior']:.2f} | Latency: {t['latency_ms']}ms")

    reports = await db.get_final_reports(session_id)
    print("Final Reports Verified:")
    print(f"  Verdict:         {reports.get('hiring_verdict')}")
    print(f"  Average Mastery: {reports.get('average_mastery')}")
    print(f"  Student MD Len:  {len(reports.get('student_compass_markdown'))} chars")


if __name__ == "__main__":
    asyncio.run(main())
