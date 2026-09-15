"""
Module 3 - Interactive node test

Loop:
  1. generate_question node  -> Gemini gives a Java question
  2. You type your answer
  3. State is shown (before and after)
  4. Repeat until you type 'exit'
"""

from app.state import InterviewState
from app.nodes import generate_question

# ── Helper: print current state cleanly ───────────────────────────────────
def print_state(label: str, state: InterviewState):
    print("\n" + "=" * 52)
    print(f"  STATE SNAPSHOT: {label}")
    print("=" * 52)
    print(f"  question : {state['question'] or '(empty)'}")
    print(f"  answer   : {state['answer']   or '(empty)'}")
    print(f"  score    : {state['score']}")
    print(f"  feedback : {state['feedback'] or '(empty)'}")
    print("=" * 52)

# ── Start with empty state ─────────────────────────────────────────────────
state: InterviewState = {
    "question": "",
    "answer":   "",
    "score":    0,
    "feedback": "",
}

round_num = 0

print("\n" + "#" * 52)
print("  Java Interview Session  (type 'exit' to quit)")
print("#" * 52)
print_state("INITIAL", state)

# ── Loop ──────────────────────────────────────────────────────────────────
while True:
    round_num += 1
    print(f"\n--- Round {round_num} ---")

    # STEP A: Node runs -> generates question -> updates state
    updates = generate_question(state)
    state.update(updates)                  # merge node output into state

    print_state(f"AFTER generate_question (Round {round_num})", state)

    # STEP B: Show the question, get user input
    print(f"\n  QUESTION: {state['question']}")
    print()
    user_input = input("  Your answer (or 'exit'): ").strip()

    if user_input.lower() == "exit":
        print("\n  Session ended. Goodbye!")
        break

    # STEP C: Store answer in state
    state["answer"] = user_input

    print_state(f"AFTER your answer (Round {round_num})", state)

    # Reset for next round (keeps showing the pattern clearly)
    state["answer"]   = ""
    state["score"]    = 0
    state["feedback"] = ""
