"""
Graph — Modules 4, 7, 9

Wires all nodes into a compiled LangGraph.

Flow:
    START
      |
      v
    generate_question  <--------------+
      |                               |
      v                               | question_number < MAX_QUESTIONS
    get_answer                        |
      |                               |
      v                               |
    evaluate_answer -------------------+
      |
      | question_number >= MAX_QUESTIONS
      v
    generate_final_report
      |
      v
    END
"""

from langgraph.graph import StateGraph, START, END
from app.state import InterviewState
from app.nodes import (
    generate_question,
    get_answer,
    evaluate_answer,
    generate_final_report,
)

MAX_QUESTIONS = 5   # Change this to run more or fewer rounds


# ── Routing function (Module 7 — Conditional Edges) ───────────────────────
def route_after_evaluation(state: InterviewState) -> str:
    """
    After evaluating an answer, decide what happens next.

    question_number >= MAX_QUESTIONS  ->  go to final report
    question_number <  MAX_QUESTIONS  ->  loop back for next question
    """
    if state["question_number"] >= MAX_QUESTIONS:
        return "final_report"
    return "generate_question"


# ── Build and compile the graph ────────────────────────────────────────────
def build_graph():
    builder = StateGraph(InterviewState)

    # Register nodes
    builder.add_node("generate_question",    generate_question)
    builder.add_node("get_answer",           get_answer)
    builder.add_node("evaluate_answer",      evaluate_answer)
    builder.add_node("final_report",         generate_final_report)

    # Fixed edges
    builder.add_edge(START,               "generate_question")
    builder.add_edge("generate_question", "get_answer")
    builder.add_edge("get_answer",        "evaluate_answer")

    # Conditional edge — the routing function decides the next node
    builder.add_conditional_edges(
        "evaluate_answer",          # source node
        route_after_evaluation,     # function that returns a node name
        {
            "generate_question": "generate_question",   # loop
            "final_report":      "final_report",        # exit
        },
    )

    builder.add_edge("final_report", END)

    return builder.compile()
