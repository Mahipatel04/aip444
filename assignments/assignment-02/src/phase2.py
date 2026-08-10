# phase2.py - Resume Gap Analysis
# Parses your resume, compares to market analysis, produces gap report
# Usage: python src/phase2.py path/to/resume.pdf
# Debug: DEBUG=true python src/phase2.py path/to/resume.pdf

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from tools import (
    read_file, web_search, call_llm_structured,
    call_llm_text, client, log, DEBUG,
    SEARCH_TOOL, execute_tool
)
from schemas import ResumeData, GapAnalysis

TODAY = datetime.now().strftime("%Y-%m-%d")


# ─────────────────────────────────────────────
# EXTRACT RESUME DATA
# ─────────────────────────────────────────────

def extract_resume(resume_path: str) -> ResumeData:
    """Extracts structured data from a resume PDF or Word file."""
    print(f"📄 Reading resume: {resume_path}")

    text = read_file(resume_path)
    if text.startswith("Error"):
        print(f"❌ Could not read resume: {text}")
        sys.exit(1)

    log(f"Resume text length: {len(text)} chars")

    system_prompt = """You are a resume parser. Extract all information from the resume
into structured categories that align with how hiring managers evaluate candidates.

Be thorough — extract every skill, technology, tool, and keyword mentioned.
For total_years_experience: estimate based on work history dates."""

    user_message = f"""Extract all information from this resume:

{text[:8000]}"""

    result = call_llm_structured(system_prompt, user_message, ResumeData)

    log(f"Extracted {len(result.hard_skills)} hard skills")
    log(f"Extracted {len(result.work_experience)} work experiences")
    log(f"Estimated experience: {result.total_years_experience} years")

    return result


# ─────────────────────────────────────────────
# PERFORM GAP ANALYSIS
# ─────────────────────────────────────────────

def perform_gap_analysis(
    resume: ResumeData,
    market_analysis: dict,
    gap_output_dir: str
) -> GapAnalysis:
    """
    Compares resume against market analysis to identify gaps.
    Uses web search to find specific advice for addressing gaps.
    """
    print("\n🔍 Performing gap analysis...")

    system_prompt = f"""You are a career advisor helping a job seeker understand their gaps.
Today is {TODAY}.

Compare the resume against the market analysis and:
1. Identify strengths (skills that match market demand)
2. Identify gaps (skills missing from resume but common in market)
3. For each gap, use web_search to find SPECIFIC actionable advice
   e.g. search "AWS Cloud Practitioner certification cost time 2026"
4. Triage gaps by difficulty:
   - quick_win: just needs resume wording change
   - short_term: can fix in days/weeks (tutorial, small project)
   - medium_term: weeks to months (learn framework, build project)
   - long_term: months to years (degree, major experience)

Be SPECIFIC — "Get AWS Cloud Practitioner cert (~$300, 20 hours study)" 
NOT "Learn AWS"

Only use web_search for gaps where you need current info on how to address them."""

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"""Resume data:
{json.dumps(resume.model_dump(), indent=2)[:4000]}

Market analysis (what employers want):
{json.dumps(market_analysis, indent=2)[:4000]}

Identify strengths, gaps, and unique value. Search for specific advice on the top gaps."""
        }
    ]

    max_iterations = 8
    for i in range(max_iterations):
        log(f"Gap analysis iteration {i+1}")

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=messages,
            tools=[SEARCH_TOOL],
            temperature=0.2,
        )

        msg = response.choices[0].message

        if not msg.tool_calls:
            break

        # Append assistant message as dict
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                } for tc in msg.tool_calls
            ]
        })

        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            log(f"Tool call: {fn_name}({fn_args})")
            result = execute_tool(fn_name, fn_args)
            log(f"Tool returned {len(result)} chars")
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    # Get research context from tool results only
    research = "\n".join([
        m["content"]
        for m in messages
        if isinstance(m, dict) and m.get("role") == "tool"
    ])

    # Now do structured extraction
    structured_prompt = """Extract the gap analysis into structured format.
Be specific and actionable for every gap identified."""

    structured_message = f"""Resume data:
{json.dumps(resume.model_dump(), indent=2)[:3000]}

Market analysis:
{json.dumps(market_analysis, indent=2)[:3000]}

Research findings:
{research[:3000]}

Extract the complete gap analysis now."""

    result = call_llm_structured(structured_prompt, structured_message, GapAnalysis)

    log(f"Found {len(result.strengths)} strengths")
    log(f"Found {len(result.gaps)} gaps")
    log(f"Found {len(result.unique_value)} unique value points")

    # Save structured data
    gap_path = os.path.join(gap_output_dir, "gap-analysis.json")
    with open(gap_path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, indent=2)
    print(f"   ✅ Saved data/analysis/gap-analysis.json")

    return result

##

def generate_gap_report(
    resume: ResumeData,
    gap_analysis: GapAnalysis,
    market_analysis: dict,
    reports_dir: str
):
    """Generates a human-readable gap analysis report."""
    print("\n📝 Generating gap analysis report...")

    system_prompt = """You are a career advisor writing a gap analysis report.
Write clearly and encouragingly. Be specific and actionable.
Format as professional Markdown."""

    user_message = f"""Write a comprehensive gap analysis report for {resume.full_name}.

Resume Summary:
- Hard skills: {', '.join(resume.hard_skills[:10])}
- Experience: {resume.total_years_experience} years
- Education: {', '.join(resume.education[:3])}

Gap Analysis:
{json.dumps(gap_analysis.model_dump(), indent=2)}

Market Context:
- Top required skills: {json.dumps(market_analysis.get('top_required_skills', [])[:5])}
- Common experience: {market_analysis.get('common_experience_levels', [])}

Write a report with:
1. Executive Summary
2. Your Strengths (what makes you competitive)
3. Gaps by Priority:
   - Quick Wins (fix your resume today)
   - Short-term Actions (weeks)
   - Medium-term Goals (months)
   - Long-term Investments
4. Your Unique Value Proposition
5. Overall Market Readiness Assessment"""

    report = call_llm_text(system_prompt, user_message)

    report_path = os.path.join(reports_dir, "gap-analysis.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Resume Gap Analysis Report\n")
        f.write(f"*Generated: {TODAY} | Candidate: {resume.full_name}*\n\n")
        f.write(report)

    print(f"   ✅ Saved reports/gap-analysis.md")
# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python src/phase2.py <path_to_resume>")
        print("Example: python src/phase2.py input/resume.pdf")
        sys.exit(1)

    resume_path = sys.argv[1]
    if not os.path.exists(resume_path):
        print(f"❌ Resume file not found: {resume_path}")
        sys.exit(1)

    root = os.path.join(os.path.dirname(__file__), "..")
    analysis_dir = os.path.join(root, "data", "analysis")
    reports_dir = os.path.join(root, "reports")
    resume_dir = os.path.join(root, "data", "resume")

    os.makedirs(analysis_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)
    os.makedirs(resume_dir, exist_ok=True)

    print("🚀 Phase 2: Resume Gap Analysis")
    print("=" * 50)

    if DEBUG:
        print("[DEBUG MODE ON]", file=sys.stderr)

    # Load market analysis from Phase 1
    market_path = os.path.join(analysis_dir, "market-analysis.json")
    if not os.path.exists(market_path):
        print("❌ Market analysis not found. Run Phase 1 first!")
        print("   python src/phase1.py")
        sys.exit(1)

    with open(market_path, "r", encoding="utf-8") as f:
        market_analysis = json.load(f)
    print("✅ Loaded market analysis from Phase 1")

    # Extract resume
    resume = extract_resume(resume_path)

    # Save resume data
    resume_path_out = os.path.join(resume_dir, "resume.json")
    with open(resume_path_out, "w", encoding="utf-8") as f:
        json.dump(resume.model_dump(), f, indent=2)
    print(f"   ✅ Saved data/resume/resume.json")

    # Perform gap analysis
    gap_analysis = perform_gap_analysis(resume, market_analysis, analysis_dir)

    # Generate report
    generate_gap_report(resume, gap_analysis, market_analysis, reports_dir)

    print("\n🎉 Phase 2 complete!")
    print(f"   📊 Gap data: data/analysis/gap-analysis.json")
    print(f"   📝 Report: reports/gap-analysis.md")


if __name__ == "__main__":
    main()