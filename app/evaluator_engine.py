"""
Shadow Evaluator Engine (Gemini REST API).
Evaluates candidate responses asynchronously against technical rubrics without candidate latency.
Document Reference: AIS-ARCH-2026-V3-MASTER (Dual-LLM Quarantined Architecture)
"""

import os
import json
from typing import Dict, Any, List
from google import genai
from google.genai import types

from dotenv import load_dotenv

load_dotenv()
evaluator_api_key = os.getenv("EVALUATOR_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=evaluator_api_key)
print("[Shadow Evaluator] Initialized with dedicated evaluation API key.")


async def evaluate_candidate_response(
    skill: str,
    interviewer_question: str,
    candidate_answer: str,
    scaffolding_level: int = 0
) -> Dict[str, Any]:
    """
    Evaluates candidate response using structured JSON output from Gemini REST API.
    Does not block audio streaming - runs asynchronously.
    """
    prompt = f"""You are the Shadow Technical Evaluator in a Socratic Engineering Interview.
Evaluate the candidate's technical response against the rubric criteria.

CONTEXT:
Skill: {skill}
Scaffolding Level: L{scaffolding_level} (0 = Free response, 1-3 = Guided hints)
Interviewer Question: "{interviewer_question}"
Candidate Answer: "{candidate_answer}"

EVALUATION RUBRIC:
1. Concept Depth: Did they understand the underlying principles and abstractions?
2. Practical Implementation: Did they mention concrete tools, patterns, or real-world constraints?
3. Trade-off Awareness: Did they identify failure modes, complexity, or system tradeoffs?

Return a strict JSON object with this exact schema:
{{
  "observation": 1,
  "depth_score": 0.85,
  "summary": "1-2 sentence concise technical assessment",
  "rubric_items": [
    {{"criterion": "Core Concept Depth", "passed": true, "note": "Clear explanation"}},
    {{"criterion": "Practical Implementation", "passed": true, "note": "Mentioned real tools"}},
    {{"criterion": "Trade-off Awareness", "passed": false, "note": "Did not explore edge cases"}}
  ],
  "recommended_probe": "Suggested follow-up concept to explore"
}}
Set "observation" to 1 if response meets expectations for this level, or 0 if fundamentally flawed/incomplete.
"""

    try:
        response = await client.aio.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )
        data = json.loads(response.text.strip())
        return data
    except Exception as e:
        print(f"[Shadow Evaluator Error]: {e}")
        # Robust fallback
        is_pass = 1 if len(candidate_answer.split()) > 15 else 0
        return {
            "observation": is_pass,
            "depth_score": 0.70 if is_pass else 0.35,
            "summary": "Evaluation fallback triggered.",
            "rubric_items": [
                {"criterion": "Core Concept Depth", "passed": bool(is_pass), "note": "Assessed via fallback"},
                {"criterion": "Practical Implementation", "passed": bool(is_pass), "note": "Assessed via fallback"},
                {"criterion": "Trade-off Awareness", "passed": False, "note": "Pending deeper exploration"}
            ],
            "recommended_probe": "Explore specific trade-offs."
        }
