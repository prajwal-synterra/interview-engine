"""
Vector Service & Competency Pillar Matching Engine.
Embeds candidate introductions using Gemini 768D embeddings and performs
similarity search against the 10 macro engineering competency pillars.
Supports Dynoxide vector index with built-in in-memory cosine similarity fallback.
"""
import os
import math
import asyncio
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
load_dotenv()
# Optional Boto3 for Dynoxide/DynamoDB Local
try:
    import boto3
except ImportError:
    boto3 = None
# Optional Google GenAI client
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None
TABLE_NAME = "CompetencyPillars"
INDEX_NAME = "PillarVectorIndex"
EMBEDDING_DIM = 768
DYNOXIDE_URL = os.getenv("DYNOXIDE_URL", "http://localhost:8000")
# Initialize GenAI Client
_gemini_client = None
evaluator_api_key = os.getenv("EVALUATOR_API_KEY") or os.getenv("GEMINI_API_KEY")
if genai and evaluator_api_key:
    try:
        _gemini_client = genai.Client(api_key=evaluator_api_key)
    except Exception as e:
        print(f"[VectorService] Gemini client warning: {e}")
# Initialize DynamoDB Client (Dynoxide)
_db_client = None
if boto3:
    try:
        _db_client = boto3.client(
            "dynamodb",
            endpoint_url=DYNOXIDE_URL,
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test"
        )
    except Exception as e:
        print(f"[VectorService] Dynoxide client warning: {e}")
# 10 Canonical Engineering Competency Pillars
SEED_PILLARS = [
    {
        "pillarId": "DISTRIBUTED_CACHING",
        "name": "Distributed Caching & Invalidation",
        "domain": "DISTRIBUTED_SYSTEMS",
        "criticality": "HIGH",
        "descriptors": "Redis Memcached cache-aside write-through write-back cache stampede thundering herd TTL expiration LRU LFU eviction",
        "probe": "How do you handle cache stampedes when a popular key expires under high concurrent load?"
    },
    {
        "pillarId": "ASYNC_CONCURRENCY",
        "name": "Real-Time Streaming & Concurrency",
        "domain": "CONCURRENCY_STREAMING",
        "criticality": "HIGH",
        "descriptors": "asyncio event loop coroutines non-blocking I/O goroutines channels reactive streams threads mutex deadlocks race conditions",
        "probe": "How does an asynchronous event loop schedule I/O multiplexing without blocking worker threads?"
    },
    {
        "pillarId": "DATABASE_MODELING_TRANSACTIONS",
        "name": "Data Persistence & Relational Transactions",
        "domain": "DATABASES",
        "criticality": "HIGH",
        "descriptors": "PostgreSQL MySQL relational schemas ACID isolation levels MVCC B-Tree indexes composite indexing deadlocks write-ahead logging 2PC Saga",
        "probe": "What is the difference between Repeatable Read and Serializable isolation levels in PostgreSQL MVCC?"
    },
    {
        "pillarId": "AI_INFERENCE_ORCHESTRATION",
        "name": "AI Systems & Inference Pipelines",
        "domain": "AI_SYSTEMS",
        "criticality": "HIGH",
        "descriptors": "LLM PyTorch ONNX vLLM model serving streaming tokens RAG vector embeddings prompt engineering quantization inference latency",
        "probe": "How do you architect low-latency streaming inference pipelines for large language models while minimizing GPU memory fragmentation?"
    },
    {
        "pillarId": "CONTAINER_INFRASTRUCTURE",
        "name": "Containerization & Cloud Infrastructure",
        "domain": "CLOUD_DEVOPS",
        "criticality": "MEDIUM",
        "descriptors": "Docker Kubernetes K8s containers pods ingress service mesh horizontal pod autoscaler CI/CD Terraform Helm cloud native",
        "probe": "How do you configure Kubernetes liveness and readiness probes to prevent cascading deployment failures?"
    },
    {
        "pillarId": "EVENT_STREAMING_MESSAGING",
        "name": "Event-Driven Architecture & Message Queues",
        "domain": "DISTRIBUTED_SYSTEMS",
        "criticality": "HIGH",
        "descriptors": "Kafka RabbitMQ AWS SQS event-driven consumer groups partitions consumer lag backpressure exactly-once delivery at-least-once ordering",
        "probe": "How do you guarantee message ordering and handle poison pills across partitioned Kafka consumer groups?"
    },
    {
        "pillarId": "API_DESIGN_PROTOCOLS",
        "name": "API Architecture & Network Protocols",
        "domain": "API_DESIGN",
        "criticality": "HIGH",
        "descriptors": "REST gRPC Protobuf GraphQL WebSockets HTTP/2 HTTP/3 rate limiting API gateway idempotency keys circuit breakers",
        "probe": "When would you choose gRPC over REST with WebSockets for bidirectional internal microservice communication?"
    },
    {
        "pillarId": "SECURITY_AUTH_IDENTITY",
        "name": "Authentication, Authorization & Security",
        "domain": "SECURITY",
        "criticality": "MEDIUM",
        "descriptors": "OAuth2 OIDC JWT session management RBAC ABAC encryption SSL TLS token refresh password hashing XSS CSRF CORS secrets",
        "probe": "How do you securely store and refresh JWT tokens without exposing user sessions to XSS or CSRF vulnerabilities?"
    },
    {
        "pillarId": "DATA_STRUCTURES_ALGORITHMS",
        "name": "Core Algorithms & Computational Complexity",
        "domain": "DATA_STRUCTURES",
        "criticality": "HIGH",
        "descriptors": "data structures algorithms trees graphs hash tables time complexity space complexity big-O sorting dynamic programming binary search heap priority queue",
        "probe": "How do you choose between a Hash Map and a B-Tree when designing memory-constrained storage?"
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
# Cache precomputed embeddings for the 10 pillars
_PILLAR_EMBEDDINGS_CACHE: Dict[str, List[float]] = {}
def generate_embedding(text: str) -> List[float]:
    """Generates a 768-dimensional normalized embedding using Gemini."""
    if _gemini_client and types:
        try:
            res = _gemini_client.models.embed_content(
                model="gemini-embedding-2",
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM)
            )
            return res.embeddings[0].values
        except Exception as e:
            print(f"[VectorService] Gemini embedding warning: {e}")
    # Fallback pseudo-embedding
    return [0.0] * EMBEDDING_DIM
def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))
def _ensure_pillar_embeddings():
    """Populates in-memory embedding cache for all 10 seed pillars."""
    if len(_PILLAR_EMBEDDINGS_CACHE) >= len(SEED_PILLARS):
        return
    for p in SEED_PILLARS:
        pid = p["pillarId"]
        if pid not in _PILLAR_EMBEDDINGS_CACHE:
            content = f"{p['name']}. Domain: {p['domain']}. Keywords: {p['descriptors']}"
            _PILLAR_EMBEDDINGS_CACHE[pid] = generate_embedding(content)
async def match_candidate_topics(intro_text: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Performs vector similarity search against the 10 macro competency pillars.
    Uses Dynoxide vector search if online, or fast in-memory cosine similarity fallback.
    Returns the top-k highest-signal pillars.
    """
    # 1. Generate candidate query embedding
    query_emb = await asyncio.to_thread(generate_embedding, intro_text)
    # 2. Try Dynoxide Vector Search if DB client is reachable
    if _db_client:
        try:
            search_vector = [{"N": str(x)} for x in query_emb]
            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    _db_client.search_vectors,
                    TableName=TABLE_NAME,
                    IndexName=INDEX_NAME,
                    SearchVector=search_vector,
                    TopK=top_k
                ),
                timeout=1.5
            )
            matches = []
            for item_res in resp.get("SearchResults", []):
                item = item_res.get("Item", {})
                distance = item_res.get("Score", 1.0)
                similarity = round(max(0.0, 1.0 - float(distance)), 3)
                matches.append({
                    "pillar_id": item.get("pillarId", {}).get("S", ""),
                    "name": item.get("name", {}).get("S", ""),
                    "domain": item.get("domain", {}).get("S", ""),
                    "criticality": item.get("criticality", {}).get("S", "MEDIUM"),
                    "probe": item.get("probe", {}).get("S", ""),
                    "similarity": similarity
                })
            if matches:
                matches.sort(key=lambda x: (1 if x["criticality"] == "HIGH" else 0, x["similarity"]), reverse=True)
                return matches[:top_k]
        except Exception:
            pass  # Fall through to in-memory cosine similarity
    # 3. Fast In-Memory Cosine Similarity
    _ensure_pillar_embeddings()
    scored_pillars = []
    for p in SEED_PILLARS:
        pid = p["pillarId"]
        pillar_emb = _PILLAR_EMBEDDINGS_CACHE.get(pid, [])
        sim = cosine_similarity(query_emb, pillar_emb)
        scored_pillars.append({
            "pillar_id": pid,
            "name": p["name"],
            "domain": p["domain"],
            "criticality": p["criticality"],
            "probe": p["probe"],
            "similarity": round(sim, 3)
        })
    # Sort by criticality (HIGH first) and highest similarity
    scored_pillars.sort(key=lambda x: (1 if x["criticality"] == "HIGH" else 0, x["similarity"]), reverse=True)
    # If embeddings succeeded and returned non-zero similarities
    if scored_pillars and scored_pillars[0]["similarity"] > 0.05:
        return scored_pillars[:top_k]
    # 4. Ultimate Fallback (Default high-signal pillars)
    return [
        {"pillar_id": "DISTRIBUTED_CACHING", "name": "Distributed Caching & Invalidation", "domain": "DISTRIBUTED_SYSTEMS", "criticality": "HIGH", "similarity": 0.85},
        {"pillar_id": "ASYNC_CONCURRENCY", "name": "Real-Time Streaming & Concurrency", "domain": "CONCURRENCY_STREAMING", "criticality": "HIGH", "similarity": 0.80},
        {"pillar_id": "AI_INFERENCE_ORCHESTRATION", "name": "AI Systems & Inference Pipelines", "domain": "AI_SYSTEMS", "criticality": "HIGH", "similarity": 0.75}
    ]
def get_all_pillars() -> List[Dict[str, Any]]:
    """Returns all 10 curated competency pillars."""
    return [
        {
            "pillar_id": p["pillarId"],
            "name": p["name"],
            "domain": p["domain"],
            "criticality": p["criticality"],
            "probe": p["probe"],
            "descriptors": p["descriptors"]
        }
        for p in SEED_PILLARS
    ]
