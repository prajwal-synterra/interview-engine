"""
test_graph.py -- Run the full interview session (Modules 4-10)

The graph handles everything automatically:
  START -> generate_question -> get_answer -> evaluate_answer
        -> [loop or final_report] -> END

After each round you will see:
  GRAPH node  |  what API was called
  QUESTION    |  the question + your input
  EVALUATION  |  score bar, strengths, weaknesses, feedback
  STATE       |  live snapshot of the state dict
"""

from dotenv import load_dotenv
from app.graph import build_graph
from app.state import InterviewState
from app.nodes import DIV

load_dotenv()

graph = build_graph()

initial_state: InterviewState = {
    "question":        "",
    "answer":          "",
    "score":           0,
    "feedback":        "",
    "strengths":       "",
    "weaknesses":      "",
    "difficulty":      "easy",
    "question_number": 0,
    "questions":       [],
    "answers":         [],
    "scores":          [],
    "feedbacks":       [],
    "final_report":    "",
}

print(f"\n{DIV}")
print("  AI INTERVIEWER  |  5 Questions  |  Adaptive Difficulty")
print(f"{DIV}")
print("  The LangGraph will drive everything from here.")
print("  Type your answer when prompted.")
print(f"{DIV}")

final_state = graph.invoke(initial_state)

# Final report
print(f"\n{DIV}")
print("  FINAL INTERVIEW REPORT")
print(f"{DIV}")
print(final_state["final_report"])
print(f"{DIV}\n")
