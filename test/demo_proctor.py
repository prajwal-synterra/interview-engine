"""
Phase 5 Demo: Testing the Behavioral Proctor Engine
Tests:
1. Authentic Human Dialogue (Natural pauses, fillers, clarifying questions -> BII = 1.00)
2. Lexical Density Anomaly (Reading aloud from an LLM -> TTR > 0.88 -> Penalty -0.10)
3. Copilot Latency Jitter Signature (Constant ~2.2s latency with low variance -> Penalty -0.40)
4. Contradiction Probe Failure (Accepting false technical premise -> Penalty -0.35)
5. Cumulative Fraud Overrides Hiring Verdict (BII < 0.70 -> FLAGGED)
"""

import sys
import os

# Add root folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.proctor_engine import ProctorEngine


def print_header(title: str):
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


def test_authentic_candidate():
    print_header("TEST 1: Authentic Human Candidate (Flawless BII = 1.00)")
    proctor = ProctorEngine()

    human_turns = [
        (450, "Well, um, what scale should we assume? Is it around 10k QPS?"),
        (1200, "Right, so for distributed caching, we could use Redis. But if the cache misses, we hit the DB."),
        (3100, "Hmm, let me think about the write-through versus write-back trade-off here. Write-back adds complexity."),
    ]

    for lat, text in human_turns:
        res = proctor.record_turn(latency_ms=lat, transcript=text)
        print(f"Turn {res['turn_id']}: Latency={res['latency_ms']}ms | TTR={res['ttr']:.2f} | BII={res['current_bii']}")

    print(f"\nFinal Summary: BII={proctor.bii:.2f} | Flags Raised: {len(proctor.flags)} | Passed: {proctor.integrity_summary['passed_proctoring']}")


def test_lexical_density_flag():
    print_header("TEST 2: Lexical Density Anomaly (Reading Pre-Written LLM Output)")
    proctor = ProctorEngine()

    # Pre-written prose with 40+ unique words and no natural human repetition
    llm_prose = (
        "Architectural scalability necessitates implementing distributed partitioned consensus mechanisms "
        "leveraging Byzantine fault tolerant protocols alongside asynchronous non-blocking event loops "
        "facilitating high throughput serialization across heterogeneous compute clusters reliably, "
        "thereby optimizing deterministic state transitions while mitigating transient operational network partition bottlenecks dynamically."
    )

    res = proctor.record_turn(latency_ms=800, transcript=llm_prose)
    print(f"Turn 1 (Reading LLM): Words={len(llm_prose.split())} | TTR={res['ttr']:.2f} | BII={res['current_bii']}")
    print(f"Flags Triggered: {[f.flag_type for f in proctor.flags]}")



def test_copilot_latency_anomaly():
    print_header("TEST 3: External Copilot Latency Signature (Near-Zero Jitter)")
    proctor = ProctorEngine()

    # External LLM Copilot turnaround: takes ~2200ms every single turn with minimal variance
    copilot_turns = [
        (2210, "First we configure the load balancer using round robin."),
        (2190, "Next we implement write-ahead logging to guarantee durability."),
        (2220, "Finally we set up read replicas to distribute query traffic."),
    ]

    for lat, text in copilot_turns:
        res = proctor.record_turn(latency_ms=lat, transcript=text)
        print(f"Turn {res['turn_id']}: Latency={res['latency_ms']}ms | BII={res['current_bii']}")

    print(f"Flags Triggered: {[f.flag_type for f in proctor.flags]}")


def test_contradiction_probe_failure():
    print_header("TEST 4: Contradiction Probe Failure")
    proctor = ProctorEngine()

    # Turn 1: Normal turn
    proctor.record_turn(latency_ms=900, transcript="We can use Raft for leader election.")

    # Turn 2: Interviewer injected false premise: 'Since Kafka guarantees zero-loss without replication'
    # Candidate blindly accepted instead of pushing back!
    proctor.record_turn(
        latency_ms=1100,
        transcript="Yes exactly, Kafka guarantees zero data loss even with zero replicas, so that works.",
        is_contradiction_probe=True,
        passed_contradiction_probe=False
    )

    summary = proctor.integrity_summary
    print(f"BII after accepting false premise: {summary['behavioral_integrity_index']:.2f}")
    print(f"Flags: {[f['type'] for f in summary['flags_raised']]}")


def test_cumulative_fraud_override():
    print_header("TEST 5: Cumulative Fraud Overrides Hiring Verdict (BII < 0.70)")
    proctor = ProctorEngine()

    # Candidate triggers Copilot Latency (-0.40) + Contradiction Probe Failure (-0.35)
    copilot_turns = [(2200, "Turn 1"), (2210, "Turn 2"), (2195, "Turn 3")]
    for lat, text in copilot_turns:
        proctor.record_turn(latency_ms=lat, transcript=text)

    # Contradiction failure
    proctor.record_turn(latency_ms=2200, transcript="I agree.", is_contradiction_probe=True, passed_contradiction_probe=False)

    summary = proctor.integrity_summary
    print(f"Final BII: {summary['behavioral_integrity_index']:.2f}")
    print(f"Total Flags Raised: {len(summary['flags_raised'])}")
    print(f"Integrity Status: {'PASSED' if summary['passed_proctoring'] else 'FLAGGED_FOR_FRAUD (Automatic Disqualification)'}")


if __name__ == "__main__":
    test_authentic_candidate()
    test_lexical_density_flag()
    test_copilot_latency_anomaly()
    test_contradiction_probe_failure()
    test_cumulative_fraud_override()
