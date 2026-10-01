# 11 — Domain Evaluation Engine

## Purpose

Maps candidate expertise to specific engineering domains and calibrates
Alex's dialect and the Shadow Evaluator's rubric to the candidate's tech stack.

## Components

| File | Function | Role |
|------|----------|------|
| app/vector_service.py | match_candidate_topics() | Vector similarity search -> top pillar IDs |
| app/ecosystem_service.py | detect_ecosystems_from_intro() | Language ecosystem detection |
| app/ecosystem_service.py | bind_pillars_to_ecosystems() | Bind pillars to detected ecosystems |
| app/graph_engine.py | build_dynamic_pillar_graph() | Graph topology from matched pillars |

## Supported Competency Pillars (IMPLEMENTED)

| Pillar ID | Name | Domain |
|-----------|------|--------|
| DISTRIBUTED_CACHING | Distributed Caching & Invalidation | DISTRIBUTED_SYSTEMS |
| ASYNC_CONCURRENCY | Real-Time Streaming & Concurrency | CONCURRENCY_STREAMING |
| DATABASE_MODELING_TRANSACTIONS | Data Persistence & Relational Transactions | DATABASES |
| AI_INFERENCE_ORCHESTRATION | AI Systems & Inference Pipelines | AI_SYSTEMS |
| CONTAINER_INFRASTRUCTURE | Containerization & Cloud Infrastructure | CLOUD_DEVOPS |
| EVENT_STREAMING_MESSAGING | Event-Driven Architecture & Message Queues | DISTRIBUTED_SYSTEMS |
| API_DESIGN_PROTOCOLS | API Architecture & Network Protocols | API_DESIGN |
| SECURITY_AUTH_IDENTITY | Authentication, Authorization & Security | SECURITY |
| DATA_STRUCTURES_ALGORITHMS | Core Algorithms & Computational Complexity | DATA_STRUCTURES |
| NOSQL_SPECIALIZED_STORAGE | NoSQL & Specialized Storage Engines | DATABASES |

## Supported Language Ecosystems (IMPLEMENTED)

| Ecosystem | Detected by Keywords |
|-----------|---------------------|
| JAVA_JVM | java, spring, springboot, netty, jvm, kotlin, scala, hibernate |
| PYTHON | python, pytorch, tensorflow, fastapi, flask, django, pandas, numpy, asyncio |
| GOLANG | go, golang, goroutine, channels, gin, grpc, gorm |
| NODE_TS | node, nodejs, typescript, javascript, express, nestjs, v8, libuv |
| CPP_RUST | c++, rust, cargo, tokio, raii, borrow checker |
| GENERAL_SYSTEMS | fallback (no keywords detected) |

## Domain Coverage by Role

| Role | Coverage |
|------|---------|
| General Systems / Backend | IMPLEMENTED (ASYNC_CONCURRENCY, DISTRIBUTED_CACHING, API_DESIGN_PROTOCOLS, DATABASE) |
| AI/ML Engineer | IMPLEMENTED (AI_INFERENCE_ORCHESTRATION pillar + PYTHON ecosystem) |
| SDE (DSA focus) | PARTIAL (DATA_STRUCTURES_ALGORITHMS pillar exists) |
| Python Backend | PARTIAL (PYTHON ecosystem directive, generic pillars) |
| Java Developer | PARTIAL (JAVA_JVM ecosystem directive, generic pillars) |
| Mobile / Flutter | NOT IMPLEMENTED |
| Full Stack | NOT IMPLEMENTED |
| DevOps / Cloud (standalone) | NOT IMPLEMENTED (CONTAINER_INFRASTRUCTURE pillar exists but no DevOps ecosystem) |

## How Domain Evaluation Works

1. Candidate introduces themselves (INTRO turn)
2. Introduction text -> match_candidate_topics() -> vector similarity -> top-3 pillars
3. Introduction text -> detect_ecosystems_from_intro() -> primary_ecosystem + all_ecosystems
4. bind_pillars_to_ecosystems() -> assigns each pillar to its matched ecosystem dialect
5. Policy router graph built from matched pillars
6. Each turn: get_ecosystem_directive() injects language-specific idioms into Alex's prompt
7. Shadow Evaluator receives ecosystem context for rubric calibration

## Fallback when Vector Search Fails

Falls back to default high-signal pillars:
- DISTRIBUTED_CACHING (similarity 0.85)
- ASYNC_CONCURRENCY (similarity 0.80)
- AI_INFERENCE_ORCHESTRATION (similarity 0.75)

## Polyglot Candidate Handling

If candidate mentions multiple ecosystems (e.g. Python + Java):
- is_polyglot = True
- each pillar bound to its most relevant ecosystem
- ASYNC_CONCURRENCY -> JAVA_JVM if Java keywords found nearby
- AI_INFERENCE_ORCHESTRATION -> PYTHON if Python keywords found
