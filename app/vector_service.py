"""
Vector Database Service (Dynoxide / DynamoDB Native Vector Search).
Document Reference: AIS-UPGRADE-2026-V1 / REPORT 7
Uses boto3 native SearchVectors API with Gemini text embeddings.
"""

import os
import asyncio
from typing import List, Dict, Any, Optional
import boto3
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

IS_PRODUCTION = os.getenv("IS_PRODUCTION", "false").lower() == "true"
DYNOXIDE_URL = os.getenv("DYNOXIDE_URL", "http://localhost:8001")
TABLE_NAME = "CompetencyPillars"
INDEX_NAME = "PillarVectorIndex"
EMBEDDING_DIM = 768

# Initialize DynamoDB Client
if not IS_PRODUCTION:
    db_client = boto3.client(
        "dynamodb",
        endpoint_url=DYNOXIDE_URL,
        aws_access_key_id="localDevKey",
        aws_secret_access_key="localDevSecret",
        region_name="us-east-1"
    )
else:
    db_client = boto3.client("dynamodb", region_name="us-east-1")

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Curated Foundational Engineering Competency Pillars (High-Signal Macro Pillars)
SEED_PILLARS = [
    {
        "pillarId": "DISTRIBUTED_CACHING",
        "name": "Distributed Caching & Invalidation",
        "domain": "DISTRIBUTED_SYSTEMS",
        "criticality": "HIGH",
        "descriptors": "Redis Memcached in-memory key-value cache invalidation cache stampede TTL eviction policy LRU write-through write-back data consistency caching layer",
        "probe": "How do you handle cache invalidation and prevent cache stampedes under high concurrency?"
    },
    {
        "pillarId": "ASYNC_CONCURRENCY",
        "name": "Real-Time Streaming & Concurrency",
        "domain": "CONCURRENCY_STREAMING",
        "criticality": "HIGH",
        "descriptors": "WebSockets SSE asynchronous asyncio event loop Netty Goroutines channels non-blocking I/O real-time streaming backpressure thread pool socket handling",
        "probe": "How do you manage horizontal scaling when users are connected to different WebSocket servers?"
    },
    {
        "pillarId": "DATABASE_MODELING_TRANSACTIONS",
        "name": "Data Persistence & Relational Transactions",
        "domain": "DATABASES",
        "criticality": "HIGH",
        "descriptors": "PostgreSQL MySQL relational database SQL schema design ACID transactions indexing isolation levels normalization query optimization foreign keys",
        "probe": "How do you decide indexing strategies to avoid table scans while maintaining write performance?"
    },
    {
        "pillarId": "AI_INFERENCE_ORCHESTRATION",
        "name": "AI Systems & Inference Pipelines",
        "domain": "AI_SYSTEMS",
        "criticality": "HIGH",
        "descriptors": "LLM Gemini OpenAI Claude inference pipeline embeddings vector search RAG model serving latency token limits prompt orchestration agent workflows",
        "probe": "How do you handle rate limits, latency spikes, and failure degradation when orchestrating external LLM APIs?"
    },
    {
        "pillarId": "CONTAINER_INFRASTRUCTURE",
        "name": "Containerization & Cloud Infrastructure",
        "domain": "CLOUD_DEVOPS",
        "criticality": "MEDIUM",
        "descriptors": "Docker Kubernetes container orchestration AWS EC2 ECS load balancing reverse proxy Nginx cloud networking microservices deployment CI/CD",
        "probe": "How do you handle service discovery, health checks, and zero-downtime rolling updates in containerized environments?"
    },
    {
        "pillarId": "EVENT_STREAMING_MESSAGING",
        "name": "Event-Driven Architecture & Message Queues",
        "domain": "DISTRIBUTED_SYSTEMS",
        "criticality": "HIGH",
        "descriptors": "Kafka RabbitMQ AWS SQS message broker event-driven pub-sub consumer groups message ordering dead-letter queues idempotency asynchronous processing",
        "probe": "How do you ensure message ordering and idempotency when consumers fail and reprocess messages?"
    },
    {
        "pillarId": "API_DESIGN_PROTOCOLS",
        "name": "API Architecture & Network Protocols",
        "domain": "API_DESIGN",
        "criticality": "MEDIUM",
        "descriptors": "REST gRPC GraphQL HTTP/2 protocol buffers API design serialization authentication JWT rate limiting endpoint versioning",
        "probe": "What are the trade-offs between gRPC and REST for inter-service communication regarding performance and debugging?"
    },
    {
        "pillarId": "SECURITY_AUTH_IDENTITY",
        "name": "Authentication, Authorization & Security",
        "domain": "SECURITY",
        "criticality": "MEDIUM",
        "descriptors": "OAuth2 JWT session management RBAC encryption SSL TLS token refresh password hashing cross-site scripting CSRF CORS",
        "probe": "How do you securely store and refresh JWT tokens without exposing sessions to XSS or CSRF attacks?"
    },
    {
        "pillarId": "DATA_STRUCTURES_ALGORITHMS",
        "name": "Core Algorithms & Computational Complexity",
        "domain": "DATA_STRUCTURES",
        "criticality": "HIGH",
        "descriptors": "data structures algorithms trees graphs hash tables time complexity space complexity big-O sorting dynamic programming binary search heap priority queue",
        "probe": "How do you choose between a Hash Map and a B-Tree when designing memory-constrained systems?"
    },
    {
        "pillarId": "NOSQL_SPECIALIZED_STORAGE",
        "name": "NoSQL & Specialized Storage Engines",
        "domain": "DATABASES",
        "criticality": "MEDIUM",
        "descriptors": "MongoDB DynamoDB Cassandra Elasticsearch TimescaleDB time-series wide-column document store partitioning sharding eventual consistency",
        "probe": "When does eventual consistency become unacceptable, and how do you enforce strong consistency in distributed NoSQL stores?"
    }
]


def generate_embedding(text: str) -> List[float]:
    """Generates a 768-dimensional normalized embedding using Gemini."""
    try:
        res = gemini_client.models.embed_content(
            model="gemini-embedding-2",
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM)
        )
        return res.embeddings[0].values
    except Exception as e:
        print(f"[VectorService] Embedding error: {e}")
        # Uniform zero vector fallback
        return [0.0] * EMBEDDING_DIM


def ensure_vector_table():
    """Initializes the CompetencyPillars DynamoDB table with Vector Index."""
    try:
        tables = db_client.list_tables().get("TableNames", [])
        if TABLE_NAME not in tables:
            print(f"[VectorService] Creating '{TABLE_NAME}' with Vector Index '{INDEX_NAME}' on {DYNOXIDE_URL}...")
            db_client.create_table(
                TableName=TABLE_NAME,
                KeySchema=[{"AttributeName": "pillarId", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "pillarId", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
                VectorIndexes=[{
                    "IndexName": INDEX_NAME,
                    "VectorAttribute": {"AttributeName": "embedding"},
                    "Dimensions": EMBEDDING_DIM,
                    "DistanceFunction": "COSINE",
                    "Projection": {"ProjectionType": "ALL"}
                }]
            )
            print(f"[VectorService] Table '{TABLE_NAME}' created successfully.")
            # Small wait for index readiness
            asyncio.run(asyncio.sleep(1.0))
        else:
            print(f"[VectorService] Table '{TABLE_NAME}' already exists.")
    except Exception as e:
        print(f"[VectorService] Table initialization error: {e}")


def seed_competency_pillars():
    """Seeds the curated engineering competency pillars with embeddings."""
    ensure_vector_table()
    try:
        scan_res = db_client.scan(TableName=TABLE_NAME, Select="COUNT")
        if scan_res.get("Count", 0) >= len(SEED_PILLARS):
            print(f"[VectorService] Seed pillars already populated ({scan_res.get('Count')} items).")
            return

        print(f"[VectorService] Seeding {len(SEED_PILLARS)} competency pillars with Gemini embeddings...")
        for p in SEED_PILLARS:
            emb = generate_embedding(f"{p['name']}. Domain: {p['domain']}. Keywords: {p['descriptors']}")
            db_client.put_item(
                TableName=TABLE_NAME,
                Item={
                    "pillarId": {"S": p["pillarId"]},
                    "name": {"S": p["name"]},
                    "domain": {"S": p["domain"]},
                    "criticality": {"S": p["criticality"]},
                    "descriptors": {"S": p["descriptors"]},
                    "probe": {"S": p["probe"]},
                    "embedding": {"L": [{"N": str(x)} for x in emb]}
                }
            )
        print(f"[VectorService] Successfully seeded all {len(SEED_PILLARS)} competency pillars into Vector DB.")
    except Exception as e:
        print(f"[VectorService] Seeding error: {e}")


async def match_candidate_topics(intro_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Performs vector similarity search against the CompetencyPillars Vector Index.
    Returns the top-k highest-leverage engineering macro pillars.
    """
    # Run embedding synchronously in thread
    query_emb = await asyncio.to_thread(generate_embedding, intro_text)
    
    search_vector = [{"N": str(x)} for x in query_emb]

    try:
        # Execute search_vectors in thread
        resp = await asyncio.to_thread(
            db_client.search_vectors,
            TableName=TABLE_NAME,
            IndexName=INDEX_NAME,
            SearchVector=search_vector,
            TopK=top_k
        )
        
        matches = []
        for res in resp.get("SearchResults", []):
            item = res.get("Item", {})
            distance = res.get("Score", 1.0)
            # Cosine distance: 0 = identical, 1 = orthogonal, 2 = opposite
            similarity = round(max(0.0, 1.0 - float(distance)), 3)
            matches.append({
                "pillar_id": item.get("pillarId", {}).get("S", ""),
                "name": item.get("name", {}).get("S", ""),
                "domain": item.get("domain", {}).get("S", ""),
                "criticality": item.get("criticality", {}).get("S", "MEDIUM"),
                "probe": item.get("probe", {}).get("S", ""),
                "similarity": similarity
            })

        # Sort by criticality (HIGH before MEDIUM) and similarity
        matches.sort(
            key=lambda x: (1 if x["criticality"] == "HIGH" else 0, x["similarity"]),
            reverse=True
        )
        return matches

    except Exception as e:
        print(f"[VectorService] search_vectors error: {e}. Falling back to default pillars.")
        # Fallback to default high-signal pillars
        return [
            {"pillar_id": "DISTRIBUTED_CACHING", "name": "Distributed Caching & Invalidation", "domain": "DISTRIBUTED_SYSTEMS", "criticality": "HIGH", "similarity": 0.85},
            {"pillar_id": "ASYNC_CONCURRENCY", "name": "Real-Time Streaming & Concurrency", "domain": "CONCURRENCY_STREAMING", "criticality": "HIGH", "similarity": 0.80},
            {"pillar_id": "AI_INFERENCE_ORCHESTRATION", "name": "AI Systems & Inference Pipelines", "domain": "AI_SYSTEMS", "criticality": "HIGH", "similarity": 0.75}
        ]
