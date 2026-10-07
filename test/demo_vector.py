"""
Phase 7 Demo: Testing the Vector Service & Pillar Matching Engine
Simulates 3 distinct candidate introductions:
1. Backend & Caching Engineer (Python, Redis, RabbitMQ)
2. Database & Data Architect (PostgreSQL, SQL, ACID, Sharding)
3. Generative AI Engineer (PyTorch, LLM inference, LangChain, GPU serving)
"""

import sys
import os
import asyncio

# Add root folder to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.vector_service import match_candidate_topics, get_all_pillars


def print_header(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


async def test_candidate_matching():
    candidates = [
        (
            "CANDIDATE 1: Backend Systems & Caching Engineer",
            "I'm a backend engineer with 4 years of experience building Python microservices using FastAPI, Redis caching, and RabbitMQ message queues for high-traffic payments."
        ),
        (
            "CANDIDATE 2: Database Architect & ACID Specialist",
            "I specialize in PostgreSQL database schema design, optimizing complex SQL queries, index tuning, and managing ACID transactions across distributed shards."
        ),
        (
            "CANDIDATE 3: Generative AI & Inference Systems Engineer",
            "I build generative AI applications with PyTorch, LangChain, vector databases, and fine-tune open-source LLMs deployed on vLLM GPU clusters for low-latency streaming."
        )
    ]

    for title, intro in candidates:
        print_header(title)
        print(f"Candidate Intro: \"{intro}\"\n")
        print("Vector Matching against 10 Macro Pillars...")
        
        matches = await match_candidate_topics(intro, top_k=3)
        print(f"Top-{len(matches)} Matched Pillars (feeds into Knowledge Graph):")
        for i, m in enumerate(matches, 1):
            print(f"  #{i} [{m['pillar_id']:<30}] Sim: {m['similarity']:.3f} | Domain: {m['domain']}")
            print(f"      Initial Technical Probe: \"{m.get('probe', 'N/A')}\"")


def test_pillars_inventory():
    print_header("INVENTORY: 10 Standard Macro Technical Pillars")
    pillars = get_all_pillars()
    for p in pillars:
        print(f"  * {p['pillar_id']:<30} Domain: {p['domain']:<22} Criticality: {p['criticality']}")


async def main():
    test_pillars_inventory()
    await test_candidate_matching()


if __name__ == "__main__":
    asyncio.run(main())
