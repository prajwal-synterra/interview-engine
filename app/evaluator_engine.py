"""
Shadow Evaluator Engine (Gemini REST API).
Evaluates candidate responses asynchronously against technical rubrics without blocking voice streaming.
Document Reference: AIS-ARCH-2026-V3-MASTER (Dual-LLM Quarantined Architecture)
"""


import os
import json
import asyncio
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Optional import of google-genai client
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None
# Initialize GenAI Client
_client = None
evaluator_api_key = os.getenv("EVALUATOR_API_KEY") or os.getenv("GEMINI_API_KEY")
if genai and evaluator_api_key:
    try:
        _client = genai.Client(api_key=evaluator_api_key)
    except Exception as e:
        print(f"[Shadow Evaluator Warning] Client init failed: {e}")


async def evaluate_candidate_response(
    skill: str,
    interviewer_question: str,
    candidate_answer: str,
    scaffolding_level: int = 0,
    ecosystem_context: str = "",
    model_name: Optional[str] = None,
    timeout_seconds: float = 6.5
) -> Dict[str, Any]:
    """
    Evaluates candidate response using structured JSON output from Gemini REST API.
    Does not block audio streaming - runs asynchronously in background with a strict 6.5s timeout.
    """
    if not model_name:
        model_name = os.getenv("EVALUATOR_MODEL", "gemini-3.8-flash")
    prompt = f"""You are the Shadow Technical Evaluator in a Socratic Engineering Interview.
Evaluate the candidate's technical response against the rubric criteria.
CONTEXT:
Skill: {skill}
Scaffolding Level: L{scaffolding_level} (0 = Free response, 1-3 = Guided hints)
Interviewer Question: "{interviewer_question}"
Candidate Answer: "{candidate_answer}"
Runtime / Ecosystem Context: {ecosystem_context or "General Systems Architecture"}
EVALUATION RUBRIC:
1. Concept Depth: Did they understand the underlying principles and abstractions?
2. Practical Implementation: Did they mention concrete tools, patterns, or real-world constraints appropriate for the active ecosystem?
3. Trade-off Awareness: Did they identify failure modes, complexity, or system tradeoffs?
4. Technical Relevance & Focus: Did the candidate directly address the technical prompt? If the candidate asked unrelated trivia questions (e.g. riddles, testing the interviewer), went completely off-topic, or gave evasive non-technical commentary, you MUST set "observation": 0 and "depth_score": 0.10.
Return a strict JSON object with this exact schema:
{{
  "observation": 1,
  "depth_score": 0.85,
  "estimated_difficulty": 0.4,
  "summary": "1-2 sentence concise technical assessment",
  "rubric_items": [
    {{"criterion": "Core Concept Depth", "passed": true, "note": "Clear explanation"}},
    {{"criterion": "Practical Implementation", "passed": true, "note": "Mentioned real tools"}},
    {{"criterion": "Trade-off Awareness", "passed": false, "note": "Did not explore edge cases"}},
    {{"criterion": "Technical Relevance", "passed": true, "note": "Directly addressed prompt"}}
  ],
  "recommended_probe": "Suggested follow-up concept to explore"
}}
Set "observation" to 1 if response meets expectations for this level, or 0 if fundamentally flawed/incomplete/off-topic.
"estimated_difficulty" should range from -1.5 (very basic) to +2.5 (advanced staff frontier).
"""
    if _client is not None and types is not None:
        gen_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            thinking_config=types.ThinkingConfig(thinking_budget=0)
        )

        # Retry loop to gracefully handle momentary Google 503 capacity spikes
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                response = await asyncio.wait_for(
                    _client.aio.models.generate_content(
                        model=model_name,
                        contents=[prompt],
                        config=gen_config
                    ),
                    timeout=timeout_seconds
                )
                data = json.loads(response.text.strip())

                # Ensure required numeric keys exist
                if "observation" not in data:
                    data["observation"] = 1 if data.get("depth_score", 0.5) >= 0.6 else 0
                if "depth_score" not in data:
                    data["depth_score"] = 0.75 if data["observation"] == 1 else 0.30
                if "estimated_difficulty" not in data:
                    data["estimated_difficulty"] = 0.3 * (scaffolding_level + 1)

                usage = getattr(response, "usage_metadata", None)
                if usage:
                    data["usage_metadata"] = {
                        "prompt_token_count": getattr(usage, "prompt_token_count", 0),
                        "candidates_token_count": getattr(usage, "candidates_token_count", 0),
                        "total_token_count": getattr(usage, "total_token_count", 0)
                    }

                return data

            except asyncio.TimeoutError:
                print(f"[Shadow Evaluator] Timeout ({timeout_seconds}s exceeded). Triggering safety fallback.")
                break
            except Exception as e:
                err_str = str(e)
                # If Google has a temporary 503 spike, wait 0.8s and retry once
                if ("503" in err_str or "UNAVAILABLE" in err_str) and attempt < max_attempts - 1:
                    print(f"[Shadow Evaluator] Temporary Google 503 capacity spike on attempt {attempt+1}. Retrying in 0.8s...")
                    await asyncio.sleep(0.8)
                    continue

                print(f"[Shadow Evaluator Error] {e}. Triggering safety fallback.")
                break
    # Robust Fallback (runs if API is offline, key missing, or call timed out)
    word_count = len(candidate_answer.split())
    is_pass = 1 if word_count > 15 else 0
    return {
        "observation": is_pass,
        "depth_score": 0.70 if is_pass else 0.35,
        "estimated_difficulty": round(0.2 * scaffolding_level + 0.3, 2),
        "summary": "Evaluation fallback triggered (deterministic heuristic applied).",
        "rubric_items": [
            {"criterion": "Core Concept Depth", "passed": bool(is_pass), "note": "Assessed via fallback"},
            {"criterion": "Practical Implementation", "passed": bool(is_pass), "note": "Assessed via fallback"},
            {"criterion": "Trade-off Awareness", "passed": False, "note": "Pending deeper exploration"},
            {"criterion": "Technical Relevance", "passed": bool(is_pass), "note": "Assessed via fallback"}
        ],
        "recommended_probe": "Explore specific trade-offs and failure modes."
    }
