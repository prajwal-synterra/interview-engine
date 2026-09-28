"""
Gemini Service Layer (v2: Resilient Models, Conversational Persona & Diversity)
Handles Rubric-Lock generation, combined grading + skill scanning,
candidate name detection, and non-repeating conversational questions.
"""

import os
import time
from typing import Optional, List, Tuple
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

MODELS_TO_TRY = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
]


def call_gemini_with_retry(prompt: str, schema, temperature: float = 0.2, max_retries: int = 4):
    """
    Calls Gemini using high-quota models with automatic fallback.
    Extracts native token usage metadata on every call.
    Returns: (response_text, prompt_tokens, completion_tokens)
    """
    last_err = None

    for attempt in range(max_retries):
        model = MODELS_TO_TRY[attempt % len(MODELS_TO_TRY)]
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
            
            prompt_tokens = 0
            completion_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
                completion_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

            return response, prompt_tokens, completion_tokens
        except Exception as e:
            last_err = e
            print(f"[Retry {attempt+1}/{max_retries}] Spike on {model}: {e}. Falling back...")
            time.sleep(0.5)

    raise last_err


def extract_skills_from_intro(candidate_intro: str) -> Tuple[List[str], Optional[str], int, int]:
    """
    Parses candidate self-introduction into:
    1. Candidate's first name (if mentioned, e.g. 'Prajwal', 'Alex').
    2. A structured queue of 2 to 4 concrete skills.
    Returns: (skills_list, candidate_name, prompt_tokens, completion_tokens)
    """
    prompt = f"""
You are an expert, friendly technical interviewer analyzing a candidate's self-introduction.
Candidate Introduction:
"{candidate_intro}"

Your tasks:
1. Candidate Name: If the candidate explicitly mentions their first name or full name (e.g., "I'm Prajwal", "My name is Alex", "Hi, I am Sarah"), extract their first name into 'candidate_name'. If they did not mention their name, set 'candidate_name' to null.
2. Skill Extraction: Extract the primary technical skills, frameworks, databases, or languages explicitly mentioned by the candidate that are suitable for deep technical interview assessment (e.g., 'FastAPI', 'PostgreSQL', 'Docker', 'Redis', 'Python', 'Kubernetes', 'HTML', 'React').

Rules:
- Return between 2 and 4 skills.
- Normalize names into standard industry casing (e.g., 'FastAPI', 'PostgreSQL', 'Docker', 'Node.js', 'Python').
- If the candidate mentioned fewer than 2 concrete skills or gave a vague introduction, include foundational skills that align with what they mentioned, or default to ['Python', 'System Architecture'].

Return strictly structured as ExtractedSkills.
"""
    try:
        response, p_tokens, c_tokens = call_gemini_with_retry(prompt, ExtractedSkills, temperature=0.1)
        data = ExtractedSkills.model_validate_json(response.text)
        cleaned = []
        for s in data.skills:
            s_clean = s.strip()
            if s_clean and s_clean.lower() not in [x.lower() for x in cleaned]:
                cleaned.append(s_clean)
        
        name = data.candidate_name.strip() if data.candidate_name else None
        return (cleaned if cleaned else ["Python", "FastAPI"]), name, p_tokens, c_tokens
    except Exception as e:
        print(f"[Skill Extraction Error]: {e}")
        return ["Python", "FastAPI"], None, 0, 0


def generate_question_and_rubric(
    skill: str, 
    depth_level: str,
    previous_questions: Optional[List[str]] = None,
    candidate_name: Optional[str] = None,
    previous_context: Optional[str] = None,
) -> Tuple[LockedRubric, int, int]:
    """
    Generates technical interview question and locks evaluation rubric BEFORE candidate sees question.
    Ensures natural, encouraging interviewer persona, and strictly prevents repeating questions/topics or repetitive greetings.
    Returns: (LockedRubric, prompt_tokens, completion_tokens)
    """
    depth_guidelines = {
        "L1": "Foundational: Core mental models, basic definitions, common use cases, and essential syntax.",
        "L2": "Implementation: Internal mechanics, standard APIs, lifecycle, data flow, and idiomatic patterns.",
        "L3": "Architectural: Concurrency, scalability, distributed patterns, state management, and system trade-offs.",
        "L4": "Production Trade-offs: Edge-case resilience, failure recovery, bottlenecks, and performance under load.",
    }

    guidance = depth_guidelines.get(depth_level, depth_guidelines["L1"])

    avoid_block = ""
    if previous_questions:
        formatted_prev = "\n".join([f"- \"{q}\"" for q in previous_questions[-4:] if q])
        if formatted_prev:
            avoid_block = f"""
STRICT TOPIC DIVERSITY RULE (NO REPEATS):
The following questions/topics have ALREADY been asked previously in this interview:
{formatted_prev}
Do NOT repeat any of these questions, and do NOT re-test the same subtopic!
You MUST switch to a completely different subtopic or core concept of {skill}.
For example:
- In Python: If list vs tuple was asked, switch to dictionaries/sets, generators/yield, decorators, list comprehensions, exception handling, or variable scope (LEGB).
- In HTML: If semantic tags was asked, switch to forms/validation, accessibility (ARIA), DOM events, or meta tags/SEO.
"""

    if previous_questions:
        greeting_instruction = (
            f"STRICT NAME RULE: DO NOT start with 'Hey {candidate_name}' or repeat their name. "
            "Real interviewers do not say the candidate's name on every turn. "
            "Instead, start directly with a natural conversational bridge (e.g. 'Building on that...', "
            "'Makes sense. Let\\'s explore...', 'Now, what if we look at...')."
            if candidate_name else
            "Start directly with a natural conversational bridge (e.g. 'Building on that...', 'Makes sense. Now let\\'s explore...')."
        )
    else:
        greeting_instruction = (
            f"This is the opening question of the assessment. Greet the candidate warmly once (e.g. 'Hey {candidate_name}! Great to meet you.')."
            if candidate_name else
            "This is the opening question of the assessment. Greet the candidate in a warm, welcoming manner."
        )

    context_bridge = ""
    if previous_context:
        context_bridge = f"""
Candidate's previous response for context:
"{previous_context[:350]}"
Use this to smoothly bridge into the next topic (e.g., 'Building on how you handled indexing there...').
"""

    prompt = f"""
You are a warm, encouraging Senior Engineering Interviewer conducting an adaptive technical conversation.
Candidate: {candidate_name or 'the candidate'}
Skill: {skill}
Target Depth: {depth_level} ({guidance})
{avoid_block}
{context_bridge}
INTERVIEWER PERSONA & TONE GUIDELINES:
1. Natural & Conversational: Sound like a friendly, supportive senior engineer pair-programming or having an insightful coffee chat with the candidate. Avoid dry, robotic, exam-style phrasing like "Define X and write code for Y".
2. Confidence-Building: Frame the question with a brief, relatable engineering scenario (e.g. "In day-to-day work with {skill}...", "When you're building a feature where...", "Many engineers run into..."). Put the candidate at ease and encourage them to share their mental model and practical experience.
3. Engaging Question: {greeting_instruction} Ask ONE focused, approachable question suited for {depth_level}. Invite them to explain their thoughts or share a quick example in their own words.
4. Rubric Criteria: Provide 2 concise 'required_criteria' representing the fundamental mechanical understanding (focus on practical concepts, not nitpicky syntax).
5. Prohibited Misconceptions: Provide 1-2 common misconceptions or buzzword bluffs that would indicate a shallow understanding.

Return the result strictly structured as a LockedRubric.
"""
    response, p_tokens, c_tokens = call_gemini_with_retry(prompt, LockedRubric, temperature=0.5)
    rubric_data = LockedRubric.model_validate_json(response.text)
    rubric_data.skill_name = skill
    rubric_data.depth_level = depth_level
    rubric_data.is_devils_advocate = False
    return rubric_data, p_tokens, c_tokens


def generate_devils_advocate_question(
    skill: str, 
    depth_level: str, 
    previous_context: str,
    candidate_name: Optional[str] = None
) -> Tuple[LockedRubric, int, int]:
    """
    Generates an adversarial Devil's Advocate trade-off cross-examination with conversational tone.
    Returns: (LockedRubric, prompt_tokens, completion_tokens)
    """
    name_clause = (
        f"You may address {candidate_name} respectfully (e.g. 'Now {candidate_name}, let\\'s stress-test that...'), but avoid repetitive greetings."
        if candidate_name else "Address the candidate in a respectful, collegial tone."
    )
    prompt = f"""
You are a thoughtful Principal Systems Architect conducting a Devil's Advocate cross-examination in an interview.
Skill: {skill} (Depth: {depth_level})
Previous Candidate Claims: "{previous_context}"

Task:
1. {name_clause} Challenge the candidate's proposed design or assumption in a polite, engaging, but rigorous architectural way.
2. Present a realistic production trade-off or failure scenario (e.g., memory overhead, high concurrency bottlenecks, data race, latency spike, or network partition).
3. Ask how they would handle or mitigate this trade-off.
4. Define 2 required criteria that show true engineering maturity and trade-off defense.
5. Define 1-2 prohibited shallow answers or hand-waving responses.

Return the result strictly structured as a LockedRubric with is_devils_advocate=True.
"""
    response, p_tokens, c_tokens = call_gemini_with_retry(prompt, LockedRubric, temperature=0.5)
    rubric_data = LockedRubric.model_validate_json(response.text)
    rubric_data.skill_name = skill
    rubric_data.depth_level = depth_level
    rubric_data.is_devils_advocate = True
    return rubric_data, p_tokens, c_tokens


def grade_and_detect_skills(rubric: LockedRubric, candidate_answer: str) -> Tuple[GradingResult, int, int]:
    """
    COMBINED EVALUATION (50% Cost Cut):
    Grades the candidate's answer against the frozen rubric criteria AND extracts
    any unprompted external tools/systems mentioned in passing in ONE single LLM call.
    Returns: (GradingResult, prompt_tokens, completion_tokens)
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
2. Issue verdict: 'partial' if the candidate demonstrates genuine understanding of the primary concept, but missed a secondary nuance (with no fatal misconceptions).
3. Issue verdict: 'incorrect' ONLY if the candidate fundamentally misses the core mechanism, repeats criteria word-for-word without real explanation, makes false claims, repeats prohibited misconceptions, or gives a superficial non-answer.
4. In 'mentioned_technologies': Identify ONLY distinct, standalone external technologies, databases, message brokers, caching layers, or cloud infrastructure explicitly mentioned (e.g., 'Kafka', 'Redis', 'PostgreSQL', 'Docker', 'Kubernetes', 'RabbitMQ', 'Celery').
STRICT NEGATIVE CONSTRAINTS:
- Do NOT extract internal submodules, functions, methods, classes, or serialization formats of libraries (e.g. NEVER extract 'tf.saved_model', 'torch.nn', 'os.path', 'numpy.array', 'DataFrame', 'asyncio.gather', 'FastAPI Depends').
- Do NOT extract any term containing a period '.' or syntax symbols.
- Do NOT extract sub-components or aliases of the active skill '{rubric.skill_name}' (e.g., if active skill is TensorFlow, do NOT extract 'tf.saved_model', 'TFS', 'TensorFlow Serving', 'Keras', 'TFLite').
- If no truly distinct, standalone external technologies are mentioned, return an empty list []

Return strictly structured as GradingResult.
"""
    response, p_tokens, c_tokens = call_gemini_with_retry(prompt, GradingResult, temperature=0.0)
    return GradingResult.model_validate_json(response.text), p_tokens, c_tokens


def generate_spot_check_question(
    skill: str, 
    previous_context: str,
    candidate_name: Optional[str] = None
) -> Tuple[LockedRubric, int, int]:
    """
    Generates a single, high-leverage architectural spot-check question
    to verify if the candidate genuinely worked with an unlisted technology.
    Returns: (LockedRubric, prompt_tokens, completion_tokens)
    """
    name_clause = f"Address {candidate_name} naturally." if candidate_name else ""
    prompt = f"""
You are an engineering interviewer conducting a concise 1-question spot-check verification.
The candidate casually referenced hands-on experience with: '{skill}'.
Context from candidate: "{previous_context}"

Task:
1. {name_clause} Formulate ONE direct, conversational architectural question testing concrete production experience with {skill} (e.g. partition keys, connection pool exhaustion, memory boundaries, failure recovery, cache invalidation).
2. Formulate 2 required criteria that prove genuine hands-on experience (not generic tutorial knowledge).
3. Formulate 1-2 prohibited misconceptions or superficial buzzwords.

Return the result strictly structured as a LockedRubric.
"""
    response, p_tokens, c_tokens = call_gemini_with_retry(prompt, LockedRubric, temperature=0.3)
    rubric_data = LockedRubric.model_validate_json(response.text)
    rubric_data.skill_name = skill
    rubric_data.depth_level = "Spot-Check"
    return rubric_data, p_tokens, c_tokens

