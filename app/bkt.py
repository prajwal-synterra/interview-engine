"""
Bayesian Knowledge Tracing (BKT) Mathematical Engine
Reference: Corbett & Anderson (1994) / AIS-ARCH-2026-V1
Strictly isolated from LLM and natural language logic.
"""
from dataclasses import dataclass
from typing import Dict, Literal, Tuple


Verdict = Literal["correct","incorrect"]

@dataclass(frozen=True)
class DepthParams:
    guess:float # P(G): Probability unknowledgeable candidate answers correctly
    slip: float # P(S): Probability knowledgeable candidate answers incorrectly
    learn: float # P(L): Probability of learning (transitioning from unknowledgeable to knowledgeable)
    #forget:float = 0.0 # P(F): Probability of forgetting (transitioning from knowledgeable to unknowledgeable)

DEPTH_LEVEL_PARAMS: Dict[str,DepthParams] = {
    "L1": DepthParams(guess=0.30,slip=0.05,learn=0.05),
    "L2":DepthParams(guess=0.20,slip=0.10,learn=0.05),
    "L3": DepthParams(guess=0.10,slip=0.15,learn=0.05),
    "L4": DepthParams(guess=0.05,slip=0.20,learn=0.05)
}

DEFAULT_PRIOR = 0.30

def update_mastery(
    prior: float,
    verdict: Verdict,
    depth_level: str
) -> Tuple[float, float]:
    """
    Executes the two-step Bayesian Knowledge Tracing update:
      Step 1: Bayesian Posterior Update: P(L_t | obs)
      Step 2: Latent Learning Transition: P(L_{t+1})
    Args:
        prior: Previous mastery probability P(L_{t-1})
        verdict: 'correct' or 'incorrect'
        depth_level: 'L1', 'L2', 'L3', or 'L4'
    Returns:
        (posterior_belief, next_mastery) both rounded to 4 decimals
"""
    if depth_level not in DEPTH_LEVEL_PARAMS:
        raise ValueError(f"Invalid depth level: {depth_level}. Must be one of {list(DEPTH_LEVEL_PARAMS.keys())}")
        
    params = DEPTH_LEVEL_PARAMS[depth_level]
    p_g = params.guess
    p_s = params.slip
    p_t = params.learn

    if verdict == "correct":
        numrator = prior * (1.0 - p_s)
        denomintor = numrator + ((1.0 - prior) * p_g)

    elif verdict == "incorrect":
        numrator = prior * p_s
        denomintor = numrator + ((1.0 - prior) * (1.0 - p_g))

    else:
        raise ValueError(f"Invalid verdict: '{verdict}'. Must be one of {list(Verdict)}")

    posterior = numrator / denomintor if denomintor > 0 else prior

    next_mastry = posterior + ((1.0 - posterior)* p_t)

    return round(posterior,4),round(next_mastry,4)

if __name__ == "__main__":
    print("Testing BKT math engine...")

    post1, m1 = update_mastery(DEFAULT_PRIOR, "correct", "L1")
    print(f"Turn 1 (L1 Correct)  : Prior=0.3000 -> Posterior={post1:.4f} -> Next={m1:.4f} (Expected: ~0.5970)")
    assert abs(m1 - 0.5970) < 0.001, f"Turn 1 expected ~0.5970, got {m1}"

    # Turn 2: L2 Correct
    post2, m2 = update_mastery(m1, "correct", "L2")
    print(f"Turn 2 (L2 Correct)  : Prior={m1:.4f} -> Posterior={post2:.4f} -> Next={m2:.4f} (Expected: ~0.8761)")
    assert abs(m2 - 0.8761) < 0.001, f"Turn 2 expected ~0.8761, got {m2}"

    # Turn 3: L3 Incorrect (Nervous Slip / Missed Nuance)
    post3, m3 = update_mastery(m2, "incorrect", "L3")
    print(f"Turn 3 (L3 Incorrect): Prior={m2:.4f} -> Posterior={post3:.4f} -> Next={m3:.4f} (Expected: ~0.5639)")
    assert abs(m3 - 0.5639) < 0.001, f"Turn 3 expected ~0.5639, got {m3}"

    # Turn 4: L3 Correct (Re-probe Recovery)
    post4, m4 = update_mastery(m3, "correct", "L3")
    print(f"Turn 4 (L3 Correct)  : Prior={m3:.4f} -> Posterior={post4:.4f} -> Next={m4:.4f} (Expected: ~0.9208)")
    assert abs(m4 - 0.9208) < 0.001, f"Turn 4 expected ~0.9208, got {m4}"

    print("\nSUCCESS: All BKT mathematical calculations match the specification exactly!")
