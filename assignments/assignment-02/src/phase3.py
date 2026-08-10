# phase3.py - Application Advisor
# Takes a new job posting PDF and produces a comprehensive application report
# Usage: python src/phase3.py path/to/posting.pdf
# Debug: DEBUG=true python src/phase3.py path/to/posting.pdf

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from tools import (
    read_file, web_search, whois_lookup,
    call_llm_structured, call_llm_text,
    client, log, DEBUG,
    SEARCH_TOOL, WHOIS_TOOL, execute_tool
)
from schemas import JobPosting, ApplicationReport, LegitimacyAssessment

TODAY = datetime.now().strftime("%Y-%m-%d")


# ─────────────────────────────────────────────
# EXTRACT NEW JOB POSTING
# ─────────────────────────────────────────────

def extract_posting(pdf_path: str) -> JobPosting:
    """Extracts structured data from the new job posting."""
    print(f"📄 Reading job posting: {pdf_path}")
    text = read_file(pdf_path)

    if text.startswith("Error"):
        print(f"❌ Could not read posting: {text}")
        sys.exit(1)

    log(f"Posting text: {len(text)} chars")

    system_prompt = f"""You are a job posting analyzer. Today is {TODAY}.
Extract all fields accurately. Use null for missing fields.
For slug: use format job-title-company (lowercase, hyphens only)."""

    result = call_llm_structured(
        system_prompt,
        f"Extract this job posting:\n\n{text[:7000]}",
        JobPosting,
    )

    log(f"Extracted: {result.job_title} at {result.company_name}")
    return result


# ─────────────────────────────────────────────
# LEGITIMACY AGENT
# ─────────────────────────────────────────────
def run_legitimacy_agent(posting: JobPosting, posting_text: str) -> LegitimacyAssessment:
    """
    Runs the legitimacy agent to check if the posting is real.
    Uses web search and WHOIS lookup tools.
    """
    print("\n🔒 Running legitimacy assessment...")

    system_prompt = f"""You are a job posting legitimacy investigator. Today is {TODAY}.

Your job is to determine if a job posting is legitimate or potentially fraudulent.

Investigate using these tools:
1. web_search - Search for the company, check if they exist, find their careers page
2. whois_lookup - Check when the company domain was registered

RED FLAGS to look for:
- Company has no web presence or very recent domain registration
- Job asks for SSN, banking info, or copies of ID upfront
- Contact email doesn't match company domain (e.g., gmail instead of company email)
- Compensation dramatically above market rate
- Job not listed on company's official careers page
- Very vague job description
- Requires upfront payment or equipment purchase

GREEN FLAGS:
- Company has established web presence and history
- Domain registered years ago (WHOIS check)
- Job listed on official careers page
- Contact email matches company domain
- Salary consistent with market rates
- Specific, detailed requirements

Be thorough — do at least 3-4 searches before making your assessment.
Never fabricate information. If you can't verify something, say so."""

    company = posting.company_name.lower().replace(" ", "")
    domain_guess = f"{company}.com"

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"""Investigate this job posting for legitimacy:

Company: {posting.company_name}
Job Title: {posting.job_title}
Location: {posting.location}
Salary: {posting.salary_range or 'not listed'}

Full posting text:
{posting_text[:3000]}

Please investigate thoroughly using the available tools."""
        }
    ]

    max_iterations = 8
    for i in range(max_iterations):
        log(f"Legitimacy agent iteration {i+1}")

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=messages,
            tools=[SEARCH_TOOL, WHOIS_TOOL],
            temperature=0.1,
        )

        msg = response.choices[0].message

        if not msg.tool_calls:
            break

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
            log(f"Legitimacy: {fn_name}({fn_args})")
            result = execute_tool(fn_name, fn_args)
            log(f"Tool returned {len(result)} chars")

            if fn_name == "whois_lookup":
                log(f"WHOIS: {result[:200]}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    research = "\n".join([
        m["content"]
        for m in messages
        if isinstance(m, dict) and m.get("role") == "tool"
    ])

    structured_prompt = """Extract a structured legitimacy assessment based on the research.
Be honest — if you couldn't verify something, say so in the signals."""

    structured_message = f"""Company: {posting.company_name}
Job: {posting.job_title}

Research findings:
{research[:4000]}

Produce a structured legitimacy assessment."""

    result = call_llm_structured(
        structured_prompt,
        structured_message,
        LegitimacyAssessment,
    )

    log(f"Legitimacy verdict: {result.verdict} (confidence: {result.confidence})")
    for signal in result.signals:
        log(f"Legitimacy signal: [{signal.type}] {signal.signal}")

    return result


# ─────────────────────────────────────────────
# GENERATE APPLICATION REPORT
# ─────────────────────────────────────────────

def generate_application_report(
    posting: JobPosting,
    legitimacy: LegitimacyAssessment,
    resume_data: dict,
    gap_analysis: dict,
    market_analysis: dict,
) -> ApplicationReport:
    """Generates the full application report with fit score and advice."""
    print("\n📊 Generating application report...")

    system_prompt = f"""You are an expert career advisor. Today is {TODAY}.

Analyze how well the candidate fits this job posting and provide:
1. A fit score (0-100%) with breakdown
2. Specific resume adaptation suggestions
3. Cover letter key points
4. Interview prep advice

FIT SCORING GUIDELINES - be encouraging:
- 80%+: Strong fit, definitely apply
- 50-80%: Good fit, apply and highlight strengths
- 30-50%: Stretch, worth applying if excited about role
- Below 30%: Growth target

Never just say "don't apply" for a reasonable match.
Job postings describe ideal candidates, not minimum requirements."""

    user_message = f"""Job Posting:
{json.dumps(posting.model_dump(), indent=2)[:3000]}

Candidate Resume:
{json.dumps(resume_data, indent=2)[:3000]}

Market Context:
{json.dumps(market_analysis, indent=2)[:2000]}

Gap Analysis:
{json.dumps(gap_analysis, indent=2)[:2000]}

Legitimacy Assessment:
{json.dumps(legitimacy.model_dump(), indent=2)}

Generate a comprehensive application report."""

    result = call_llm_structured(
        system_prompt,
        user_message,
        ApplicationReport,
    )

    log(f"Fit score: {result.fit_score.overall_percentage}%")
    log(f"Fit scoring: {len(result.fit_score.matched_requirements)} requirements matched")
    log(f"Fit scoring: {len(result.fit_score.gaps)} gaps identified")
    log(f"Overall fit: {result.fit_score.overall_percentage}% — {result.fit_score.recommendation}")

    return result


# ─────────────────────────────────────────────
# GENERATE HTML REPORT
# ─────────────────────────────────────────────

def generate_html_report(
    posting: JobPosting,
    report: ApplicationReport,
    reports_dir: str
):
    """Generates a beautiful HTML application report."""
    print("\n🎨 Generating HTML report...")

    verdict_colors = {
        "legitimate": "#28a745",
        "caution": "#ffc107",
        "suspicious": "#fd7e14",
        "fraudulent": "#dc3545",
    }
    verdict_color = verdict_colors.get(report.legitimacy.verdict, "#6c757d")

    fit_pct = report.fit_score.overall_percentage
    if fit_pct >= 80:
        fit_color = "#28a745"
        fit_label = "Strong Fit"
    elif fit_pct >= 50:
        fit_color = "#17a2b8"
        fit_label = "Good Fit"
    elif fit_pct >= 30:
        fit_color = "#ffc107"
        fit_label = "Stretch"
    else:
        fit_color = "#6c757d"
        fit_label = "Growth Target"

    red_flags = [s for s in report.legitimacy.signals if s.type == "red_flag"]
    green_flags = [s for s in report.legitimacy.signals if s.type == "green_flag"]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Application Report — {posting.job_title} at {posting.company_name}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8f9fa; color: #333; }}
  .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 40px; }}
  .header h1 {{ font-size: 2rem; margin-bottom: 8px; }}
  .header p {{ opacity: 0.8; font-size: 1.1rem; }}
  .container {{ max-width: 900px; margin: 30px auto; padding: 0 20px; }}
  .card {{ background: white; border-radius: 12px; padding: 30px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  .card h2 {{ font-size: 1.3rem; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #f0f0f0; }}
  .badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; color: white; }}
  .verdict-badge {{ background: {verdict_color}; font-size: 1rem; padding: 8px 20px; }}
  .fit-badge {{ background: {fit_color}; font-size: 1rem; padding: 8px 20px; }}
  .signal {{ padding: 10px 14px; border-radius: 8px; margin-bottom: 8px; font-size: 0.9rem; }}
  .red-flag {{ background: #fff5f5; border-left: 4px solid #dc3545; }}
  .green-flag {{ background: #f0fff4; border-left: 4px solid #28a745; }}
  .signal strong {{ display: block; margin-bottom: 4px; }}
  .signal .evidence {{ color: #666; font-size: 0.85rem; }}
  .fit-bar {{ background: #e9ecef; border-radius: 10px; height: 20px; margin: 15px 0; overflow: hidden; }}
  .fit-fill {{ height: 100%; border-radius: 10px; background: {fit_color}; width: {fit_pct}%; transition: width 0.5s; }}
  .fit-pct {{ font-size: 2.5rem; font-weight: 700; color: {fit_color}; }}
  ul {{ padding-left: 20px; }}
  li {{ margin-bottom: 8px; line-height: 1.5; }}
  .matched {{ color: #28a745; }}
  .gap {{ color: #dc3545; }}
  .section-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
  .warning-banner {{ background: #fff3cd; border: 2px solid #ffc107; border-radius: 8px; padding: 16px; margin-bottom: 20px; }}
  .danger-banner {{ background: #f8d7da; border: 2px solid #dc3545; border-radius: 8px; padding: 16px; margin-bottom: 20px; }}
  .tag {{ display: inline-block; background: #e9ecef; border-radius: 4px; padding: 2px 8px; font-size: 0.8rem; margin: 2px; }}
  .footer {{ text-align: center; color: #999; padding: 30px; font-size: 0.85rem; }}
  @media (max-width: 600px) {{ .section-grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>

<div class="header">
  <h1>Application Report</h1>
  <p>{posting.job_title} at {posting.company_name}</p>
  <p style="margin-top: 8px; opacity: 0.6; font-size: 0.9rem;">Generated {TODAY} | {posting.location}</p>
</div>

<div class="container">

  <!-- LEGITIMACY SECTION -->
  <div class="card">
    <h2>🔒 Legitimacy Assessment</h2>
    {"<div class='danger-banner'>⚠️ <strong>Warning:</strong> This posting shows signs of being fraudulent. Do NOT submit personal information.</div>" if report.legitimacy.verdict == "fraudulent" else ""}
    {"<div class='warning-banner'>⚠️ <strong>Caution:</strong> We could not fully verify this posting. Proceed carefully.</div>" if report.legitimacy.verdict in ["suspicious", "caution"] else ""}
    
    <div style="margin-bottom: 20px;">
      <span class="badge verdict-badge">{report.legitimacy.verdict.upper()}</span>
      <span style="margin-left: 10px; color: #666;">Confidence: {report.legitimacy.confidence}</span>
    </div>
    
    <p style="margin-bottom: 20px; line-height: 1.6;">{report.legitimacy.recommendation}</p>
    
    <div class="section-grid">
      <div>
        <h3 style="color: #dc3545; margin-bottom: 10px;">🚩 Red Flags</h3>
        {"".join([f'<div class="signal red-flag"><strong>{s.signal}</strong><span class="evidence">{s.evidence}</span></div>' for s in red_flags]) or "<p style='color:#999'>No red flags found</p>"}
      </div>
      <div>
        <h3 style="color: #28a745; margin-bottom: 10px;">✅ Green Flags</h3>
        {"".join([f'<div class="signal green-flag"><strong>{s.signal}</strong><span class="evidence">{s.evidence}</span></div>' for s in green_flags]) or "<p style='color:#999'>No green flags found</p>"}
      </div>
    </div>
  </div>

  <!-- FIT ASSESSMENT -->
  <div class="card">
    <h2>📊 Fit Assessment</h2>
    <div style="text-align: center; margin-bottom: 20px;">
      <div class="fit-pct">{fit_pct:.0f}%</div>
      <span class="badge fit-badge">{fit_label}</span>
    </div>
    <div class="fit-bar"><div class="fit-fill"></div></div>
    <p style="margin: 15px 0; line-height: 1.6;">{report.fit_score.reasoning}</p>
    <p style="font-weight: 600; margin-bottom: 10px;">Recommendation: {report.fit_score.recommendation}</p>
    
    <div class="section-grid" style="margin-top: 20px;">
      <div>
        <h3 class="matched" style="margin-bottom: 10px;">✅ You Match</h3>
        <ul>{"".join([f'<li class="matched">{r}</li>' for r in report.fit_score.matched_requirements])}</ul>
      </div>
      <div>
        <h3 class="gap" style="margin-bottom: 10px;">❌ Gaps</h3>
        <ul>{"".join([f'<li class="gap">{g}</li>' for g in report.fit_score.gaps])}</ul>
      </div>
    </div>
  </div>

  <!-- RESUME ADAPTATIONS -->
  <div class="card">
    <h2>📝 Resume Adaptations</h2>
    <p style="color: #666; margin-bottom: 15px;">Specific changes to tailor your resume for this role:</p>
    <ul>{"".join([f'<li style="margin-bottom: 10px;">{a}</li>' for a in report.resume_adaptations])}</ul>
  </div>

  <!-- COVER LETTER -->
  <div class="card">
    <h2>✉️ Cover Letter Guidance</h2>
    <p style="color: #666; margin-bottom: 15px;">Key points to hit in your cover letter:</p>
    <ul>{"".join([f'<li style="margin-bottom: 10px;">{p}</li>' for p in report.cover_letter_points])}</ul>
  </div>

  <!-- INTERVIEW PREP -->
  <div class="card">
    <h2>🎯 Interview Preparation</h2>
    
    <h3 style="margin-bottom: 10px;">Likely Interview Questions</h3>
    <ul style="margin-bottom: 20px;">{"".join([f'<li style="margin-bottom: 8px;">{q}</li>' for q in report.interview_questions])}</ul>
    
    <h3 style="margin-bottom: 10px;">Skills to Brush Up On</h3>
    <div style="margin-bottom: 20px;">{"".join([f'<span class="tag">{s}</span>' for s in report.skills_to_brush_up])}</div>
    
    <h3 style="margin-bottom: 10px;">Research Before Your Interview</h3>
    <ul>{"".join([f'<li style="margin-bottom: 8px;">{r}</li>' for r in report.company_research_points])}</ul>
  </div>

</div>

<div class="footer">
  <p>Generated by Job Search Assistant | {TODAY}</p>
  <p style="margin-top: 4px;">This report is AI-generated. Always verify information independently.</p>
</div>

</body>
</html>"""

    report_path = os.path.join(reports_dir, "application-report.html")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"   ✅ Saved reports/application-report.html")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python src/phase3.py <path_to_posting.pdf>")
        print("Example: python src/phase3.py input/new-posting.pdf")
        sys.exit(1)

    posting_path = sys.argv[1]
    if not os.path.exists(posting_path):
        print(f"❌ Posting file not found: {posting_path}")
        sys.exit(1)

    root = os.path.join(os.path.dirname(__file__), "..")
    analysis_dir = os.path.join(root, "data", "analysis")
    reports_dir = os.path.join(root, "reports")

    print("🚀 Phase 3: Application Advisor")
    print("=" * 50)

    if DEBUG:
        print("[DEBUG MODE ON]", file=sys.stderr)

    # Load Phase 1 and 2 data
    market_path = os.path.join(analysis_dir, "market-analysis.json")
    gap_path = os.path.join(analysis_dir, "gap-analysis.json")
    resume_path = os.path.join(root, "data", "resume", "resume.json")

    if not os.path.exists(market_path):
        print("❌ Market analysis not found. Run Phase 1 first!")
        sys.exit(1)
    if not os.path.exists(gap_path):
        print("❌ Gap analysis not found. Run Phase 2 first!")
        sys.exit(1)
    if not os.path.exists(resume_path):
        print("❌ Resume data not found. Run Phase 2 first!")
        sys.exit(1)

    with open(market_path) as f:
        market_analysis = json.load(f)
    with open(gap_path) as f:
        gap_analysis = json.load(f)
    with open(resume_path) as f:
        resume_data = json.load(f)

    print("✅ Loaded Phase 1 and 2 data")

    # Extract the new posting
    posting = extract_posting(posting_path)
    posting_text = read_file(posting_path)

    # Run legitimacy agent
    legitimacy = run_legitimacy_agent(posting, posting_text)
    print(f"   Verdict: {legitimacy.verdict} (confidence: {legitimacy.confidence})")

    # Generate application report
    report = generate_application_report(
        posting, legitimacy, resume_data, gap_analysis, market_analysis
    )

    # Generate HTML report
    generate_html_report(posting, report, reports_dir)

    print("\n🎉 Phase 3 complete!")
    print(f"   📊 Report: reports/application-report.html")
    print(f"   🌐 Open in browser to view!")


if __name__ == "__main__":
    main()