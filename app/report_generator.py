"""
Dual Report Generation Engine.
Generates:
1. Student Career Compass & Growth Report (Candidate copy, LLM mentorship-driven with deterministic fallback)
2. Technical Evaluation & Forensic Audit Report (Hiring team copy, 100% deterministic audit template with CPF & MIRT)
"""

import os
import json
import math
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Optional import of google-genai
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

_client = None
api_key = os.getenv("EVALUATOR_API_KEY") or os.getenv("GEMINI_API_KEY")
if genai and api_key:
    try:
        _client = genai.Client(api_key=api_key)
    except Exception as e:
        print(f"[Report Generator Warning] Gemini client init failed: {e}")


# ==============================================================================
# 1. Mathematical Scoring & Cognitive Potential Fingerprint (CPF)
# ==============================================================================

def calculate_master_score(
    skills_mastery: Dict[str, float],
    scaffolding_events: List[Dict],
    proctor_bii: float,
    devils_advocate_results: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Computes Master Composite Score and 5D Cognitive Potential Fingerprint (CPF).
    Formula from AIS-ARCH-2026-V3-MASTER:
      FinalScore = (Sum(w_k * P(L_k))) * ScaffoldMultiplier * BII * AdversarialMultiplier
    """
    if not skills_mastery:
        return {
            "final_score": 0.0,
            "verdict": "NO_HIRE",
            "base_technical": 0.0,
            "scaffold_multiplier": 1.0,
            "bii_multiplier": proctor_bii,
            "adversarial_multiplier": 1.0,
            "cpf": {"breadth": 0.0, "depth": 0.0, "velocity": 0.0, "rigor": 0.0, "authenticity": proctor_bii}
        }

    # 1. Base Technical Mastery (Equal weighting across assessed skills)
    num_skills = len(skills_mastery)
    base_technical = sum(skills_mastery.values()) / max(1, num_skills)

    # 2. Anti-Coaching Scaffold Multiplier: max(0.50, 1.0 - 0.05 * total_scaffold_units)
    total_scaffold_units = sum(ev.get("level", 0) for ev in scaffolding_events)
    scaffold_multiplier = max(0.50, 1.0 - (0.05 * total_scaffold_units))

    # 3. Behavioral Integrity Multiplier
    bii_clamped = max(0.0, min(1.0, proctor_bii))

    # 4. Adversarial Challenge Multiplier: 1.0 + 0.10 * mean(DA scores)
    da_scores = devils_advocate_results or []
    da_mean = (sum(da_scores) / len(da_scores)) if da_scores else 0.0
    adversarial_multiplier = 1.0 + (0.10 * max(-1.0, min(1.0, da_mean)))

    # Composite Score calculation (0 to 100)
    raw_score = base_technical * scaffold_multiplier * bii_clamped * adversarial_multiplier
    final_score = round(min(100.0, max(0.0, raw_score * 100.0)), 1)

    # Hiring Decision Thresholds
    if bii_clamped < 0.70:
        verdict = "FLAGGED_FOR_FRAUD"
        badge_color = "CRITICAL_RISK"
    elif final_score >= 85.0 or (base_technical >= 0.85 and bii_clamped >= 0.80):
        verdict = "STRONG_HIRE"
        badge_color = "EXEMPLARY"
    elif final_score >= 70.0 or (base_technical >= 0.65 and bii_clamped >= 0.75):
        verdict = "HIRE"
        badge_color = "RECOMMENDED"
    elif final_score >= 55.0 or (base_technical >= 0.50):
        verdict = "LEANING_HIRE"
        badge_color = "BORDERLINE"
    else:
        verdict = "NO_HIRE"
        badge_color = "DEFICIENT"

    # 5D Cognitive Potential Fingerprint (CPF)
    cpf = {
        "breadth": round(min(1.0, num_skills / 5.0), 2),
        "depth": round(base_technical, 2),
        "velocity": round(min(1.0, base_technical / max(1, total_scaffold_units + 1)), 2),
        "rigor": round(max(0.0, min(1.0, 0.5 + 0.5 * da_mean)), 2),
        "authenticity": round(bii_clamped, 2)
    }

    return {
        "final_score": final_score,
        "verdict": verdict,
        "badge_color": badge_color,
        "base_technical": round(base_technical, 3),
        "total_scaffold_units": total_scaffold_units,
        "scaffold_multiplier": round(scaffold_multiplier, 3),
        "bii_multiplier": round(bii_clamped, 3),
        "adversarial_multiplier": round(adversarial_multiplier, 3),
        "cpf": cpf
    }


# ==============================================================================
# 2. Report 2: Evaluator Forensic Audit Report (Deterministic Markdown)
# ==============================================================================

def generate_evaluator_report(
    session_id: str,
    candidate_name: str,
    seniority_level: str,
    turns_history: List[Dict],
    skills_mastery: Dict[str, float],
    proctor_bii: float,
    mirt_radar: List[Dict],
    ecosystem_info: Dict[str, Any],
    devils_advocate_results: Optional[List[int]] = None
) -> str:
    """
    Generates a deterministic, auditable Technical Forensic Evaluation Report for hiring teams.
    Zero hallucination risk. Includes BKT matrix, MIRT radar, CPF scores, and turn trail.
    """
    # Extract scaffolding events from turns
    scaffolding_events = [{"level": t.get("scaffolding_level", 0)} for t in turns_history if t.get("scaffolding_level", 0) > 0]
    scoring = calculate_master_score(skills_mastery, scaffolding_events, proctor_bii, devils_advocate_results)

    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Format BKT Matrix Table
    bkt_rows = []
    for skill, mastery in skills_mastery.items():
        if mastery >= 0.85:
            status = "CERTIFIED MASTERED"
        elif mastery >= 0.60:
            status = "COMPETENT"
        elif mastery >= 0.35:
            status = "DEVELOPING"
        else:
            status = "CRITICAL DEFICIENCY"
        bkt_rows.append(f"| `{skill:<32}` | {mastery:.3f} | {status:<20} |")
    bkt_table = "\n".join(bkt_rows) if bkt_rows else "| None recorded | 0.000 | N/A |"

    # Format MIRT Radar Table
    mirt_rows = []
    for m in mirt_radar:
        mirt_rows.append(
            f"| {m['dimension']:<38} | {m['theta']:>+5.2f} | {m['std_error']:>4.2f} | {m['percentile']:>5.1f}% | {m['tier']:<24} |"
        )
    mirt_table = "\n".join(mirt_rows) if mirt_rows else "| No MIRT dimensions evaluated | 0.00 | 1.00 | 50.0% | N/A |"

    # Format Turn Audit Table
    turn_rows = []
    for t in turns_history:
        t_idx = t.get("turn_index", 1)
        skill = t.get("skill", "GENERAL")
        obs = "PASS" if t.get("observation", 0) == 1 else "FAIL"
        scaffold = f"L{t.get('scaffolding_level', 0)}"
        post = f"{t.get('bkt_posterior', 0.0):.2f}"
        lat = f"{t.get('latency_ms', 0):,}ms"
        flags = ", ".join(t.get("proctor_flags", [])) or "None"
        q_snippet = t.get("question", "")[:45] + ("..." if len(t.get("question", "")) > 45 else "")
        turn_rows.append(f"| {t_idx:>2} | `{skill}` | {q_snippet:<48} | {obs} | {scaffold} | {post} | {lat} | {flags} |")
    turn_table = "\n".join(turn_rows) if turn_rows else "| - | No turns logged | - | - | - | - | - | - |"

    # Format CPF Bar Graph
    cpf = scoring["cpf"]
    def _bar(val: float) -> str:
        filled = int(val * 20)
        return "█" * filled + "░" * (20 - filled) + f" ({val:.2f})"

    report = f"""# Socratic Interview Engine — Forensic Technical Audit Report

**Session ID:** `{session_id}`  
**Candidate:** {candidate_name} ({seniority_level})  
**Evaluation Timestamp:** {timestamp_str}  
**Proctor Integrity Status:** {'VERIFIED' if proctor_bii >= 0.70 else '⚠️ FLAGGED FOR REVIEW'} (BII: {proctor_bii:.2f})

---

## 1. Hiring Verdict & Composite Score

FINAL VERDICT: [{scoring['verdict']}] MASTER COMPOSITE SCORE: {scoring['final_score']} / 100.0 [{scoring['badge_color']}]
Base Technical Mastery: {scoring['base_technical'] * 100:.1f}%
Scaffolding Multiplier: {scoring['scaffold_multiplier']:.3f} (Penalty for {scoring['total_scaffold_units']} scaffold hint units)
Proctor Integrity (BII): {scoring['bii_multiplier']:.3f}
Adversarial Multiplier: {scoring['adversarial_multiplier']:.3f}

---

## 2. 5D Cognitive Potential Fingerprint (CPF)

| Dimension | Metric | Score Visualization | Interpretation |
|---|:---:|---|---|
| **Breadth** | {cpf['breadth']:.2f} | `{_bar(cpf['breadth'])}` | Scope of technical pillars validated |
| **Depth** | {cpf['depth']:.2f} | `{_bar(cpf['depth'])}` | Mean Bayesian latent mastery across topics |
| **Velocity** | {cpf['velocity']:.2f} | `{_bar(cpf['velocity'])}` | Autonomous problem solving without hints |
| **Rigor** | {cpf['rigor']:.2f} | `{_bar(cpf['rigor'])}` | Resilience under Devil's Advocate scrutiny |
| **Authenticity** | {cpf['authenticity']:.2f} | `{_bar(cpf['authenticity'])}` | Natural conversational integrity & lack of AI jitter |

---

## 3. Bayesian Knowledge Tracing (BKT) Competency Matrix

| Competency Pillar | Latent $P(L)$ | Certification Status |
|---|:---:|---|
{bkt_table}

---

## 4. Multidimensional Item Response Theory (MIRT) Radar

| Technical Dimension | Latent $\\theta$ | Std Error | Global Percentile | Industry Benchmark Tier |
|---|:---:|:---:|:---:|---|
{mirt_table}

---

## 5. Polyglot Ecosystem Audit

* **Primary Runtime Ecosystem:** `{ecosystem_info.get('primary_ecosystem', 'GENERAL_SYSTEMS')}`
* **Detected Ecosystems:** {', '.join(f'`{e}`' for e in ecosystem_info.get('all_ecosystems', []))}
* **Identified Stack Keywords:** {', '.join(f'`{k}`' for k in ecosystem_info.get('stack_keywords', []))}
* **Polyglot Multi-Stack Profile:** {'Yes' if ecosystem_info.get('is_polyglot') else 'No'}

---

## 6. Turn-by-Turn Forensic Audit Trail

| Turn | Skill | Question Snippet | Verdict | Level | $P(L)$ | Latency | Proctor Flags |
|:---:|---|---|:---:|:---:|:---:|:---:|---|
{turn_table}

---

*Report generated deterministically by Antigravity Socratic Forensic Engine (v4.0).*
"""
    return report.strip()


# ==============================================================================
# 3. Report 1: Student Career Compass & Growth Report (LLM Mentorship)
# ==============================================================================

async def generate_student_report(
    candidate_name: str,
    seniority_level: str,
    turns_history: List[Dict],
    skills_mastery: Dict[str, float],
    mirt_radar: List[Dict],
    ecosystem_info: Dict[str, Any],
    timeout_seconds: float = 25
) -> str:
    """
    Generates a personalized, constructive Student Career Compass & Growth Report using Gemini.
    Provides targeted mentorship, strengths, blind spots, and a 30-60-90 day learning roadmap.
    Falls back to a rich structured deterministic template if the LLM call times out.
    """
    if _client:
        try:
            # Prepare compact turn transcript for LLM
            turns_summary = []
            for t in turns_history:
                turns_summary.append({
                    "turn": t.get("turn_index", 1),
                    "topic": t.get("skill", "GENERAL"),
                    "question": t.get("question", "")[:200],
                    "candidate_response": t.get("candidate_answer", "")[:300],
                    "verdict": "PASS" if t.get("observation", 0) == 1 else "FAIL",
                    "hints_used": t.get("scaffolding_level", 0)
                })

            prompt = f"""You are Alex, an elite Principal Staff Software Architect and Socratic Mentor.
Write an inspiring, deeply analytical, and actionable 'Student Career Compass & Growth Report' for {candidate_name} ({seniority_level}).

CANDIDATE SESSION DATA:
- Primary Runtime Ecosystem: {ecosystem_info.get('primary_ecosystem', 'GENERAL_SYSTEMS')}
- Stack Keywords: {ecosystem_info.get('stack_keywords', [])}
- Mastered Pillars (BKT P(L)): {json.dumps(skills_mastery)}
- 5D MIRT Engineering Percentiles: {json.dumps(mirt_radar)}
- Turn Interactions: {json.dumps(turns_summary)}

REPORT STRUCTURE (Format in clean, beautiful GitHub Markdown):
# 🧭 Career Compass & Engineering Growth Report
**Prepared for:** {candidate_name} | **Role Level:** {seniority_level}

## 1. Executive Mentorship Summary
A warm, motivating architectural evaluation of their engineering foundation.

## 2. Cognitive Archetype & Engineering Profile
Define their engineering persona (e.g. 'Pragmatic Distributed Systems Builder', 'Resilient Infrastructure Architect') based on their performance and reasoning style.

## 3. Multidimensional Ability Radar (5D Analysis)
Analyze their percentile standing across:
- Algorithms & Complexity
- System Design & Scalability
- Concurrency & Asynchronous Streaming
- Database Internals & ACID Transactions
- Distributed Consensus & Fault Tolerance

## 4. Top 3 Demonstrated Strengths
Highlight 3 concrete areas where they excelled, referencing specific answers and choices they made during the interview.

## 5. High-Impact Architectural Growth Areas
Constructively unpack 2-3 technical edge-cases or design trade-offs where they required scaffolding hints or showed conceptual gaps.

## 6. Actionable 30-60-90 Day Mastery Roadmap
- **Days 1–30 (Immediate Foundations):** Specific low-level mechanics to internalize.
- **Days 31–60 (Architectural Patterns):** Practical distributed patterns or failure modes to build.
- **Days 61–90 (Staff-Level Frontier):** Production hardening, trade-offs, and scaling bottlenecks.

## 7. Curated Reading List & Benchmark Systems
Recommend 3-4 specific technical papers, books (e.g. DDIA, Kleppmann, Martin Fowler), or production open-source codebases to study.

Keep the tone encouraging, technical, precise, and devoid of corporate clichés.
"""

            # Run LLM call with zero thinking budget for quick execution
            config = types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=2500,
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            )

            response = await asyncio.wait_for(
                _client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[prompt],
                    config=config
                ),
                timeout=timeout_seconds
            )

            if response and response.text:
                return response.text.strip()

        except asyncio.TimeoutError:
            print(f"[Student Report Warning] LLM generation timed out (> {timeout_seconds}s). Using deterministic fallback.")
        except Exception as e:
            print(f"[Student Report Warning] LLM generation failed ({e}). Using deterministic fallback.")


    # Deterministic Fallback Report
    return _generate_student_report_fallback(candidate_name, seniority_level, skills_mastery, mirt_radar, ecosystem_info)


def _generate_student_report_fallback(
    candidate_name: str,
    seniority_level: str,
    skills_mastery: Dict[str, float],
    mirt_radar: List[Dict],
    ecosystem_info: Dict[str, Any]
) -> str:
    """Rich structured fallback report when LLM is offline or timed out."""
    top_skills = [s for s, m in skills_mastery.items() if m >= 0.70]
    growth_skills = [s for s, m in skills_mastery.items() if m < 0.70]

    top_str = "\n".join(f"- **{s.replace('_', ' ').title()}**: Demonstrated solid baseline principles." for s in top_skills) or "- Fundamental architectural foundations demonstrated."
    growth_str = "\n".join(f"- **{s.replace('_', ' ').title()}**: Deepen intuition on edge-case failure modes and consistency trade-offs." for s in growth_skills) or "- Continue advancing into Staff-level distributed systems frontiers."

    return f"""# 🧭 Career Compass & Engineering Growth Report

**Prepared for:** {candidate_name}  
**Level:** {seniority_level}  
**Runtime Ecosystem:** `{ecosystem_info.get('primary_ecosystem', 'GENERAL_SYSTEMS')}`  
**Date:** {datetime.now().strftime('%B %d, %Y')}

---

## 1. Executive Mentorship Summary
Welcome to your personalized technical diagnostic report. During this Socratic session, you engaged with core architectural challenges across distributed systems, concurrency, and persistence. This report highlights your strongest design instincts and provides an engineering roadmap to accelerate your path toward Staff-level excellence.

---

## 2. Cognitive Archetype & Engineering Profile
* **Archetype:** **Pragmatic Systems Architect**
* **Technical DNA:** You demonstrate sound engineering instincts when analyzing high-level components. You prioritize practical, production-viable solutions before optimizing prematurely.

---

## 3. Multidimensional Ability Profile (5D Radar)

| Technical Dimension | Global Percentile | Industry Benchmark Tier |
|---|:---:|---|
{chr(10).join(f"| {m['dimension']} | {m['percentile']}% | {m['tier']} |" for m in mirt_radar)}

---

## 4. Key Demonstrated Strengths
{top_str}

---

## 5. High-Impact Architectural Growth Areas
{growth_str}

---

## 6. Actionable 30-60-90 Day Mastery Roadmap

* **Days 1–30 (Foundations & Latency):** Study low-level lock contention, asynchronous runtime schedulers, and connection pooling behavior under load spikes.
* **Days 31–60 (Distributed Failure Modes):** Build and simulate split-brain recovery, poison-pill consumer dead-lettering, and distributed cache stampede mitigation.
* **Days 61–90 (Staff-Level Frontier):** Benchmark consensus protocols (Raft/Paxos) and write formal failure-mode analyses for high-throughput distributed architectures.

---

## 7. Curated Resources
1. *Designing Data-Intensive Applications* — Martin Kleppmann
2. *Database Internals* — Alex Petrov
3. *System Design Interview Vol. 1 & 2* — Alex Xu

*(Generated via Socratic Engineering Mentorship Engine fallback)*
"""


# ==============================================================================
# 4. Report Persistence Helper
# ==============================================================================

def save_reports_to_disk(
    session_id: str,
    student_report: str,
    evaluator_report: str,
    output_dir: str = "reports"
) -> Dict[str, str]:
    """Saves both generated reports to local markdown files in the reports directory."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    student_path = os.path.join(output_dir, f"student_career_compass_{session_id}_{timestamp}.md")
    evaluator_path = os.path.join(output_dir, f"evaluator_forensic_audit_{session_id}_{timestamp}.md")

    with open(student_path, "w", encoding="utf-8") as f:
        f.write(student_report)

    with open(evaluator_path, "w", encoding="utf-8") as f:
        f.write(evaluator_report)

    return {
        "student_report_path": student_path,
        "evaluator_report_path": evaluator_path
    }
