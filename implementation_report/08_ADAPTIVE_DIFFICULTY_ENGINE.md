# 08 — Adaptive Difficulty Engine

## Purpose

Adjusts the challenge level of the interview dynamically based on:
1. Scaffolding ladder (L0-L3): controls how much hint Alex gives
2. MIRT (5D): tracks candidate ability for reporting
3. Devil's Advocate: challenges claimed mastery under pressure

## Scaffolding Ladder (app/policy_router.py)

| Level | State | Alex Directive |
|-------|-------|---------------|
| L0 | ACTIVE | Open-ended question, no hint |
| L1 | SCAFFOLDING_L1 | Subtle Socratic conceptual nudge, no solution |
| L2 | SCAFFOLDING_L2 | Concrete partial scenario or skeleton |
| L3 | SCAFFOLDING_L3 | Binary architectural trade-off choice |

Trigger: each observation==0 increments current_scaffolding_level by 1
At L3 fail -> _advance_to_next_skill() (topic conceded as unmastered)

Anti-coaching decay: BKT delta multiplied by 0.85^level
  L1 gain * 0.85 = 85% of normal gain
  L2 gain * 0.7225 = 72.25% of normal gain
  L3 gain * 0.6141 = 61.4% of normal gain

## Devil's Advocate Protocol (app/policy_router.py)

Triggered when: bkt_res["is_surge"] == True
  (delta >= 0.40 OR P(L) >= 0.90 with <= 1 prior observation)

Protocol:
- State -> DEVILS_ADVOCATE
- Alex directive: "Challenge their architectural choice with a severe edge case"
- On next observation:
  - observation==1: node.p_l = max(p_l, mastery_threshold + 0.05); propagate mastery
  - observation==0: node.p_l = min(p_l, deficiency_threshold); mastery collapsed
- After Devil's Advocate: advance to next skill regardless

Purpose: Prevent false mastery from a lucky first answer.

## MIRT — Adaptive Item Selection

MIRTEngine.select_highest_information_item() exists and uses Fisher Information:
```
I(theta, item) = ||alpha||^2 * P(correct) * (1 - P(correct))
```
Highest information when item difficulty matches candidate ability.

CURRENT STATUS: select_highest_information_item() is defined but NOT called
in the live pipeline. Alex generates questions freely. MIRT only tracks ability.

## Difficulty Estimation

estimated_difficulty returned by Shadow Evaluator (-1.5 to +2.5):
- Passed to MIRT update_ability() as item.difficulty
- Used to adjust MIRT ability theta updates

## Prerequisite Gate as Difficulty Control

Skills with unmet prerequisites are excluded from recommendation.
This prevents asking staff-level distributed systems questions
before the candidate has demonstrated basic concurrency knowledge.
