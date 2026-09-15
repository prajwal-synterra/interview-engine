"""
Module 2 - LangGraph State

Concept: State is the shared memory of the entire graph.
Every node reads from it and writes back to it.

Flow:
  EMPTY STATE
      |
      v
  [Node fills question]
      |
      v
  [Node fills answer + score + feedback]
      |
      v
  FINAL STATE
"""

from app.state import InterviewState

# ── Helper to print state clearly ──────────────────────────────────────────
def print_state(label: str, state: InterviewState):
    print(f"\n{'='*50}")
    print(f"  STATE: {label}")
    print(f"{'='*50}")
    print(f"  question : {state['question'] or '(empty)'}")
    print(f"  answer   : {state['answer']   or '(empty)'}")
    print(f"  score    : {state['score']}")
    print(f"  feedback : {state['feedback'] or '(empty)'}")
    print(f"{'='*50}")

# ── STEP 1: Create the initial (empty) state ───────────────────────────────
print("\n[STEP 1] Creating initial empty state...")

state: InterviewState = {
    "question": "",
    "answer":   "",
    "score":    0,
    "feedback": "",
}

print_state("INITIAL (before any node runs)", state)

# ── STEP 2: Simulate Node 1 — Interviewer asks a question ─────────────────
print("\n[STEP 2] Node 1 runs -> fills in the 'question' field...")

state["question"] = "What is polymorphism in Java?"

print_state("AFTER Node 1 (question added)", state)

# -- STEP 3: Simulate Node 2 -- Candidate answers ───────────────────────────
print("\n[STEP 3] Node 2 runs -> fills in 'answer', 'score', 'feedback'...")

state["answer"]   = "Polymorphism lets one interface represent different types."
state["score"]    = 8
state["feedback"] = "Good explanation. Could also mention method overriding vs overloading."

print_state("AFTER Node 2 (answer + feedback + score)", state)

# -- SUMMARY ────────────────────────────────────────────────────────────────
print("\n[DONE] Key concept:")
print("  -> State is a Python dict that flows through every node.")
print("  -> Each node reads what it needs and writes its result back.")
print("  -> No node talks to another directly -- State is the messenger.")
