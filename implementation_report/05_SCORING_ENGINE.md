# 05 — Scoring Engine

## Purpose

Computes the candidate's final composite score using BKT mastery probabilities,
scaffolding penalties, BII integrity weighting, and adversarial challenge performance.

## Components

| File | Class | Role |
|------|-------|------|
| app/bkt_engine.py | BKTNode | Per-skill latent mastery tracking |
| app/cpf_engine.py | MasterScorer | Final score aggregation formula |
| app/mirt_engine.py | MIRTEngine | 5D latent ability (reported separately) |

---

## BKT — Bayesian Knowledge Tracing

### Mathematical Model

Parameters (BKTConfig):
- P(T) = 0.15  — probability of learning/transitioning to mastery in one step
- P(S) = 0.10  — base slip probability (answering incorrectly despite knowing)
- P(G) = 0.05  — guess probability (answering correctly without knowing)
- s_max = 0.25 — maximum slip floor (capped after consecutive errors)
- decay_rate = 0.85 — anti-coaching scaffolding decay per level
- mastery_threshold = 0.85
- deficiency_threshold = 0.20

Initial P(L0) by seniority:
- STUDENT:      P(L0) = 0.15
- JUNIOR:       P(L0) = 0.25
- MID:          P(L0) = 0.45
- SENIOR_STAFF: P(L0) = 0.70

### Update Equations

Step 1: Dynamic slip floor
```
If observation == 0:
    p_s = min(s_max, P_S_base + 0.05 * (consecutive_slips - 1))
Else:
    consecutive_slips = 0
    p_s = P_S_base
```

Step 2: Closed-form posterior P(L_t | O_t)
```
If O_t == 1 (correct):
    P(L_t | correct) = [P(L_{t-1}) * (1 - p_s)] / [P(L_{t-1}) * (1-p_s) + (1-P(L_{t-1})) * P_G]

If O_t == 0 (incorrect):
    P(L_t | incorrect) = [P(L_{t-1}) * p_s] / [P(L_{t-1}) * p_s + (1-P(L_{t-1})) * (1-P_G)]
```

Step 3: Forward state transition
```
P(L_{t+1}) = P(L_t | O_t) + (1 - P(L_t | O_t)) * P_T
```

Step 4: Anti-coaching scaffolding decay
```
delta = P(L_{t+1}) - P(L_{t-1})
If delta > 0 and scaffolding_level > 0:
    decay_factor = decay_rate ^ scaffolding_level   (e.g. 0.85^2 = 0.7225 at L2)
    P_effective = P(L_{t-1}) + delta * decay_factor
Else:
    P_effective = P(L_{t+1})
```

Final clamped: P(L) = max(0.001, min(0.999, P_effective))

### Mastery Status Thresholds

- MASTERED:    P(L) >= 0.85
- UNMASTERED:  P(L) <= 0.20 AND at least 3 observations
- IN_PROGRESS: all other states

### Mastery Surge (Devil's Advocate Trigger)

```
is_surge = (delta >= 0.40) OR (P(L) >= 0.90 AND scaffolding_level == 0 AND len(history) <= 1)
```

---

## Master Scoring Formula (MasterScorer.calculate_final_score)

```
FinalScore = (Sum(w_k * P(L_k))) * ScaffoldMultiplier * BII * AdversarialMultiplier
```

Where:
- w_k = 1 / num_skills (equal weight per skill — NOTE: not role-weighted in current impl)
- P(L_k) = terminal BKT mastery for skill k
- ScaffoldMultiplier = max(0.50, 1.0 - 0.05 * sum(level * count for all scaffolding events))
- BII = Behavioral Integrity Index from proctor (0.0 to 1.0)
- AdversarialMultiplier = 1.0 + 0.10 * devils_advocate_score (-1.0 to +1.0)
- FinalScore scaled to 0-100

### Hiring Thresholds

| Verdict | Condition |
|---------|-----------|
| FLAGGED_FOR_FRAUD | BII < 0.70 (overrides technical score) |
| STRONG_HIRE | FinalScore >= 85 |
| HIRE | FinalScore >= 70 |
| LEANING_HIRE | FinalScore >= 55 |
| NO_HIRE | FinalScore < 55 |

Simplified thresholds in live_server.py (uses avg_mastery directly):
- STRONG HIRE: avg_mastery >= 0.80
- HIRE: avg_mastery >= 0.60
- LEAN HIRE: avg_mastery >= 0.45
- NO HIRE: else

NOTE: MasterScorer.calculate_final_score() is only called inside
policy_router.generate_final_session_report() which is NEVER called in
the live pipeline. The live pipeline uses avg_mastery directly.

---

## MIRT — Multidimensional Item Response Theory

5 Dimensions:
- algorithms
- system_design
- concurrency
- databases
- distributed_systems

Prediction: P(correct | theta, alpha, b) = sigmoid(alpha . theta - b)

Online gradient update (after each turn):
```
eta = learning_rate / (1.0 + 0.05 * step_count)   # decaying learning rate
residual = observation - P_predicted
delta_theta[dim] = eta * alpha[dim] * residual
std_error[dim] = max(0.15, std_error / (1.0 + 0.1 * alpha^2 * P * (1-P)))
```

Initial: theta = 0.0 for all dims, std_error = 1.0
Learning rate: 0.45

MIRT is used for reporting (percentile radar) only.
It does NOT affect hiring decision or BKT mastery in current implementation.
