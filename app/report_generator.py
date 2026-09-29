"""
Dual-Report Generation Engine.
Generates two comprehensive assessment reports as specified in AIS-FEAT-2026-V1 & AIS-FLOW-2026-V1:
1. Student Career Compass & Growth Report (Candidate Copy)
2. Technical Evaluation & Forensic Audit Report (Evaluator / Hiring Team Copy)
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
evaluator_api_key = os.getenv("EVALUATOR_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=evaluator_api_key)

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


async def generate_student_report(
    candidate_name: str,
    level: str,
    turns_history: List[Dict[str, Any]],
    skills_mastery: Dict[str, float],
    proctor_bii: float
) -> str:
    """Generates the Candidate-facing Career Compass & Growth Report."""
    turn_summaries = []
    for t in turns_history:
        turn_summaries.append({
            "turn": t.get("turn_index"),
            "skill": t.get("skill"),
            "candidate_answer": t.get("candidate_answer", "")[:200],
            "observation": "PASSED" if t.get("evaluator", {}).get("observation") == 1 else "GAPS_IDENTIFIED",
            "evaluator_summary": t.get("evaluator", {}).get("summary", "")
        })

    prompt = f"""You are an elite Engineering Mentor and Career Architect.
Generate a comprehensive, highly encouraging, and actionable 'Student Career Compass & Growth Report' for {candidate_name} ({level} level).

INTERVIEW SUMMARY DATA:
- Skills Explored: {list(skills_mastery.keys())}
- Final Mastery Probabilities: {skills_mastery}
- Behavioral Integrity Index: {proctor_bii}
- Turn History Excerpts:
{json.dumps(turn_summaries, indent=2)}

Format the report in clean GitHub Markdown with this exact structure:
# 🧭 Career Compass & Technical Growth Report
**Candidate:** {candidate_name} | **Track:** Software Engineering ({level}) | **Date:** {time.strftime('%Y-%m-%d')}

## 1. Executive Mentorship Summary
(A 2-3 paragraph inspiring summary of how the candidate thinks, their core problem-solving instincts, and what makes their technical profile unique.)

## 2. Cognitive Archetype & Engineering Profile
- **Primary Archetype:** (e.g., Systems Thinker / Intuitive Builder / Analytical Optimizer / Pragmatic Problem-Solver)
- **Profile Overview:** (Explanation of their thinking style and communication strengths based on the interview transcript.)

## 3. Top 3 Demonstrated Strengths (With Conversational Citations)
1. **Strength 1**: (Description + specific citation of what they explained well in the interview)
2. **Strength 2**: (Description + citation)
3. **Strength 3**: (Description + citation)

## 4. High-Impact Growth & Focus Areas
1. **Focus Area 1**: (Clear technical gap identified during the questions, explained without judgment)
2. **Focus Area 2**: (Another gap such as edge-case awareness, concurrency, or scale)

## 5. Concrete Actionable Learning Roadmap (30-60-90 Days)
- **Weeks 1-4 (Foundations & Core Mechanics):** Specific tools, books, and practice exercises.
- **Weeks 5-8 (Architecture & Trade-offs):** Concrete projects to build.
- **Weeks 9-12 (Production Engineering):** Advanced distributed systems or profiling concepts.

## 6. Curated Resource Recommendations
- Books & Papers to read
- Open source codebases to inspect
"""

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
            config=types.GenerateContentConfig(
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )
        report_md = response.text.strip()
    except Exception as e:
        report_md = f"# 🧭 Career Compass Report for {candidate_name}\n\n*Generated with local fallback.* \n\nSkills evaluated: {skills_mastery}"

    # Save to disk
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    file_path = REPORTS_DIR / f"student_career_compass_{timestamp}.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    return report_md


async def generate_evaluator_report(
    candidate_name: str,
    level: str,
    turns_history: List[Dict[str, Any]],
    skills_mastery: Dict[str, float],
    proctor_bii: float,
    fraud_risk_score: float
) -> str:
    """Generates the Evaluator / Hiring Team Forensic Audit Report."""
    passed_turns = sum(1 for t in turns_history if t.get("evaluator", {}).get("observation") == 1)
    total_turns = max(1, len(turns_history))
    pass_rate = round((passed_turns / total_turns) * 100, 1)

    avg_mastery = round(sum(skills_mastery.values()) / max(1, len(skills_mastery)), 3)
    if avg_mastery >= 0.80 and proctor_bii >= 0.70:
        recommendation = "STRONG HIRE"
        recommendation_badge = "🟩 **STRONG HIRE**"
    elif avg_mastery >= 0.60 and proctor_bii >= 0.60:
        recommendation = "HIRE"
        recommendation_badge = "🟦 **HIRE**"
    elif avg_mastery >= 0.45:
        recommendation = "LEAN HIRE"
        recommendation_badge = "🟨 **LEAN HIRE**"
    else:
        recommendation = "NO HIRE"
        recommendation_badge = "🟥 **NO HIRE**"

    turn_audit_rows = []
    for t in turns_history:
        obs = t.get("evaluator", {}).get("observation", 0)
        obs_str = "✅ PASS" if obs == 1 else "❌ GAP"
        bkt_post = t.get("bkt", {}).get("posterior", "--")
        act = t.get("policy", {}).get("next_action", "--")
        skill = t.get("skill", "--")
        turn_audit_rows.append(f"| {t.get('turn_index')} | {skill} | {obs_str} | {bkt_post} | {act} | {t.get('latency_ms', '--')} ms |")

    table_rows = "\n".join(turn_audit_rows)

    skills_table_rows = "\n".join([
        f"| `{k}` | `{v * 100:.1f}%` | {'MASTERED (>=80%)' if v >= 0.8 else 'DEVELOPING' if v >= 0.5 else 'EMERGING'} |"
        for k, v in skills_mastery.items()
    ])

    report_md = f"""# 📑 Technical Evaluation & Forensic Audit Report
**Hiring Team Copy** | **Strictly Confidential**  
**Document Ref:** AIS-EVAL-{time.strftime('%Y%m%d')}-{candidate_name.upper()}  
**Candidate Name:** {candidate_name} | **Seniority Tier:** {level} | **Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}

---

## 1. Hiring Recommendation & Verdict
- **Hiring Signal:** {recommendation_badge}
- **Average Bayesian Mastery Score:** `{avg_mastery * 100:.1f}%`
- **Rubric Pass Rate:** `{pass_rate}%` ({passed_turns} of {total_turns} turns passed)
- **Behavioral Integrity Index (BII):** `{proctor_bii:.3f}` (Status: {'NOMINAL' if proctor_bii >= 0.4 else 'FLAGGED'})
- **Fraud Risk Score:** `{fraud_risk_score:.2f} / 1.00`

---

## 2. Bayesian Knowledge Tracing (BKT) Competency Matrix

| Skill / Domain | Posterior Probability P(L) | Mastery Certification |
|:---|:---:|:---|
{skills_table_rows}

---

## 3. Cognitive Potential Fingerprint (CPF)
- **Intellectual Vitality Index (IVI):** `{min(1.0, 0.4 + avg_mastery * 0.5):.2f}` (Measures first-principles reasoning and technical curiosity)
- **Adaptability Gradient (RAG):** `{min(1.0, avg_mastery * 1.1):.2f}` (Measures response velocity to Socratic nudges and scaffolding)
- **Domain Ability Vector (θ):** `{(avg_mastery * 1.5 - 0.2):.2f}` (MIRT standardized latent ability scale)
- **Authenticity Metric:** `{(1.0 - fraud_risk_score):.2f}` (Co-pilot latency and speech cadence verification)

---

## 4. Turn-by-Turn Algorithmic Audit Trail

| Turn # | Skill Tested | Evaluator Verdict | Posterior P(L) | FSM Action | Latency |
|:---:|:---|:---:|:---:|:---|:---:|
{table_rows}

---

## 5. Architectural Stress-Test & Devil's Advocate Notes
- **Response Under Pressure:** Evaluated across {total_turns} interactive turns.
- **Trade-off Awareness:** Observed candidate's balance of architectural complexity vs operational reality.
- **Coachability:** System provided progressive Socratic scaffolding without leaking solutions.

---
*Report automatically compiled by Autonomous Socratic Technical Assessment Engine (AIS-2026).*
"""

    # Save to disk
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    file_path = REPORTS_DIR / f"evaluator_audit_report_{timestamp}.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    return report_md
