import sys
import os
sys.path.insert(0, os.path.abspath("."))

import asyncio
import uuid
from fastapi.testclient import TestClient
from app.live_server import app
from app.db_service import create_session, get_session_final_reports, log_turn_telemetry
from app.speech_cleaner import clean_candidate_transcript

client = TestClient(app)

def test_index_html_has_controls():
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    # Verify speaking pace selector exists
    assert 'id="speaking-pace-select"' in html
    assert 'Deliberate (6s pause)' in html
    assert 'Manual Spacebar only' in html
    # Verify resetStudioState exists
    assert 'function resetStudioState' in html
    # Verify resilient finish endpoint invocation
    assert '/finish' in html


def test_speech_cleaner_acoustics():
    # 1. Duplication test
    raw_dup = "can you please repeat the question  can you please repeat the question"
    cleaned = clean_candidate_transcript(raw_dup)
    assert cleaned == "can you please repeat the question"

    # 2. Technical terms test
    raw_tech = "I won many hack Account and used post grasis with casing memory and doctor with red is"
    cleaned_tech = clean_candidate_transcript(raw_tech)
    assert "hackathons" in cleaned_tech
    assert "PostgreSQL" in cleaned_tech
    assert "cache memory" in cleaned_tech
    assert "Docker" in cleaned_tech
    assert "Redis" in cleaned_tech

    # 3. Model terms test
    raw_models = "without the lumps using rag ways and b k d algorithms"
    cleaned_models = clean_candidate_transcript(raw_models)
    assert "LLMs" in cleaned_models
    assert "RAG-based" in cleaned_models
    assert "BKT" in cleaned_models


def test_finish_endpoint_saves_to_postgres():
    # Create a real test session in PostgreSQL
    session_id = f"test_{uuid.uuid4().hex[:12]}"
    create_session(
        session_id=session_id,
        candidate_name="Prajwal Integration Test",
        seniority_tier="MEDIUM",
        intro_blueprint={"topics": ["Real-Time Streaming & Concurrency"]}
    )

    # Log at least 1 turn
    log_turn_telemetry(
        session_id=session_id,
        turn_index=1,
        topic="ASYNC_CONCURRENCY",
        interviewer_prompt="Tell me about your Netty and Redis pipeline.",
        candidate_transcript="We used Netty non-blocking channels and Redis write-through caching.",
        latency_ms=1200,
        evaluator_observation=1,
        depth_score=0.85,
        bkt_prior=0.40,
        bkt_posterior=0.72,
        proctor_bii=0.98
    )

    # Call the new REST finish endpoint
    res = client.post(f"/api/session/{session_id}/finish")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "student_report" in data
    assert "evaluator_report" in data
    assert len(data["student_report"]) > 100
    assert len(data["evaluator_report"]) > 100

    # Verify that the report is persisted directly in PostgreSQL!
    db_rep = get_session_final_reports(session_id)
    assert db_rep is not None
    assert db_rep["session_id"] == session_id
    assert len(db_rep["student_compass_markdown"]) > 100
    assert len(db_rep["evaluator_audit_markdown"]) > 100
    print(f"\n[Test Success] Verified dual reports saved in PostgreSQL for session {session_id}!")


if __name__ == "__main__":
    test_index_html_has_controls()
    test_speech_cleaner_acoustics()
    test_finish_endpoint_saves_to_postgres()
    print("\nAll integration & persistence tests passed perfectly!")
