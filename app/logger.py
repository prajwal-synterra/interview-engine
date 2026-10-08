"""
Centralized File & Console Logger for the Socratic Interview Engine.
Writes timestamped entries to stdout and logs/interview_engine.log.
"""

import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "interview_engine.log"


def log_event(category: str, message: str, details: Any = None):
    """Writes a timestamped log entry to both stdout and logs/interview_engine.log."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] [{category.upper()}] {message}"
    if details is not None:
        formatted_msg += f"\n  -> Details: {details}"

    print(formatted_msg, flush=True)

    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted_msg + "\n")
            f.flush()
    except Exception as e:
        print(f"[LOGGER ERROR]: Could not write to log file: {e}", file=sys.stderr)


def log_speech(speaker: str, text: str):
    log_event("SPEECH", f"[{speaker}]: {text}")


def log_shadow_eval(turn_idx: int, skill: str, obs: int, depth: float, summary: str):
    log_event("SHADOW_EVAL", f"Turn #{turn_idx} ({skill}) | Obs: {obs} | Depth: {depth * 100:.0f}%", summary)


def log_bkt_math(skill: str, prior: float, post: float, delta: float, p_s: float):
    log_event("BKT_MATH", f"{skill} | Prior: {prior} -> Post: {post} (Delta: {delta:+.4f}) | Ps: {p_s}")


def log_policy(prev_state: str, new_state: str, action: str, directive: str):
    log_event("POLICY_FSM", f"Transition: {prev_state} -> {new_state} | Action: {action} | Directive: {directive}")


def log_proctor(bii: float, risk: float, status: str):
    log_event("PROCTOR", f"BII: {bii:.3f} | Risk: {risk:.2f} | Status: {status}")


def log_report(report_type: str, path: str):
    log_event("REPORT_GEN", f"Generated {report_type} at {path}")
