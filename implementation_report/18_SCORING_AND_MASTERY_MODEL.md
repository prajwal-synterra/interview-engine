git push -u origin dev/v4
# 18 — Scoring and Mastery Model (Full Mathematical Derivation)

## Layer 1: BKT Bayesian Posterior (per skill, per turn)

Parameters (BKTConfig, bkt_engine.py):
  P_T = 0.15    (transit / learning probability)
  P_S = 0.10    (base slip probability)
  P_G = 0.05    (guess probability)
  s_max = 0.25  (maximum slip floor)
  decay_rate = 0.85  (anti-coaching decay base)
  mastery_threshold = 0.85
  deficiency_threshold = 0.20

Initial P(L0) by tier:
  STUDENT = 0.15, JUNIOR = 0.25, MID = 0.45, SENIOR_STAFF = 0.70

Step 1: Dynamic Slip Floor
  If O_t = 0 (incorrect):
    consecutive_slips += 1
    p_s = min(s_max, P_S + 0.05 * (consecutive_slips - 1))
  If O_t = 1 (correct):
    consecutive_slips = 0
    p_s = P_S

Step 2: Closed-form Bayesian Posterior
  If O_t = 1:
    P(L_t | correct) = [P(L_{t-1}) * (1 - p_s)] / [P(L_{t-1}) * (1-p_s) + (1-P(L_{t-1})) * P_G]

  If O_t = 0:
    P(L_t | incorrect) = [P(L_{t-1}) * p_s] / [P(L_{t-1}) * p_s + (1-P(L_{t-1})) * (1-P_G)]

Step 3: Forward State Transition
  P(L_t+1) = P(L_t | O_t) + (1 - P(L_t | O_t)) * P_T

Step 4: Anti-Coaching Scaffolding Decay
  delta = P(L_t+1) - P(L_{t-1})
  If delta > 0 AND scaffolding_level > 0:
    decay_factor = decay_rate ^ scaffolding_level
    P_effective = P(L_{t-1}) + delta * decay_factor
  Else:
    P_effective = P(L_t+1)

  P(L) = clamp(P_effective, 0.001, 0.999)

Step 5: Mastery Surge Detection
  is_surge = (delta >= 0.40) OR (P(L) >= 0.90 AND scaffolding_level = 0 AND len(history) <= 1)

---

## Layer 2: MIRT 5D Online Gradient Update (per turn)

Dimensions: algorithms, system_design, concurrency, databases, distributed_systems
Initial: theta[dim] = 0.0, std_error[dim] = 1.0
Learning rate: eta_0 = 0.45

Per turn:
  p_predicted = sigmoid(sum(alpha[dim] * theta[dim]) - difficulty)
  residual = observation - p_predicted
  eta = eta_0 / (1.0 + 0.05 * step_count)   [decaying rate]

  For each dim in alpha:
    theta[dim] += eta * alpha[dim] * residual
    info = alpha[dim]^2 * p_predicted * (1 - p_predicted)
    std_error[dim] = max(0.15, std_error[dim] / (1 + 0.1 * info))

Percentile: theta_to_percentile(theta) = 0.5 * (1 + erf(theta / sqrt(2))) * 100

Tiers:
  theta >= 2.0: Staff / Principal Frontier
  theta >= 1.0: Senior Engineer
  theta >= 0.0: Mid-Level Professional
  theta >= -1.0: Developing / Junior
  else: Foundational Trainee

MIRT is used for the reporting radar ONLY.
It does not influence hiring verdict or BKT progression.

---

## Layer 3: Behavioral Integrity Index (BII)

Starting value: 1.0 (perfect integrity)
Each flag deducts penalty:
  UNNATURAL_LEXICAL_DENSITY_TTR: -0.10
    (triggered when len(words) >= 35 AND TTR > 0.88)
  CONTRADICTION_PROBE_FAILED: -0.35
    (triggered when candidate accepts injected false technical premise)
  COPILOT_LATENCY_JITTER_ANOMALY: -0.40
    (triggered when mean_latency > 2000ms AND jitter_std < 180ms, after >= 3 turns)
  PASSIVE_COMPLIANCE_ZERO_CURIOSITY: -0.08
    (triggered after >= 5 turns with zero clarifying questions)

BII = max(0.0, 1.0 - sum(penalties))
Passing threshold: BII >= 0.70 (from cpf_engine.py)
Flagged threshold: BII < 0.35 -> "FLAGGED" status in telemetry

---

## Layer 4: Master Composite Score (cpf_engine.py MasterScorer)

FinalScore = (Sigma_k(w_k * P(L_k))) * ScaffoldMultiplier * BII * AdversarialMultiplier

Where:
  w_k = 1 / len(skills)  [equal weighting -- not role-weighted]
  P(L_k) = terminal BKT mastery for skill k
  total_scaffold_units = sum(level * count for each scaffolding event across all skills)
  ScaffoldMultiplier = max(0.50, 1.0 - 0.05 * total_scaffold_units)
  devils_advocate_score = mean of [+1.0 or -1.0] per DA event
  AdversarialMultiplier = 1.0 + 0.10 * clamp(devils_advocate_score, -1.0, 1.0)

FinalScore scaled: min(100, max(0, raw_score * 100))

Hiring classification:
  BII < 0.70: FLAGGED_FOR_FRAUD (overrides technical score)
  FinalScore >= 85: STRONG_HIRE
  FinalScore >= 70: HIRE
  FinalScore >= 55: LEANING_HIRE
  else: NO_HIRE

NOTE: In the live pipeline, avg_mastery is used directly (simplified):
  avg_mastery = mean P(L) across all nodes
  STRONG HIRE: avg_mastery >= 0.80
  HIRE: avg_mastery >= 0.60
  LEAN HIRE: avg_mastery >= 0.45
  NO HIRE: else

MasterScorer.calculate_final_score() is only called in
policy_router.generate_final_session_report() which is NEVER called in live pipeline.

---

## Scoring Properties

| Property | Value |
|----------|-------|
| Raw score range | P(L): 0.001 to 0.999 |
| Easy vs hard question weight | Scaffold decay lowers gain from scaffolded answers |
| Repeated attempts | Consecutive slips increase dynamic slip floor |
| Partial credit | Not explicit; depth_score stored but not used in BKT |
| Domain aggregation | Equal weight per skill (no role-specific weighting) |
| Score persistence | bkt_prior + bkt_posterior per turn in PostgreSQL |
| Score recalculated | After every turn |
