# 09 — Session State Engine (FSM)

## Purpose

Manages the full lifecycle of an interview session from creation to report archival,
using a deterministic finite state machine.

## Location

File: app/policy_router.py (SessionState enum, PolicyRouter)
File: app/live_server.py (session_phase, ACTIVE_SESSIONS)

## State Machines (Two Levels)

### Level 1: PolicyRouter FSM (per-turn state)

```
READY
  -> (initialize_session()) -> ACTIVE
  -> (observation==1, mastered) -> ACTIVE (next skill)
  -> (observation==0, scaffold<3) -> SCAFFOLDING_L1/L2/L3
  -> (scaffolding exhausted) -> ACTIVE (next skill)
  -> (mastery surge) -> DEVILS_ADVOCATE
  -> (DA resolved) -> ACTIVE (next skill)
  -> (no more skills) -> COMPLETED
```

### Level 2: Session Phase (per-session phase in live_server.py)

```
INTRO
  -> (first candidate turn) -> DEEP_DIVE
  -> vector match pillars, build graph
DEEP_DIVE
  -> (mastery >= 0.80 OR turns >= 3 on topic) -> topic advance (graph routes)
  -> (no more topics) -> WRAPPING_UP
WRAPPING_UP
  -> (finish event / disconnect) -> reports generated
```

## Session Creation

```
WebSocket connect -> receive init_data (name, level)
-> session_id = f"sess_{uuid.uuid4().hex[:12]}"
-> create_session(session_id, candidate_name, level) -> PostgreSQL
-> PolicyRouter(seniority=tier) initialized
-> policy_router.initialize_session(initial_skills) with tier-defaults
-> ACTIVE_SESSIONS[session_id] = { ... }
-> LATEST_SESSION_ID = session_id
```

## Session Data Structure (ACTIVE_SESSIONS[session_id])

```python
{
  "session_id": str,
  "candidate_name": str,
  "level": str,              # STUDENT / MEDIUM / HARD
  "is_paused": bool,
  "policy_router": PolicyRouter,  # contains graph, mirt, proctor
  "turns_history": list,
  "telemetry": dict,
  "llm_metrics": dict,
  "websocket": WebSocket,
  "ecosystem_summary": dict,
  "pillar_ecosystem_map": dict,
  "get_active_topic": lambda,
  "get_candidate_topics": lambda,
  "get_session_phase": lambda,
  "get_matched_pillars": lambda,
  "get_primary_topic": lambda
}
```

## Session Persistence (3-tier fallback)

1. ACTIVE_SESSIONS (in-memory, lost on restart)
2. SESSION_CACHE (in-memory snapshot updated each turn, survives disconnect but not restart)
3. PostgreSQL interview_sessions + turn_telemetry_logs (permanent)

GET /api/session/{id}/state checks all 3 tiers in order.

## Session Termination

| Trigger | Action |
|---------|--------|
| finish_interview WebSocket event | Generate reports, archive to PostgreSQL |
| REST POST /api/session/{id}/finish | Generate reports, optionally push via WebSocket |
| WebSocket disconnect | Auto-generate reports if turns exist (asyncio.create_task) |
| Graph COMPLETED state | Alex told to conclude warmly |

## Reconnection

Gemini Live session resumption handle tracked in resumption_handle variable.
On GoAway signal or exception: reconnect_gemini() called with saved handle.
Session state (ACTIVE_SESSIONS, SESSION_CACHE) preserved across Gemini reconnects.
Browser WebSocket reconnect: client must re-send init_data to start new session.

## Pause/Resume

- REST: POST /api/session/{id}/pause -> sets is_paused=True, pushes event to browser
- REST: POST /api/session/{id}/resume -> sets is_paused=False
- WebSocket: pause_interview / resume_interview events
- Paused: audio and text inputs blocked (returns session_paused_warning)

## Security

Candidate cannot:
- Select session state via API (states are computed server-side only)
- Inject custom state values via WebSocket (only recognised events processed)
- Access another candidate's session (no shared session namespace enforced by auth — gap)

VULNERABILITY: No authentication. Any client that knows a session_id can query
GET /api/session/{id}/state and read full session state.
