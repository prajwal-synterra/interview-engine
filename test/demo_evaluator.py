"""
Phase 6 Demo: Testing the Shadow Evaluator Engine
Tests:
1. Strong Technical Answer (Senior level -> Observation: 1, High Depth)
2. Weak/Flawed Technical Answer (Incorrect concepts -> Observation: 0)
3. Off-Topic / Evasive Non-Technical Answer (Enforces 0.10 depth penalty)
4. Offline / Timeout Safety Fallback (Ensures zero crashes)
"""

import sys
import os
import asyncio
import json

# Add root folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.evaluator_engine import evaluate_candidate_response


def print_header(title: str):
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


async def test_strong_answer():
    print_header("TEST 1: Strong Technical Answer (Distributed Caching)")
    question = "How would you handle cache stampedes when a high-traffic key expires in Redis?"
    answer = (
        "To prevent a cache stampede, I would use mutex locking with a tool like Redlock or singleflight, "
        "so only one worker fetches from the database while concurrent requests wait. "
        "Alternatively, we can use probabilistic early expiration (the XFetch algorithm) to recompute the value "
        "before the TTL actually lapses, or serve stale data via background asynchronous refresh."
    )

    print(f"Question: \"{question}\"")
    print(f"Candidate Answer: \"{answer[:90]}...\"\n")

    res = await evaluate_candidate_response(
        skill="DISTRIBUTED_CACHING",
        interviewer_question=question,
        candidate_answer=answer,
        scaffolding_level=0,
        ecosystem_context="Python / Redis Distributed Architecture"
    )

    print(f"Evaluation Results:")
    print(f"  -> Observation:          {res['observation']} (1=Pass, 0=Fail)")
    print(f"  -> Depth Score:           {res['depth_score']:.2f}")
    print(f"  -> Estimated Difficulty:  {res['estimated_difficulty']:.2f}")
    print(f"  -> Evaluator Summary:     \"{res['summary']}\"")
    print(f"  -> Recommended Probe:     \"{res.get('recommended_probe', 'N/A')}\"")
    print("  -> Rubric Items:")
    for item in res.get("rubric_items", []):
        mark = "[PASS]" if item["passed"] else "[FAIL]"
        print(f"     {mark} {item['criterion']}: {item['note']}")


async def test_weak_answer():
    print_header("TEST 2: Weak / Flawed Technical Answer (Distributed Caching)")
    question = "How would you handle cache stampedes when a high-traffic key expires in Redis?"
    answer = (
        "I think if the cache expires we can just restart Redis or increase the server RAM. "
        "Maybe put another Redis instance in front of Redis so it doesn't crash."
    )

    print(f"Question: \"{question}\"")
    print(f"Candidate Answer: \"{answer}\"\n")

    res = await evaluate_candidate_response(
        skill="DISTRIBUTED_CACHING",
        interviewer_question=question,
        candidate_answer=answer,
        scaffolding_level=0
    )

    print(f"Evaluation Results:")
    print(f"  -> Observation:          {res['observation']} (Expected: 0)")
    print(f"  -> Depth Score:           {res['depth_score']:.2f}")
    print(f"  -> Evaluator Summary:     \"{res['summary']}\"")
    print("  -> Rubric Items:")
    for item in res.get("rubric_items", []):
        mark = "[PASS]" if item["passed"] else "[FAIL]"
        print(f"     {mark} {item['criterion']}: {item['note']}")


async def test_off_topic_answer():
    print_header("TEST 3: Off-Topic / Evasive Response (Strict Penalties)")
    question = "Explain how PostgreSQL handles MVCC and vacuuming."
    answer = (
        "You know, database internals remind me of traffic jams. "
        "Speaking of that, what is the difference between a truck and a bus? "
        "Can you answer that riddle for me?"
    )

    print(f"Question: \"{question}\"")
    print(f"Candidate Answer: \"{answer}\"\n")

    res = await evaluate_candidate_response(
        skill="DATABASE_MODELING_TRANSACTIONS",
        interviewer_question=question,
        candidate_answer=answer,
        scaffolding_level=0
    )

    print(f"Evaluation Results:")
    print(f"  -> Observation:          {res['observation']} (Strict Rule: MUST be 0)")
    print(f"  -> Depth Score:           {res['depth_score']:.2f} (Strict Rule: MUST be ~0.10)")
    print(f"  -> Evaluator Summary:     \"{res['summary']}\"")


async def test_timeout_fallback():
    print_header("TEST 4: Timeout & Error Fallback Safety Mechanism")
    # Force a timeout with timeout_seconds=0.001
    res = await evaluate_candidate_response(
        skill="ASYNC_CONCURRENCY",
        interviewer_question="How does the asyncio event loop schedule coroutines?",
        candidate_answer="It uses an epoll/kqueue selector to poll ready file descriptors.",
        timeout_seconds=0.001
    )

    print("Fallback Triggered Successfully:")
    print(f"  -> Observation:          {res['observation']}")
    print(f"  -> Depth Score:           {res['depth_score']:.2f}")
    print(f"  -> Summary:               \"{res['summary']}\"")


async def main():
    await test_strong_answer()
    await test_weak_answer()
    await test_off_topic_answer()
    await test_timeout_fallback()


if __name__ == "__main__":
    asyncio.run(main())
