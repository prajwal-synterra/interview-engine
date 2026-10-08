"""
Phase 8 Demo: Testing the Ecosystem & Polyglot Technical Detection Engine
Tests:
1. Pure Go Candidate (Goroutines, channels, GMP scheduler)
2. Pure Java Enterprise Candidate (Spring Boot, JVM, Netty)
3. Polyglot Candidate (Python ML + Go Microservices) -> Custom Pillar Binding
4. Prompt Directive Generation for Alex
"""

import sys
import os

# Add root folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ecosystem_service import (
    detect_ecosystems_from_intro,
    bind_pillars_to_ecosystems,
    get_ecosystem_directive,
    get_evaluator_ecosystem_context
)


def print_header(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_single_ecosystem_detection():
    print_header("TEST 1: Single Ecosystem Detection")

    go_intro = "I've been working with Go for 3 years, building high-throughput microservices with goroutines and gRPC."
    go_res = detect_ecosystems_from_intro(go_intro)
    print("Candidate Intro (Go):", go_intro)
    print(f"  -> Primary Ecosystem: {go_res['primary_ecosystem']}")
    print(f"  -> Matched Keywords:   {go_res['stack_keywords']}")
    print(f"  -> Is Polyglot:        {go_res['is_polyglot']}\n")

    java_intro = "I lead backend systems at an enterprise using Java and Spring Boot with Netty for reactive microservices."
    java_res = detect_ecosystems_from_intro(java_intro)
    print("Candidate Intro (Java):", java_intro)
    print(f"  -> Primary Ecosystem: {java_res['primary_ecosystem']}")
    print(f"  -> Matched Keywords:   {java_res['stack_keywords']}")
    print(f"  -> Is Polyglot:        {java_res['is_polyglot']}")


def test_polyglot_and_pillar_binding():
    print_header("TEST 2: Polyglot Candidate & Multi-Ecosystem Pillar Binding")

    polyglot_intro = (
        "I build our AI inference pipelines using Python and PyTorch with FastAPI, "
        "while our real-time messaging gateway is written in Java using Spring Boot."
    )
    poly_res = detect_ecosystems_from_intro(polyglot_intro)
    print("Candidate Intro (Polyglot):", polyglot_intro)
    print(f"  -> Primary Ecosystem: {poly_res['primary_ecosystem']}")
    print(f"  -> All Ecosystems:    {poly_res['all_ecosystems']}")
    print(f"  -> Is Polyglot:        {poly_res['is_polyglot']}\n")

    # Simulate matched pillars from vector search
    mock_pillars = [
        {"pillar_id": "AI_INFERENCE_ORCHESTRATION"},
        {"pillar_id": "EVENT_STREAMING_MESSAGING"}
    ]

    bindings = bind_pillars_to_ecosystems(mock_pillars, polyglot_intro)
    print("Pillar -> Ecosystem Dialect Bindings:")
    for pid, eco in bindings.items():
        print(f"  * Pillar '{pid:<30}' -> Bound to: {eco}")


def test_alex_prompt_directive():
    print_header("TEST 3: Injected Prompt Directive for Alex")
    bindings = {
        "ASYNC_CONCURRENCY": "PYTHON",
        "EVENT_STREAMING_MESSAGING": "JAVA_JVM"
    }

    print("--- Directive for Python Async ---")
    print(get_ecosystem_directive("ASYNC_CONCURRENCY", bindings))

    print("\n--- Directive for Java Event Streaming ---")
    print(get_ecosystem_directive("EVENT_STREAMING_MESSAGING", bindings))


if __name__ == "__main__":
    test_single_ecosystem_detection()
    test_polyglot_and_pillar_binding()
    test_alex_prompt_directive()
