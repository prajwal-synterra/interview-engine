# 12 — Report Generation Engine

## Purpose

Generates two comprehensive assessment reports at end of session:
1. Student Career Compass & Growth Report (candidate copy)
2. Technical Evaluation & Forensic Audit Report (hiring team copy)

## Location

File: app/report_generator.py
Functions: generate_student_report(), generate_evaluator_report()
Called from: live_server.py (finish_interview event, REST /finish, auto-disconnect)

## Report 1: Student Career Compass

LLM-generated (gemini-2.5-flash with gemini-2.0-flash fallback).

Input data:
- candidate_name, level
- turns_history (truncated to 250 chars per turn)
- skills_mastery dict {skill: P(L)}
- proctor_bii
- mirt_theta, mirt_std_error (MIRT 5D radar)
- ecosystem_summary
- matched_pillars (with probe hints)
- primary_topic

Output format (Markdown):
1. Executive Mentorship Summary
2. Cognitive Archetype & Engineering Profile
3. Multidimensional Ability Profile (MIRT Dimensions with percentiles)
4. Top 3 Demonstrated Strengths with conversational citations
5. High-Impact Growth & Focus Areas
6. 30-60-90 Day Actionable Learning Roadmap
7. Curated Resource Recommendations

Fallback: structural template filled with radar text + domain label if LLM fails.
Saved to: reports/student_career_compass_{timestamp}.md (disk)
         PostgreSQL final_reports.student_compass_markdown

## Report 2: Evaluator Forensic Audit

Template-based (deterministic Markdown, no additional LLM call for evaluator report).

Sections:
1. Hiring Recommendation & Verdict (badge + avg mastery + pass rate + BII + fraud risk)
2. BKT Competency Matrix (skill -> P(L) -> mastery certification table)
3. Polyglot Ecosystem Audit (detected ecosystems, stack keywords)
4. MIRT Ability Radar (5D theta + std_error + percentile + tier)
5. Cognitive Potential Fingerprint (IVI, RAG, theta, Authenticity)
6. Turn-by-Turn Audit Trail (turn# | skill | verdict | posterior | FSM action | latency)
7. Architectural Stress-Test Notes

Hiring thresholds:
- avg_mastery >= 0.80 AND proctor_bii >= 0.70 -> STRONG HIRE
- avg_mastery >= 0.60 AND proctor_bii >= 0.60 -> HIRE
- avg_mastery >= 0.45 -> LEAN HIRE
- else -> NO HIRE

CPF values in evaluator report:
- IVI = min(1.0, 0.4 + avg_mastery * 0.5)  [NOTE: approximation, not true CPF formula]
- RAG = min(1.0, avg_mastery * 1.1)          [NOTE: approximation]
- True CPF (generate_cpf()) NOT called in live pipeline

## Report Triggers

| Trigger | Location |
|---------|---------|
| WebSocket "finish_interview" event | live_server.py line ~1432 |
| REST POST /api/session/{id}/finish | live_server.py finish_session_endpoint() |
| REST GET /api/session/{id}/intermediate-report | live_server.py get_intermediate_report() |
| WebSocket disconnect (auto) | live_server.py finally block -> _auto_generate_and_save_reports() |

## Report Persistence

Reports saved to disk: reports/{type}_{timestamp}.md
Reports saved to PostgreSQL: final_reports table (upsert on session_id)
Status in interview_sessions updated to COMPLETED + completed_at timestamp

## What is NOT Implemented

- Role-specific report (same evaluator report for all roles)
- Report versioning (upsert overwrites previous)
- LLM call for evaluator report main narrative (template only)
- True CPF score in report (approximated values used)
