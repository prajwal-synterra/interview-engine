"""
Phase 9 Demo: Dual Report Generation Verification
Tests:
1. Master Composite Scoring & 5D Cognitive Potential Fingerprint (CPF)
2. Deterministic Technical Evaluator Forensic Audit Report
3. LLM-Powered Student Career Compass & Growth Report (with automatic fallback)
4. Disk Persistence to reports/ folder
"""

import sys
import os
import asyncio

# Add root folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.mirt_engine import MIRTEngine, get_radar_summary
from app.report_generator import (
    calculate_master_score,
    generate_evaluator_report,
    generate_student_report,
    save_reports_to_disk
)


def print_header(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def main():
    print_header("PHASE 9: DUAL REPORT GENERATION TEST")

    session_id = "test-session-v4-001"
    candidate_name = "Alex Vance"
    seniority = "SENIOR"

    # 1. Mock Interview Session State (Simulated 6 Turns)
    mock_skills_mastery = {
        "DISTRIBUTED_CACHING": 0.88,
        "EVENT_STREAMING_MESSAGING": 0.82,
        "DATABASE_MODELING_TRANSACTIONS": 0.65
    }

    mock_ecosystem_info = {
        "primary_ecosystem": "PYTHON",
        "all_ecosystems": ["PYTHON", "JAVA_JVM"],
        "stack_keywords": ["python", "fastapi", "redis", "kafka", "postgres"],
        "is_polyglot": True
    }

    mock_turns = [
        {
            "turn_index": 1,
            "skill": "DISTRIBUTED_CACHING",
            "question": "How do you handle cache stampedes when a high-traffic key expires in Redis?",
            "candidate_answer": "I use mutex locking with singleflight or Redis SETNX with a TTL to ensure only one worker queries the database.",
            "observation": 1,
            "scaffolding_level": 0,
            "bkt_posterior": 0.72,
            "latency_ms": 1420,
            "proctor_flags": []
        },
        {
            "turn_index": 2,
            "skill": "DISTRIBUTED_CACHING",
            "question": "What happens if that single worker node crashes while holding the distributed lock?",
            "candidate_answer": "The lock must have an automatic TTL lease, and we use a heartbeat background thread to renew the lease while actively working.",
            "observation": 1,
            "scaffolding_level": 0,
            "bkt_posterior": 0.88,
            "latency_ms": 1650,
            "proctor_flags": []
        },
        {
            "turn_index": 3,
            "skill": "DISTRIBUTED_CACHING",
            "question": "[DEVILS ADVOCATE] Isn't Redlock flawed due to asynchronous clock drift across distributed nodes?",
            "candidate_answer": "Yes, Martin Kleppmann showed clock drift can invalidate leases. If absolute consistency is required, a consensus system like Raft or fenced tokens is necessary.",
            "observation": 1,
            "scaffolding_level": 0,
            "bkt_posterior": 0.94,
            "latency_ms": 1820,
            "proctor_flags": []
        },
        {
            "turn_index": 4,
            "skill": "EVENT_STREAMING_MESSAGING",
            "question": "How do you guarantee strict FIFO ordering across partitioned Kafka consumer groups?",
            "candidate_answer": "Ensure messages with the same entity ID share the same partition key, and keep single-threaded processing per partition.",
            "observation": 1,
            "scaffolding_level": 0,
            "bkt_posterior": 0.82,
            "latency_ms": 1500,
            "proctor_flags": []
        },
        {
            "turn_index": 5,
            "skill": "DATABASE_MODELING_TRANSACTIONS",
            "question": "What is the difference between Repeatable Read and Serializable isolation levels in PostgreSQL MVCC?",
            "candidate_answer": "Repeatable read prevents non-repeatable reads, but I'm not totally certain how it handles serialization anomalies.",
            "observation": 0,
            "scaffolding_level": 0,
            "bkt_posterior": 0.52,
            "latency_ms": 2100,
            "proctor_flags": []
        },
        {
            "turn_index": 6,
            "skill": "DATABASE_MODELING_TRANSACTIONS",
            "question": "[L1 HINT] Consider write skew where two concurrent transactions read overlapping rows before updating disjoint ones.",
            "candidate_answer": "Under Serializable, PostgreSQL uses SSI (Serializable Snapshot Isolation) with SIREAD locks to detect write-skew dependency cycles.",
            "observation": 1,
            "scaffolding_level": 1,
            "bkt_posterior": 0.65,
            "latency_ms": 1900,
            "proctor_flags": []
        }
    ]

    proctor_bii = 0.95
    devils_advocate_results = [1]  # Successfully defended against Redlock clock drift challenge

    # 2. Build MIRT 5D Radar Profile
    mirt = MIRTEngine(initial_theta={
        "distributed_systems": 1.4,
        "concurrency": 1.1,
        "system_design": 0.9,
        "databases": 0.5,
        "algorithms": 0.3
    })
    mirt_radar = get_radar_summary(mirt)

    # 3. Test Master Score & CPF Calculation
    scaffolding_events = [{"level": t["scaffolding_level"]} for t in mock_turns if t["scaffolding_level"] > 0]
    score_res = calculate_master_score(mock_skills_mastery, scaffolding_events, proctor_bii, devils_advocate_results)

    print(f"Master Composite Score: {score_res['final_score']} / 100")
    print(f"Hiring Verdict:         {score_res['verdict']} ({score_res['badge_color']})")
    print(f"5D CPF Fingerprint:     {score_res['cpf']}")

    # 4. Generate Evaluator Forensic Audit Report
    print_header("GENERATING EVALUATOR FORENSIC AUDIT REPORT")
    evaluator_rep = generate_evaluator_report(
        session_id=session_id,
        candidate_name=candidate_name,
        seniority_level=seniority,
        turns_history=mock_turns,
        skills_mastery=mock_skills_mastery,
        proctor_bii=proctor_bii,
        mirt_radar=mirt_radar,
        ecosystem_info=mock_ecosystem_info,
        devils_advocate_results=devils_advocate_results
    )
    print("Evaluator Report Length:", len(evaluator_rep), "chars")
    print("\n--- Evaluator Report Preview (First 35 lines) ---")
    print("\n".join(evaluator_rep.splitlines()[:35]))

    # 5. Generate Student Career Compass Report
    print_header("GENERATING STUDENT CAREER COMPASS & GROWTH REPORT (LLM)")
    student_rep = await generate_student_report(
        candidate_name=candidate_name,
        seniority_level=seniority,
        turns_history=mock_turns,
        skills_mastery=mock_skills_mastery,
        mirt_radar=mirt_radar,
        ecosystem_info=mock_ecosystem_info
    )
    print("Student Report Length:", len(student_rep), "chars")
    print("\n--- Student Report Preview (First 35 lines) ---")
    print("\n".join(student_rep.splitlines()[:35]))

    # 6. Save Both Reports to Disk
    print_header("PERSISTING REPORTS TO DISK")
    saved_paths = save_reports_to_disk(session_id, student_rep, evaluator_rep)
    print("Saved Student Report:   ", saved_paths["student_report_path"])
    print("Saved Evaluator Report: ", saved_paths["evaluator_report_path"])


if __name__ == "__main__":
    asyncio.run(main())
