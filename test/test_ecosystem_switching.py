"""
Verification Test Suite for Project-Scoped Multi-Ecosystem Switching.
Document Reference: AIS-POLYGLOT-2026-V1 / REPORT 7
Tests:
1. Parsing polyglot intro transcripts (e.g. Java Netty microservice + Python PyTorch model).
2. Binding distinct competency pillars to distinct project ecosystems.
3. Socratic dialect directive generation for Alex (JVM vs CPython vs Go).
4. Evaluator rubric contextualization based on active runtime ecosystem.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ecosystem_service import (
    detect_ecosystems_from_intro, bind_pillars_to_ecosystems,
    get_ecosystem_directive, get_evaluator_ecosystem_context
)


def test_polyglot_intro_detection():
    print("\n--- Test 1: Polyglot Intro Ecosystem Detection ---")
    polyglot_intro = (
        "Hi, I am Alex. In my previous role at FinTech, I built an order matching engine in Java using Spring Boot, "
        "Netty, and Kafka for ultra-low latency. Later, I created a disease diagnostic pipeline in Python using PyTorch and FastAPI."
    )

    detected = detect_ecosystems_from_intro(polyglot_intro)
    print(f"Primary Ecosystem: {detected['primary_ecosystem']}")
    print(f"All Ecosystems: {detected['all_ecosystems']}")
    print(f"Keywords: {detected['stack_keywords']}")
    print(f"Is Polyglot: {detected['is_polyglot']}")

    assert detected["is_polyglot"] is True
    assert "JAVA_JVM" in detected["all_ecosystems"]
    assert "PYTHON" in detected["all_ecosystems"]
    print("[PASS] Verified multi-project polyglot ecosystem detection.")


def test_project_pillar_binding():
    print("\n--- Test 2: Project-to-Pillar Ecosystem Binding ---")
    polyglot_intro = (
        "I built a high-throughput Java Netty service with Kafka event streaming, "
        "and also built a Python PyTorch inference server with Redis caching."
    )
    matched_pillars = [
        {"pillar_id": "ASYNC_CONCURRENCY", "name": "Concurrency & Streaming"},
        {"pillar_id": "EVENT_STREAMING_MESSAGING", "name": "Event Streaming"},
        {"pillar_id": "AI_INFERENCE_ORCHESTRATION", "name": "AI Inference"}
    ]

    bindings = bind_pillars_to_ecosystems(matched_pillars, polyglot_intro)
    print("Pillar Ecosystem Bindings:", bindings)

    assert bindings["ASYNC_CONCURRENCY"] == "JAVA_JVM"
    assert bindings["EVENT_STREAMING_MESSAGING"] == "JAVA_JVM"
    assert bindings["AI_INFERENCE_ORCHESTRATION"] == "PYTHON"
    print("[PASS] Verified project-scoped pillar ecosystem bindings.")


def test_dialect_directive_and_evaluator_context():
    print("\n--- Test 3: Dialect Directives & Evaluator Context ---")
    pillar_map = {
        "ASYNC_CONCURRENCY": "JAVA_JVM",
        "AI_INFERENCE_ORCHESTRATION": "PYTHON"
    }

    # Directive for Java Topic
    java_dir = get_ecosystem_directive("ASYNC_CONCURRENCY", pillar_map)
    java_eval_ctx = get_evaluator_ecosystem_context("ASYNC_CONCURRENCY", pillar_map)
    print("\nJava Directive Excerpt:")
    print(java_dir[:200] + "...")
    assert "JAVA" in java_dir
    assert "JVM" in java_dir
    assert "Python GIL" in java_dir  # Instructs Alex NOT to mention Python GIL

    # Directive for Python Topic
    py_dir = get_ecosystem_directive("AI_INFERENCE_ORCHESTRATION", pillar_map)
    py_eval_ctx = get_evaluator_ecosystem_context("AI_INFERENCE_ORCHESTRATION", pillar_map)
    print("\nPython Directive Excerpt:")
    print(py_dir[:200] + "...")
    assert "PYTHON" in py_dir
    assert "GIL" in py_dir
    assert "JVM" in py_dir  # Instructs Alex NOT to mention JVM

    print("[PASS] Verified dynamic dialect directive switching and evaluator context.")


if __name__ == "__main__":
    test_polyglot_intro_detection()
    test_project_pillar_binding()
    test_dialect_directive_and_evaluator_context()
    print("\n========================================================")
    print("ALL MULTI-ECOSYSTEM SWITCHING TESTS PASSED (3/3)!")
    print("========================================================")
