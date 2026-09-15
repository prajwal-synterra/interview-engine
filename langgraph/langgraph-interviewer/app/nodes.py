"""
Nodes — Module 3-6

Pattern every node follows:
    receive state  ->  do work  ->  return partial dict

LangGraph merges the partial dict back into the full state.
Nodes never return the full state; only the fields they changed.
"""

from pydantic import BaseModel, field_validator
from app.state import InterviewState
from app.llm import get_llm

# ── Shared display helpers ─────────────────────────────────────────────────
DIV  = "=" * 62
LINE = "-" * 62

def _section(title: str):
    print(f"\n{DIV}\n  {title}\n{DIV}")

def _row(label: str, value):
    print(f"  {label:<14}: {value}")

llm = get_llm()

# ── Pydantic schema for structured evaluation output ───────────────────────
# llm.with_structured_output(Evaluation) forces Gemini to return this exact
# shape. field_validator clamps score to 0-10 (Gemini sometimes returns 35!).
class Evaluation(BaseModel):
    score:      int   # 0-10
    strengths:  str   # what the candidate got right
    weaknesses: str   # what was missing or wrong
    feedback:   str   # overall coaching advice

    @field_validator("score")
    @classmethod
    def clamp_score(cls, v: int) -> int:
        return max(0, min(10, int(v)))


# ── Difficulty ladder ──────────────────────────────────────────────────────
LEVELS = ["easy", "medium", "hard"]

def _next_difficulty(current: str, score: int) -> str:
    """Increase difficulty on good score, decrease on poor score."""
    idx = LEVELS.index(current)
    if score >= 7:
        return LEVELS[min(idx + 1, 2)]   # cap at "hard"
    else:
        return LEVELS[max(idx - 1, 0)]   # floor at "easy"


# ── Node 1: Generate Question (Modules 4 + 8) ─────────────────────────────
def generate_question(state: InterviewState) -> dict:
    q_num    = state["question_number"]
    prev_score = state["score"]
    current_diff = state.get("difficulty", "easy")

    # First question is always easy; after that adapt
    if q_num == 0:
        difficulty = "easy"
    else:
        difficulty = _next_difficulty(current_diff, prev_score)

    _section(f"GRAPH  |  Node: generate_question")
    _row("Difficulty", difficulty.upper())
    _row("Round", f"{q_num + 1} / 5")
    _row("API call", "llm.invoke(Java question prompt)")
    print(f"  Waiting for Gemini...")

    response = llm.invoke(
        f"Generate one {difficulty} Java interview question. "
        f"Return ONLY the question text, no explanation, no numbering."
    )

    _row("Status", "Question received")

    return {
        "question":        response.content.strip(),
        "difficulty":      difficulty,
        "question_number": q_num + 1,
        "answer":          "",
        "score":           0,
        "feedback":        "",
    }


# ── Node 2: Get User Answer (Module 5) ────────────────────────────────────
def get_answer(state: InterviewState) -> dict:
    _section(f"QUESTION {state['question_number']}  |  Difficulty: {state['difficulty'].upper()}")
    print(f"  {state['question']}")
    print(f"\n{LINE}")
    answer = input("  Your answer: ").strip()
    print(LINE)
    return {"answer": answer}


# ── Node 3: Evaluate Answer (Module 6) ────────────────────────────────────
def evaluate_answer(state: InterviewState) -> dict:
    _section("GRAPH  |  Node: evaluate_answer")
    _row("API call", "llm.with_structured_output(Evaluation)")
    _row("Input",    "question + answer -> Gemini")
    print(f"  Evaluating... please wait.")

    structured_llm = llm.with_structured_output(Evaluation)
    prompt = f"""
You are a strict but fair Java technical interviewer.

Question asked:
{state['question']}

Candidate's answer:
{state['answer']}

Evaluate the answer objectively. Score must be between 0 and 10.
"""
    result: Evaluation = structured_llm.invoke(prompt)

    questions = list(state.get("questions", []))
    answers   = list(state.get("answers",   []))
    scores    = list(state.get("scores",    []))
    feedbacks = list(state.get("feedbacks", []))

    questions.append(state["question"])
    answers.append(state["answer"])
    scores.append(result.score)
    feedbacks.append(result.feedback)

    # ── Clean evaluation display ───────────────────────────────────────────
    score_bar = ("[" + "#" * result.score + "." * (10 - result.score) + "]")
    _section(f"EVALUATION  |  Round {state['question_number']}")
    _row("Score",      f"{result.score}/10  {score_bar}")
    _row("Strengths",  result.strengths)
    _row("Weaknesses", result.weaknesses)
    _row("Feedback",   result.feedback)

    # ── State snapshot ─────────────────────────────────────────────────────
    all_scores = scores
    avg = sum(all_scores) / len(all_scores)
    _section("STATE SNAPSHOT  |  After this round")
    _row("question_number", state['question_number'])
    _row("difficulty",      state['difficulty'].upper())
    _row("scores so far",   f"{all_scores}  avg={avg:.1f}/10")
    next_diff = _next_difficulty(state['difficulty'], result.score)
    _row("next difficulty", next_diff.upper() + (" (up)" if next_diff != state['difficulty'] and LEVELS.index(next_diff) > LEVELS.index(state['difficulty']) else " (down)" if next_diff != state['difficulty'] else " (same)"))

    return {
        "score":     result.score,
        "feedback":  result.feedback,
        "questions": questions,
        "answers":   answers,
        "scores":    scores,
        "feedbacks": feedbacks,
    }


# ── Node 4: Final Report (Module 10) ──────────────────────────────────────
def generate_final_report(state: InterviewState) -> dict:
    _section("GRAPH  |  Node: generate_final_report")
    _row("API call", "llm.invoke(full history prompt)")
    _row("Input",    f"{len(state['questions'])} Q&A pairs + scores")
    print("  Generating your interview report... please wait.")

    avg_score = sum(state["scores"]) / len(state["scores"])

    history_block = ""
    for i, (q, a, s, f) in enumerate(zip(
        state["questions"], state["answers"],
        state["scores"],    state["feedbacks"],
    ), start=1):
        history_block += (
            f"\nQ{i}: {q}\n"
            f"Answer: {a}\n"
            f"Score: {s}/10\n"
            f"Feedback: {f}\n"
        )

    prompt = f"""
You are writing a professional interview debrief report.

Here is the complete Java interview session:
{history_block}

Average Score: {avg_score:.1f}/10

Write a concise INTERVIEW REPORT with these four sections:
1. Overall Score
2. Key Strengths
3. Key Weaknesses
4. Recommended Topics to Study
"""
    response = llm.invoke(prompt)
    return {"final_report": response.content}
