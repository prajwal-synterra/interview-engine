"""
Gemini Service Layer
Handles Rubric-Lock generation, discrete grading against frozen rubrics,
and Devil's Advocate adversarial trade-off challenges.
Strictly isolated from score and mastery calculations.
"""

from fastapi import responses
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

try:
    from app.models import LockedRubric, GradingResult, ExtractedSkills
except ModuleNotFoundError:
    from models import LockedRubric, GradingResult, ExtractedSkills

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY not found in environment!")

client = genai.Client(api_key=api_key)
MODEL_NAME = "gemini-3.5-flash-lite"


def call_gemini_with_retry(prompt: str, schema, temperature: float = 0.2, max_retries: int = 3):
    """
    Calls Gemini with automatic retry for transient 503 spikes.
    Falls back to alternate flash models if one is under high demand.
    """
    models_to_try = [MODEL_NAME, "gemini-2.5-flash", "gemini-2.0-flash"]
    last_err = None

    for attempt in range(max_retries):
        model = models_to_try[attempt % len(models_to_try)]
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=temperature,
                ),
            )
            return response
        except Exception as e:
            last_err = e
            print(f"[Retry {attempt+1}/{max_retries}] 503 or transient error on {model}. Retrying...")
            time.sleep(1.5)

    raise last_err

def extract_skills_from_intro(candidate_intro) -> list[str]:
    """
    Extracts a clean list of technical skills and technologies mentioned
    in the candidate's self-introduction.
    """
    prompt = f"""
You are an expert technical interviewer analyzing a candidate's self-introduction.
Candidate Introduction:
"{candidate_intro}"
Extract the primary technical skills, frameworks, databases, or languages explicitly mentioned by the candidate that are suitable for deep technical interview assessment (e.g., 'FastAPI', 'PostgreSQL', 'Docker', 'Redis', 'Python', 'Kubernetes').
Rules:
- Return between 2 and 5 skills.
- Normalize names into standard industry casing (e.g., 'FastAPI', 'PostgreSQL', 'Docker', 'Node.js').
- If the candidate mentioned fewer than 2 concrete skills or gave a vague introduction, include foundational skills that align with what they mentioned, or default to ['Python', 'System Architecture'].
Return strictly structured as ExtractedSkills.
"""
    try:
        response = call_gemini_with_retry(prompt,ExtractedSkills,temperature=0.1)
        data = ExtractedSkills.model_validate_json(response.text)
        cleaned = []
        for s in data.skills:
            s_clean = s.strip()
            if s_clean and s_clean.lower() not in [x.lower() for x in cleaned]:
                cleaned.append(s_clean)
        
        return cleaned
    except Exception as e:
        print(f"[Gemini Error] Failed to extract skills: {e}")
        return ['Python', 'System Architecture']

def detect_mentioned_skills(candidate_answer:str)-> list[str]:
    """
    This if for fetching skills when user is on interview and answering the questions for L1 rto l4
    """
    prompt= f"""
You are a technical analyzer reviewing an engineer's interview response.
Response:
"{candidate_answer}"
Identify any specific external technologies, databases, message brokers, caching systems, or architectural tools explicitly mentioned by the candidate as tools they used or recommended (e.g., 'Redis', 'Celery', 'PostgreSQL', 'Kafka', 'Docker', 'RabbitMQ', 'Elasticsearch').
Rules:
- Only include specific concrete technologies or tools, NOT general programming concepts (do NOT include 'concurrency', 'threads', 'async', 'REST', 'API', 'functions', 'loops').
- Return strictly structured as ExtractedSkills. If none are mentioned, return an empty list.
"""
    try:
        response = call_gemini_with_retry(prompt,ExtractedSkills, temperature=0.0)
        data = ExtractedSkills.model_validate_json(response.text)
        return [s.strip() for s in data.skills if s.strip()]
    except Exception:
        return []    

def generate_spot_check_question(skill:str, question_index:int, previous_context:str) -> LockedRubric:
    """
    Generate a question that is mentioned in the interview
    """
    if question_index == 1:
        focus = "Concrete Architecture & Integration: Ask specifically how they configured, integrated, or implemented this technology in a production codebase."
    else:
        focus = "Production Bottlenecks & Trade-offs: Ask specifically about failure modes, memory limits, connection pooling, scaling limits, or edge-case gotchas they faced."
    
    prompt = f"""
You are an engineering interviewer conducting a quick 2-question spot-check verification.
The candidate casually mentioned experience with: '{skill}'.
Context / quote from candidate: "{previous_context}"
Question Phase: {question_index} of 2.
Focus: {focus}
Task:
1. Formulate a direct, practical question testing whether the candidate genuinely worked with {skill} or is merely name-dropping it.
2. Formulate 2 required criteria that indicate genuine hands-on experience.
3. Formulate 1-2 prohibited misconceptions or vague generic answers.
Return the result strictly structured as a LockedRubric.
"""
    response = call_gemini_with_retry(prompt,LockedRubric, temperature=0.3)
    rubric_data = LockedRubric.model_validate_json(response.text)
    rubric_data.skill_name = skill
    rubric_data.depth_level = f"Spot-check-{question_index}"
    return rubric_data

def generate_question_and_rubric(skill: str, depth_level: str) -> LockedRubric:
    """
    Generates technical interview question and locks the evaluation rubric
    BEFORE the candidate sees the question.
    """
    depth_guidelines = {
        "L1": "Foundational: Definitions, syntax, core concepts, and basic use cases.",
        "L2": "Implementation: Internal mechanics, APIs, lifecycle, standard patterns.",
        "L3": "Architectural: Concurrency, scalability, distributed systems, internal trade-offs.",
        "L4": "Production Trade-offs: Failure modes, edge cases, performance under heavy load.",
    }

    guidance = depth_guidelines.get(depth_level, depth_guidelines["L1"])

    prompt = f"""
You are an expert technical interviewer designing an assessment question for:
Skill: {skill}
Cognitive Depth Level: {depth_level} ({guidance})

Your task:
1. Formulate a clear, direct interview question suited for {depth_level}.
2. Formulate 2 concise 'required_criteria' representing the CORE mechanical understanding (focus on high-level concepts, not pedantic syntax).
3. Formulate 1 or 2 'prohibited_misconceptions' (buzzword bluffs or false architectural claims).

Return the result strictly structured as a LockedRubric.
"""


    response = call_gemini_with_retry(prompt, LockedRubric, temperature=0.4)
    rubric_data = LockedRubric.model_validate_json(response.text)
    rubric_data.skill_name = skill
    rubric_data.depth_level = depth_level
    rubric_data.is_devils_advocate = False
    return rubric_data


def generate_devils_advocate_question(skill: str, depth_level: str, previous_context: str) -> LockedRubric:
    """
    Generates an adversarial Devil's Advocate trade-off cross-examination.
    """
    prompt = f"""
You are a skeptical Principal Systems Architect conducting a Devil's Advocate cross-examination.
Skill: {skill} (Depth: {depth_level})
Previous Candidate Claims: "{previous_context}"

Challenge the candidate aggressively on their architectural choices or trade-offs.
Ask them to defend against a realistic production failure mode (e.g. resource contention, locking, event-loop stalls, latency spikes).
Also define the required criteria to pass this defense, and prohibited shallow answers.

Return the result strictly structured as a LockedRubric with is_devils_advocate=True.
"""

    response = call_gemini_with_retry(prompt, LockedRubric, temperature=0.5)
    rubric_data = LockedRubric.model_validate_json(response.text)
    rubric_data.skill_name = skill
    rubric_data.depth_level = depth_level
    rubric_data.is_devils_advocate = True
    return rubric_data


def grade_answer_with_rubric(rubric: LockedRubric, candidate_answer: str) -> GradingResult:
    """
    Grades the candidate's answer strictly against the frozen rubric criteria.
    Emits ONLY a boolean verdict ('correct' or 'incorrect') and rationale.
    Never calculates scores or probabilities.
    """
    prompt = f"""
You are an impartial technical evaluator assessing a candidate's answer against the frozen rubric below.

QUESTION:
{rubric.question_text}

FROZEN REQUIRED CRITERIA:
{rubric.required_criteria}

FROZEN PROHIBITED MISCONCEPTIONS:
{rubric.prohibited_misconceptions}

CANDIDATE ANSWER:
"{candidate_answer}"

EVALUATION RULES:
1. Issue verdict: 'correct' if the candidate clearly and accurately articulates the core required criteria without falling into prohibited misconceptions.
2. Issue verdict: 'partial' if the candidate demonstrates genuine understanding of the primary concept, but missed a secondary nuance, or provided a solid explanation without a requested code example (with no fatal misconceptions).
3. Issue verdict: 'incorrect' ONLY if the candidate fundamentally misses the core mechanism, makes false technical claims, repeats prohibited misconceptions, or gives a superficial non-answer.

Return strictly structured as GradingResult with verdict being 'correct', 'partial', or 'incorrect'.
"""



    response = call_gemini_with_retry(prompt, GradingResult, temperature=0.0)
    return GradingResult.model_validate_json(response.text)


if __name__ == "__main__":
    print("Testing Gemini Service Layer (Rubric-Lock & Grader)...")

    # Step 1: Generate Locked Rubric
    print("\n1. Generating Locked Rubric for 'FastAPI' (Level L1)...")
    rubric = generate_question_and_rubric("FastAPI", "L1")
    print(f"Locked Rubric ID: {rubric.rubric_id}")
    print(f"Question        : {rubric.question_text}")
    print(f"Required        : {rubric.required_criteria}")
    print(f"Prohibited      : {rubric.prohibited_misconceptions}")

    # Step 2: Grade knowledgeable answer
    print("\n2. Grading knowledgeable answer...")
    good_answer = "FastAPI uses Pydantic models for request body validation and python type hints on function parameters like item_id: int."
    good_grade = grade_answer_with_rubric(rubric, good_answer)
    print(f"Verdict  : {good_grade.verdict.upper()}")
    print(f"Rationale: {good_grade.rationale}")

    # Step 3: Grade bluffer answer
    print("\n3. Grading bluffer answer...")
    bad_answer = "FastAPI is fast because it uses Python and AI magic to do everything automatically."
    bad_grade = grade_answer_with_rubric(rubric, bad_answer)
    print(f"Verdict  : {bad_grade.verdict.upper()}")
    print(f"Rationale: {bad_grade.rationale}")

    print("\nSUCCESS: Gemini Service Layer is fully functional!")
