"""
Ecosystem & Polyglot Technical Detection Engine.
Detects programming language ecosystems (Python, Java/JVM, Go, Node.js, C++/Rust)
from candidate introductions and binds competency pillars to idiomatic system directives.
"""

import re
from typing import Dict, List, Any


ECOSYSTEM_KEYWORDS: Dict[str, List[str]] = {
    "JAVA_JVM": [
        "java", "spring", "springboot", "spring boot", "netty", "jvm",
        "kotlin", "scala", "hibernate", "maven", "gradle", "quarkus", "micronaut"
    ],
    "PYTHON": [
        "python", "pytorch", "tensorflow", "fastapi", "flask", "django",
        "pandas", "numpy", "asyncio", "celery", "pydantic", "sqlalchemy", "cpython"
    ],
    "GOLANG": [
        "go", "golang", "goroutine", "goroutines", "channels", "gin",
        "grpc", "gorm", "chi", "echo", "mutex"
    ],
    "NODE_TS": [
        "node", "nodejs", "node.js", "typescript", "javascript", "express",
        "nestjs", "v8", "libuv", "fastify", "deno", "bun"
    ],
    "CPP_RUST": [
        "c++", "cpp", "rust", "cargo", "tokio", "raii", "borrow checker",
        "actix", "cmake", "llvm", "valgrind"
    ]
}


ECOSYSTEM_DIALECT_DIRECTIVES: Dict[str, Dict[str, str]] = {
    "JAVA_JVM": {
        "persona_tone": "Senior JVM Platform Architect",
        "idioms": "JVM memory model, GC pause mitigation (G1/ZGC), thread pool sizing (ExecutorService), thread-safety, Netty event loops, Project Loom virtual threads.",
        "directive": (
            "[ECOSYSTEM DIRECTIVE: JAVA / JVM RUNTIME]\n"
            "- Speak using idiomatic Java & JVM terminology.\n"
            "- Drill into: JVM heap allocation, GC pause mitigation (G1/ZGC), thread pools, thread safety, or virtual threads.\n"
            "- Do NOT mention Python GIL or Node.js event loop."
        ),
        "evaluator_context": "Candidate is answering in a Java/JVM ecosystem. Evaluate based on JVM memory model, thread safety, class design, and garbage collection awareness."
    },
    "PYTHON": {
        "persona_tone": "High-Performance Python Systems Engineer",
        "idioms": "CPython Global Interpreter Lock (GIL), asyncio event loop vs multiprocessing worker pools, PyTorch CUDA tensor memory management, Cython/C-extensions, memory profiling (tracemalloc), FastAPI ASGI workers.",
        "directive": (
            "[ECOSYSTEM DIRECTIVE: PYTHON ECOSYSTEM]\n"
            "- Speak using idiomatic Python systems terminology.\n"
            "- Drill into: CPython GIL contention, asyncio vs multiprocessing for CPU-bound tasks, FastAPI ASGI worker concurrency, memory management (ref counting + cyclic GC).\n"
            "- Do NOT ask about JVM GC flags or Java interfaces."
        ),
        "evaluator_context": "Candidate is answering in a Python ecosystem. Evaluate based on CPython internals, GIL awareness, async I/O mechanics, and memory management."
    },
    "GOLANG": {
        "persona_tone": "Cloud-Native Go Infrastructure Engineer",
        "idioms": "Goroutine stack allocation (2KB start), M:N runtime scheduler (GMP model), buffered vs unbuffered channels, select statements, sync.Mutex/RWMutex vs channel passing, GC pacing (GOGC), zero-copy byte slicing.",
        "directive": (
            "[ECOSYSTEM DIRECTIVE: GOLANG RUNTIME]\n"
            "- Speak using idiomatic Go systems terminology.\n"
            "- Drill into: Goroutine scheduling (GMP model), channel deadlocks, select timeouts, context cancellation propagation, GC pacing, and memory escaping to the heap.\n"
            "- Do NOT mention Python GIL or Java virtual machines."
        ),
        "evaluator_context": "Candidate is answering in a Go ecosystem. Evaluate based on idiomatic concurrency (channels, mutexes, GMP scheduler), error handling, and zero-allocation patterns."
    },
    "NODE_TS": {
        "persona_tone": "High-Throughput Node.js / V8 Architect",
        "idioms": "V8 engine heap limits, libuv event loop phases (timers, poll, check), microtasks vs macrotasks, Worker Threads, cluster module, backpressure in streams, Buffer allocation.",
        "directive": (
            "[ECOSYSTEM DIRECTIVE: NODE.JS / TYPESCRIPT RUNTIME]\n"
            "- Speak using idiomatic Node.js & V8 runtime terminology.\n"
            "- Drill into: Libuv event loop blocking, microtask starvation (process.nextTick vs Promise), streaming backpressure, Worker Threads for CPU intensive tasks, and V8 heap profiling.\n"
            "- Do NOT ask about JVM GC or Python GIL."
        ),
        "evaluator_context": "Candidate is answering in a Node.js/TypeScript ecosystem. Evaluate based on non-blocking I/O, event loop phases, and streaming architecture."
    },
    "CPP_RUST": {
        "persona_tone": "Systems & Low-Latency Performance Engineer",
        "idioms": "RAII, memory ownership, zero-cost abstractions, cache locality, lock-free data structures, atomics, Tokio asynchronous runtime, borrow checker.",
        "directive": (
            "[ECOSYSTEM DIRECTIVE: C++ / RUST SYSTEMS]\n"
            "- Speak using low-level systems programming terminology.\n"
            "- Drill into: Cache misses, memory layout, lock-free atomic CAS operations, zero-copy networking, RAII destructor ordering, and borrow checker concurrency safety.\n"
        ),
        "evaluator_context": "Candidate is answering in a C++/Rust low-level systems ecosystem. Evaluate based on mechanical sympathy, memory safety, and computational efficiency."
    },
    "GENERAL_SYSTEMS": {
        "persona_tone": "Principal Systems Architect",
        "idioms": "Distributed consensus, caching, horizontal scaling, transaction isolation, network latency, failure recovery.",
        "directive": (
            "[ECOSYSTEM DIRECTIVE: GENERAL SYSTEMS ARCHITECTURE]\n"
            "- Explore high-level architecture, network protocols, data consistency, and operational trade-offs."
        ),
        "evaluator_context": "Evaluate based on fundamental distributed systems principles and sound architectural reasoning."
    }
}


def detect_ecosystems_from_intro(intro_text: str) -> Dict[str, Any]:
    """
    Parses a candidate's introduction and extracts project-scoped language ecosystems.
    Returns detected primary ecosystem, all detected ecosystems, and stack keywords.
    """
    intro_lower = intro_text.lower()
    detected_ecosystems = []
    stack_keywords = []

    for eco, keywords in ECOSYSTEM_KEYWORDS.items():
        found = [k for k in keywords if re.search(r'\b' + re.escape(k) + r'\b', intro_lower)]
        if found:
            detected_ecosystems.append((eco, len(found)))
            stack_keywords.extend(found)

    # Sort by keyword match density
    detected_ecosystems.sort(key=lambda x: x[1], reverse=True)

    primary = detected_ecosystems[0][0] if detected_ecosystems else "GENERAL_SYSTEMS"
    ecosystem_list = [e[0] for e in detected_ecosystems] if detected_ecosystems else ["GENERAL_SYSTEMS"]

    return {
        "primary_ecosystem": primary,
        "all_ecosystems": ecosystem_list,
        "stack_keywords": list(set(stack_keywords)),
        "is_polyglot": len(ecosystem_list) > 1
    }


def bind_pillars_to_ecosystems(
    matched_pillars: List[Dict],
    intro_text: str
) -> Dict[str, str]:
    """
    Binds each matched competency pillar to its most relevant project ecosystem.
    e.g. If candidate mentioned 'Spring Boot microservice' and 'PyTorch model',
    EVENT_STREAMING binds to JAVA_JVM, and AI_INFERENCE binds to PYTHON.
    """
    intro_lower = intro_text.lower()
    pillar_ecosystem_map: Dict[str, str] = {}
    default_eco = detect_ecosystems_from_intro(intro_text)["primary_ecosystem"]

    for p in matched_pillars:
        pid = p.get("pillar_id") or p.get("pillarId", "")
        assigned = default_eco

        # Java indicators near concurrency / messaging
        if pid in ("ASYNC_CONCURRENCY", "EVENT_STREAMING_MESSAGING", "DISTRIBUTED_CACHING"):
            if any(k in intro_lower for k in ["java", "spring", "netty", "jvm"]):
                assigned = "JAVA_JVM"
            elif any(k in intro_lower for k in ["go", "golang", "goroutine"]):
                assigned = "GOLANG"

        # Python indicators near AI / data
        if pid in ("AI_INFERENCE_ORCHESTRATION", "DATA_STRUCTURES_ALGORITHMS"):
            if any(k in intro_lower for k in ["python", "pytorch", "fastapi", "django"]):
                assigned = "PYTHON"

        pillar_ecosystem_map[pid] = assigned

    return pillar_ecosystem_map


def get_ecosystem_directive(pillar_id: str, pillar_ecosystem_map: Dict[str, str]) -> str:
    """Returns the Socratic prompt injection for Alex based on the active topic's ecosystem."""
    eco = pillar_ecosystem_map.get(pillar_id, "GENERAL_SYSTEMS")
    info = ECOSYSTEM_DIALECT_DIRECTIVES.get(eco, ECOSYSTEM_DIALECT_DIRECTIVES["GENERAL_SYSTEMS"])
    return f"{info['directive']}\nActive Topic: {pillar_id} | Technical Dialect: {info['persona_tone']}"


def get_evaluator_ecosystem_context(pillar_id: str, pillar_ecosystem_map: Dict[str, str]) -> str:
    """Returns ecosystem context for the Shadow Evaluator rubric."""
    eco = pillar_ecosystem_map.get(pillar_id, "GENERAL_SYSTEMS")
    info = ECOSYSTEM_DIALECT_DIRECTIVES.get(eco, ECOSYSTEM_DIALECT_DIRECTIVES["GENERAL_SYSTEMS"])
    return info["evaluator_context"]
