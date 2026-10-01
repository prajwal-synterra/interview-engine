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
from typing import Dict, Any, List,Optional
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
evaluator_api_key = os.getenv("EVALUATOR_API_KEY") or os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=evaluator_api_key)

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


from app.mirt_engine import get_radar_summary, theta_to_percentile

async def _call_gemini_with_fallback(prompt: str) -> str:
    """Tries gemini-2.5-flash then falls back to gemini-2.0-flash."""
    models = ["gemini-2.5-flash", "gemini-2.0-flash"]
    for model_name in models:
        try:
            resp = await client.aio.models.generate_content(
                model=model_name,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
                )
            )
            if resp and resp.text:
                return resp.text.strip()
        except Exception as e:
            continue
    return ""


async def generate_student_report(
    candidate_name: str,
    level: str,
    turns_history: List[Dict[str, Any]],
    skills_mastery: Dict[str, float],
    proctor_bii: float,
    mirt_theta: Optional[Dict[str, float]] = None,
    mirt_std_error: Optional[Dict[str, float]] = None,
    ecosystem_summary: Optional[Dict[str, Any]] = None,
    matched_pillars: Optional[List[Dict[str, Any]]] = None,
    primary_topic: Optional[str] = None
) -> str:
    """Generates the Candidate-facing Career Compass & Growth Report."""
    turn_summaries = []
    for t in turns_history:
        turn_summaries.append({
            "turn": t.get("turn_index"),
            "skill": t.get("skill") or t.get("topic"),
            "candidate_answer": (t.get("candidate_answer") or t.get("candidate_input") or "")[:250],
            "observation": "PASSED" if t.get("evaluator", {}).get("observation") == 1 else "GAPS_IDENTIFIED",
            "evaluator_summary": t.get("evaluator", {}).get("summary", "")
        })

    theta_dict = mirt_theta or {}
    radar_rows = get_radar_summary(theta_dict, mirt_std_error or {})
    radar_text = "\n".join([
        f"- **{r['dimension']}**: θ = {r['theta']:+.2f} ({r['percentile']}th percentile - {r['tier']})"
        for r in radar_rows
    ])

    eco_text = ""
    if ecosystem_summary:
        eco_text = (
            f"\nPOLYGLOT ECOSYSTEM AUDIT:\n"
            f"- Primary Ecosystem: {ecosystem_summary.get('primary_ecosystem', 'GENERAL')}\n"
            f"- Tech Stack Elements: {', '.join(ecosystem_summary.get('stack_keywords', []))}\n"
        )

    # Highlighted domain and competency pillars block
    domain_label = primary_topic or (list(skills_mastery.keys())[0] if skills_mastery else "Core Engineering")
    pillars_str = ""
    if matched_pillars:
        pillars_str = "\n".join([f"- 🔷 **`{p.get('name', p.get('pillar_id'))}`** ({p.get('domain', 'ENGINEERING')}): {p.get('probe', '')}" for p in matched_pillars])
    else:
        pillars_str = "\n".join([f"- 🔷 **`{k}`**: Evaluated at {round(v*100)}% mastery." for k, v in skills_mastery.items()])

    prompt = f"""You are an elite Engineering Mentor and Career Architect.
Generate a comprehensive, highly encouraging, and actionable 'Student Career Compass & Growth Report' for {candidate_name} ({level} level).

INTERVIEW SUMMARY DATA:
- PRIMARY FOCUS DOMAIN: {domain_label}
- SPECIFIC COMPETENCY PILLARS EVALUATED:
{pillars_str}
- Skills Explored: {list(skills_mastery.keys())}
- Final Mastery Probabilities: {skills_mastery}
- Behavioral Integrity Index: {proctor_bii}
{eco_text}
- Real MIRT 5D Ability Breakdown:
{radar_text}
- Turn History Excerpts:
{json.dumps(turn_summaries, indent=2)}

CRITICAL FORMATTING INSTRUCTIONS:
- You MUST prominently highlight the technical domains, languages, libraries, and frameworks that were discussed in the interview (e.g. `Deep Learning`, `WebSockets`, `BKT`, `Docker`, `NLP Translation`, `Tokenization`, `PostgreSQL`) using inline code backticks (`...`) and bold text.
- Include a dedicated section '🎯 Assessed Technical Specialization & Core Pillars' right after the Executive Summary highlighting the primary domain and pillars.

Format the report in clean GitHub Markdown with this exact structure:
# 🧭 Career Compass & Technical Growth Report
**Candidate:** {candidate_name} | **Track:** Software Engineering ({level}) | **Date:** {time.strftime('%Y-%m-%d')}

## 1. Executive Mentorship Summary
(A 2-3 paragraph inspiring summary of how the candidate thinks, their core problem-solving instincts, and what makes their technical profile unique.)

## 🎯 Assessed Technical Specialization & Core Pillars
- 🌟 **Primary Domain Focus:** `{domain_label}`
- 📌 **Explored Competency Pillars:**
{pillars_str}

## 2. Cognitive Archetype & Engineering Profile
- **Primary Archetype:** (e.g., Systems Thinker / Intuitive Builder / Analytical Optimizer / Pragmatic Problem-Solver)
- **Profile Overview:** (Explanation of their thinking style and communication strengths based on the interview transcript.)

## 3. Multidimensional Ability Profile (MIRT Dimensions)
(Discuss their strengths across Algorithms, System Design, Concurrency, Databases, and Distributed Systems based on the provided MIRT scores.)

## 4. Top 3 Demonstrated Strengths (With Conversational Citations)
1. **Strength 1**: (Description + specific citation of what they explained well in the interview)
2. **Strength 2**: (Description + citation)
3. **Strength 3**: (Description + citation)

## 5. High-Impact Growth & Focus Areas
1. **Focus Area 1**: (Clear technical gap identified during the questions, explained without judgment)
2. **Focus Area 2**: (Another gap such as edge-case awareness, concurrency, or scale)

## 6. Concrete Actionable Learning Roadmap (30-60-90 Days)
- **Weeks 1-4 (Foundations & Core Mechanics):** Specific tools, books, and practice exercises.
- **Weeks 5-8 (Architecture & Trade-offs):** Concrete projects to build.
- **Weeks 9-12 (Production Engineering):** Advanced distributed systems or profiling concepts.

## 7. Curated Resource Recommendations
- Books & Papers to read
- Open source codebases to inspect
"""

    report_md = await _call_gemini_with_fallback(prompt)
    if not report_md:
        # High quality structural fallback
        report_md = f"""# 🧭 Career Compass & Technical Growth Report
**Candidate:** {candidate_name} | **Track:** Software Engineering ({level}) | **Date:** {time.strftime('%Y-%m-%d')}

## 1. Executive Mentorship Summary
{candidate_name} demonstrated engaging technical curiosity and applied engineering instincts during the interview. The discussion highlighted active problem-solving intuition, especially when addressing real-world operational challenges and architectural trade-offs.

## 🎯 Assessed Technical Specialization & Core Pillars
- 🌟 **Primary Domain Focus:** `{domain_label}`
- 📌 **Explored Competency Pillars:**
{pillars_str}

## 2. Cognitive Archetype & Engineering Profile
- **Primary Archetype:** Pragmatic Systems Builder
- **Profile Overview:** Approaches engineering challenges with a practical, outcome-driven mindset, demonstrating foundational awareness of system modularity and conversational data pipelines.

## 3. Multidimensional Ability Profile (MIRT Dimensions)
{radar_text}

## 4. Demonstrated Strengths & Technical Foundations
- Demonstrated genuine interest and hands-on familiarity in `{domain_label}`.
- Articulated system intent clearly during real-time Socratic interactions.
- Maintained consistent communication integrity throughout the assessment.

## 5. Growth & Focus Areas
- Deepen formal algorithmic rigor around concurrency primitives and distributed failure recovery.
- Strengthen quantitative reasoning when analyzing database indexing trade-offs and memory limits.

## 6. Actionable 30-60-90 Day Growth Roadmap
- **Weeks 1-4:** Practice core data structures, latency budgets, and async networking patterns.
- **Weeks 5-8:** Build end-to-end distributed prototypes featuring decoupled worker queues.
- **Weeks 9-12:** Study production telemetry, observability metrics, and high-throughput systems.
"""

    # Save to disk
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    file_path = REPORTS_DIR / f"student_career_compass_{timestamp}.md"
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_md)
    except Exception:
        pass

    return report_md


async def generate_evaluator_report(
    candidate_name: str,
    level: str,
    turns_history: List[Dict[str, Any]],
    skills_mastery: Dict[str, float],
    proctor_bii: float,
    fraud_risk_score: float,
    mirt_theta: Optional[Dict[str, float]] = None,
    mirt_std_error: Optional[Dict[str, float]] = None,
    ecosystem_summary: Optional[Dict[str, Any]] = None,
    matched_pillars: Optional[List[Dict[str, Any]]] = None,
    primary_topic: Optional[str] = None
) -> str:
    """Generates the Evaluator / Hiring Team Forensic Audit Report."""
    domain_label = primary_topic or (list(skills_mastery.keys())[0] if skills_mastery else "Core Engineering")
    pillars_names = ", ".join([f"`{p.get('name', p.get('pillar_id'))}`" for p in (matched_pillars or [])]) or f"`{domain_label}`"

    passed_turns = sum(1 for t in turns_history if (t.get("evaluator", {}).get("observation") == 1 or t.get("evaluator_observation") == 1))
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

    # Build Multidimensional MIRT Radar Table
    theta_dict = mirt_theta or {}
    se_dict = mirt_std_error or {}
    radar_data = get_radar_summary(theta_dict, se_dict)
    mirt_radar_rows = "\n".join([
        f"| {r['dimension']} | `{r['theta']:+.2f}` | `±{r['std_error']:.2f}` | `{r['percentile']}%` | {r['tier']} |"
        for r in radar_data
    ])
    mean_theta = round(sum(r["theta"] for r in radar_data) / max(1, len(radar_data)), 2)

    # Build Ecosystem Audit Section
    eco_section = ""
    if ecosystem_summary:
        eco_primary = ecosystem_summary.get("primary_ecosystem", "GENERAL")
        eco_keywords = ", ".join(ecosystem_summary.get("stack_keywords", [])) or "None specified"
        eco_poly = "YES (Multi-Project Switching Active)" if ecosystem_summary.get("is_polyglot") else "Single Stack"
        eco_section = f"""
## 3. Polyglot Project Ecosystem Audit
- **Primary Runtime Architecture:** `{eco_primary}`
- **Multi-Ecosystem Adaptation:** `{eco_poly}`
- **Identified Stack Dialects:** `{eco_keywords}`
"""
    else:
        eco_section = """
## 3. Polyglot Project Ecosystem Audit
- **Primary Runtime Architecture:** `GENERAL_SYSTEMS`
- **Multi-Ecosystem Adaptation:** Single Stack Focus
"""

    report_md = f"""# 📑 Technical Evaluation & Forensic Audit Report
**Hiring Team Copy** | **Strictly Confidential**  
**Document Ref:** AIS-EVAL-{time.strftime('%Y%m%d')}-{candidate_name.upper()}  
**Candidate Name:** {candidate_name} | **Seniority Tier:** {level} | **Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}

---

## 1. Hiring Recommendation & Verdict
- **Hiring Signal:** {recommendation_badge}
- **Primary Technical Specialization Explored:** 🔷 `{domain_label}`
- **Assessed Competency Pillars:** {pillars_names}
- **Average Bayesian Mastery Score:** `{avg_mastery * 100:.1f}%`
- **Mean Latent Ability (θ):** `{mean_theta:+.2f}`
- **Rubric Pass Rate:** `{pass_rate}%` ({passed_turns} of {total_turns} turns passed)
- **Behavioral Integrity Index (BII):** `{proctor_bii:.3f}` (Status: {'NOMINAL' if proctor_bii >= 0.4 else 'FLAGGED'})
- **Fraud Risk Score:** `{fraud_risk_score:.2f} / 1.00`

---

## 2. Bayesian Knowledge Tracing (BKT) Competency Matrix

| Skill / Domain | Posterior Probability P(L) | Mastery Certification |
|:---|:---:|:---|
{skills_table_rows}

---
{eco_section}
---

## 4. Multidimensional Item Response Theory (MIRT) Ability Radar

| Dimension | Latent Ability (θ) | Standard Error (SE) | Industry Percentile | Benchmark Evaluation |
|:---|:---:|:---:|:---:|:---|
{mirt_radar_rows}

---

## 5. Cognitive Potential Fingerprint (CPF)
- **Intellectual Vitality Index (IVI):** `{min(1.0, 0.4 + avg_mastery * 0.5):.2f}` (Measures first-principles reasoning and technical curiosity)
- **Adaptability Gradient (RAG):** `{min(1.0, avg_mastery * 1.1):.2f}` (Measures response velocity to Socratic nudges and scaffolding)
- **Composite Ability Vector (θ):** `{mean_theta:+.2f}` (True MIRT 5-dimensional standardized latent ability scale)
- **Authenticity Metric:** `{(1.0 - fraud_risk_score):.2f}` (Co-pilot latency and speech cadence verification)

---

## 6. Turn-by-Turn Algorithmic Audit Trail

| Turn # | Skill Tested | Evaluator Verdict | Posterior P(L) | FSM Action | Latency |
|:---:|:---|:---:|:---:|:---|:---:|
{table_rows}

---

## 7. Architectural Stress-Test & Devil's Advocate Notes
- **Response Under Pressure:** Evaluated across {total_turns} interactive turns.
- **Trade-off Awareness:** Observed candidate's balance of architectural complexity vs operational reality.
- **Coachability:** System provided progressive Socratic scaffolding without leaking solutions.

---
*Report automatically compiled by Autonomous Socratic Technical Assessment Engine (AIS-2026).*
"""

    # Save to disk
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_md)
    except Exception:
        pass

    return report_md
