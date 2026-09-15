from typing import TypedDict, List


class InterviewState(TypedDict):
    # ── Current round ─────────────────────────────────────────────────────
    question:        str    # The question Gemini generated
    answer:          str    # The candidate's typed answer
    score:           int    # Score 0-10 from Gemini evaluation
    feedback:        str    # Feedback string from Gemini
    difficulty:      str    # "easy" | "medium" | "hard"
    question_number: int    # How many questions completed so far (0 = not started)

    # ── Accumulated history (grows each round) ────────────────────────────
    questions:  List[str]   # All questions asked
    answers:    List[str]   # All answers given
    scores:     List[int]   # All scores received
    feedbacks:  List[str]   # All feedbacks received

    # ── Final output ──────────────────────────────────────────────────────
    final_report: str       # Gemini-generated interview report
