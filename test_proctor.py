"""
Verification Test Suite for Behavioral Proctoring Engine.
Tests:
1. Natural human engineer session: natural fast latency, clarifying questions, high BII (1.0).
2. AI Copilot overlay signature: high delay (2500ms) with flat jitter, high TTR, BII degradation.
3. Contradiction probe: failing an injected false technical premise triggers critical flag.
"""

from app.proctor_engine import BehavioralProctorEngine


def test_natural_human_interview():
    print("\n--- Test 1: Natural Human Candidate (Authentic Flow) ---")
    proctor = BehavioralProctorEngine()

    # Turn 1: Quick answer with natural filler
    proctor.record_turn(
        latency_ms=650,
        transcript="Well, looking at the storage layer, we should probably consider PostgreSQL for relational consistency."
    )

    # Turn 2: Natural clarifying question
    proctor.record_turn(
        latency_ms=480,
        transcript="Before we choose the cache, what is the expected read to write ratio for these active users?"
    )

    # Turn 3: Natural thinking speed with disfluency
    proctor.record_turn(
        latency_ms=820,
        transcript="Right, so if writes are 20%, Redis write-through cache is definitely appropriate here."
    )

    summary = proctor.integrity_summary
    print(f"Human BII: {summary['behavioral_integrity_index']} | Flags: {len(summary['flags_raised'])}")

    assert summary["behavioral_integrity_index"] == 1.0
    assert summary["passed_proctoring"] is True
    print("[PASS] Natural human interview maintained 1.0 Behavioral Integrity Index.")


def test_copilot_hud_detection():
    print("\n--- Test 2: AI Copilot Detection (Latency Gap & Flat Jitter) ---")
    proctor = BehavioralProctorEngine()

    # Copilot takes 2500ms every time (STT + LLM response + read), very low variance
    proctor.record_turn(
        latency_ms=2510,
        transcript="Redis utilizes an in-memory data structure store used as a database, cache, and message broker with microsecond latency."
    )
    proctor.record_turn(
        latency_ms=2490,
        transcript="To mitigate cache stampede, we implement mutual exclusion locks using Redis SETNX with an expiration time."
    )
    proctor.record_turn(
        latency_ms=2505,
        transcript="Consistent hashing maps keys to a circular continuum, minimizing cache reallocation during dynamic node scaling events."
    )

    summary = proctor.integrity_summary
    print(f"Copilot BII: {summary['behavioral_integrity_index']}")
    for f in summary["flags_raised"]:
        print(f" - [{f['severity']}] {f['type']}: {f['evidence']}")

    assert any(f["type"] == "COPILOT_LATENCY_JITTER_ANOMALY" for f in summary["flags_raised"])
    assert summary["behavioral_integrity_index"] < 0.70
    print("[PASS] Copilot acoustic latency signature correctly caught and penalized.")


def test_contradiction_probe_failure():
    print("\n--- Test 3: Contradiction Probe Failure ---")
    proctor = BehavioralProctorEngine()

    # Candidate blindly agrees with false premise ("HTTP/2 uses UDP")
    proctor.record_turn(
        latency_ms=1200,
        transcript="Yes, to configure TCP packet loss retries on HTTP/2's UDP stream, we should tune the socket buffers.",
        is_contradiction_probe=True,
        passed_contradiction_probe=False
    )

    summary = proctor.integrity_summary
    print(f"BII after accepting false premise: {summary['behavioral_integrity_index']}")
    assert any(f["type"] == "CONTRADICTION_PROBE_FAILED" for f in summary["flags_raised"])
    print("[PASS] Contradiction probe failure caught with CRITICAL severity flag.")


if __name__ == "__main__":
    test_natural_human_interview()
    test_copilot_hud_detection()
    test_contradiction_probe_failure()
    print("\n========================================================")
    print("ALL BEHAVIORAL PROCTORING TESTS PASSED (3/3)!")
    print("========================================================")
