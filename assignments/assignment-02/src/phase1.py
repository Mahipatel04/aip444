# phase1.py - Job Market Analysis
# Processes job posting PDFs, extracts structured data, researches companies,
# and produces a market analysis report
# Usage: python src/phase1.py
# Debug: DEBUG=true python src/phase1.py

import os
import sys
import json
import glob
from datetime import datetime

# Add parent dir to path so we can import from src/
sys.path.insert(0, os.path.dirname(__file__))

from tools import (
    read_file, web_search, call_llm_structured,
    call_llm_text, client, log, DEBUG,
    SEARCH_TOOL, execute_tool
)
from schemas import JobPosting, MarketAnalysis

TODAY = datetime.now().strftime("%Y-%m-%d")


# ─────────────────────────────────────────────
# EXTRACT JOB POSTING
# ─────────────────────────────────────────────

def extract_job_posting(pdf_path: str) -> JobPosting:
    """
    Extracts structured data from a job posting PDF.
    Uses tool calling to research the company.
    """
    filename = os.path.basename(pdf_path)
    log(f"Extracting posting: {filename}")

    # Read the PDF
    text = read_file(pdf_path)
    if text.startswith("Error"):
        raise ValueError(f"Could not read {pdf_path}: {text}")

    log(f"PDF text length: {len(text)} chars")

    # First pass: extract basic info with tool calling for company research
    system_prompt = f"""You are a job posting analyzer. Today's date is {TODAY}.

Extract structured data from the job posting. Use the web_search tool to research
the company — look for company size, industry, recent news, and culture signals.

When calculating posting_age_days:
- If the posting has an exact date, calculate days from that date to today ({TODAY})
- If it shows "Posted X days ago", use X as the age
- If no date information, set to null

For slug: create a URL-friendly identifier like "senior-dev-acme-corp" from the job title and company.

Be precise — if a field is not mentioned, use null or "not listed" rather than guessing."""

    user_message = f"""Please extract and analyze this job posting:

{text[:8000]}"""

    # Use tool calling loop for company research
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]

    max_iterations = 5
    for i in range(max_iterations):
        log(f"LLM iteration {i+1} for {filename}")

        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=messages,
            tools=[SEARCH_TOOL],
            temperature=0.1,
        )

        msg = response.choices[0].message

        if not msg.tool_calls:
            # Got final response — now parse it into structured output
            break

# Handle tool calls
        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments
                }
            } for tc in msg.tool_calls
        ]})
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
# Get research context
    research_context = "\n".join([
        m["content"] if isinstance(m, dict) and m.get("role") == "tool" else ""
        for m in messages
        if isinstance(m, dict) and m.get("role") == "tool"
    ])

    structured_prompt = f"""You are a job posting data extractor. Today's date is {TODAY}.

Based on the job posting text and research below, extract all fields accurately.
For slug use format: job-title-company-name (lowercase, hyphens, no special chars)
For posting_age_days: calculate from posting date to {TODAY}. Use null if unknown."""

    structured_message = f"""Job posting text:
{text[:6000]}

Company research findings:
{research_context[:2000]}

Extract all fields now."""

    result = call_llm_structured(
        structured_prompt,
        structured_message,
        JobPosting,
    )

    log(f"Extracted {len(result.required_skills)} required skills, {len(result.preferred_skills)} preferred skills")
    if result.salary_range:
        log(f"Salary: {result.salary_range}")
    else:
        log("Salary field: not found in posting")

    return result


# ─────────────────────────────────────────────
# PROCESS ALL POSTINGS
# ─────────────────────────────────────────────

def process_all_postings(jobs_input_dir: str, jobs_output_dir: str) -> list:
    """
    Processes all PDF job postings in the input directory.
    Skips postings that have already been processed.
    """
    pdf_files = glob.glob(os.path.join(jobs_input_dir, "*.pdf"))

    if not pdf_files:
        print(f"❌ No PDF files found in {jobs_input_dir}")
        print("   Drop your job posting PDFs into the input/jobs/ folder")
        sys.exit(1)

    print(f"📂 Found {len(pdf_files)} job posting PDFs")
    all_postings = []

    for pdf_path in pdf_files:
        filename = os.path.basename(pdf_path)
        name_without_ext = os.path.splitext(filename)[0]

        # Check if already processed
        existing_json = os.path.join(jobs_output_dir, f"{name_without_ext}.json")
        if os.path.exists(existing_json):
            print(f"   ⏭️  Skipping {filename} (already processed)")
            with open(existing_json, "r", encoding="utf-8") as f:
                all_postings.append(json.load(f))
            continue

        print(f"   🔄 Processing {filename}...")
        try:
            posting = extract_job_posting(pdf_path)

            # Save to JSON
            posting_dict = posting.model_dump()
            output_path = os.path.join(jobs_output_dir, f"{name_without_ext}.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(posting_dict, f, indent=2)

            print(f"   ✅ Saved: {name_without_ext}.json")
            log(f"Saved posting data to {output_path}")
            all_postings.append(posting_dict)

        except Exception as e:
            print(f"   ❌ Failed to process {filename}: {e}")
            log(f"Error processing {filename}: {e}")

    return all_postings


# ─────────────────────────────────────────────
# GENERATE MARKET ANALYSIS
# ─────────────────────────────────────────────

def generate_market_analysis(postings: list, output_dir: str) -> MarketAnalysis:
    """
    Aggregates all job postings into a market analysis.
    """
    print(f"\n📊 Generating market analysis from {len(postings)} postings...")

    system_prompt = """You are a job market analyst. Analyze the provided job postings
and identify patterns, trends, and insights across all of them.

Be specific and data-driven. Count actual occurrences of skills across postings.
Calculate percentages based on total number of postings."""

    user_message = f"""Analyze these {len(postings)} job postings and identify market trends:

{json.dumps(postings, indent=2)[:12000]}

Provide a comprehensive market analysis."""

    analysis = call_llm_structured(
        system_prompt,
        user_message,
        MarketAnalysis,
    )

    # Save structured data
    analysis_path = os.path.join(output_dir, "market-analysis.json")
    with open(analysis_path, "w", encoding="utf-8") as f:
        json.dump(analysis.model_dump(), f, indent=2)
    print(f"   ✅ Saved market-analysis.json")

    return analysis


# ─────────────────────────────────────────────
# GENERATE MARKET REPORT
# ─────────────────────────────────────────────

def generate_market_report(analysis: MarketAnalysis, postings: list, reports_dir: str):
    """Generates a human-readable markdown market analysis report."""
    print("\n📝 Generating market analysis report...")

    system_prompt = """You are a job market analyst writing a detailed report for a job seeker.
Write in clear, actionable language. Include specific numbers and examples.
Format as professional Markdown with headers, tables, and bullet points."""

    user_message = f"""Write a comprehensive market analysis report based on this data:

Market Analysis Data:
{json.dumps(analysis.model_dump(), indent=2)}

Number of postings analyzed: {len(postings)}
Date: {TODAY}

Include:
1. Executive Summary
2. Top Skills Required (with frequency table)
3. Experience & Education Trends
4. Salary Insights
5. Company & Industry Landscape
6. Key Observations & Recommendations for job seekers"""

    report = call_llm_text(system_prompt, user_message)

    report_path = os.path.join(reports_dir, "market-analysis.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Job Market Analysis Report\n")
        f.write(f"*Generated: {TODAY} | Postings Analyzed: {len(postings)}*\n\n")
        f.write(report)

    print(f"   ✅ Saved reports/market-analysis.md")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    # Set up paths relative to assignment-02 root
    root = os.path.join(os.path.dirname(__file__), "..")
    jobs_input_dir = os.path.join(root, "input", "jobs")
    jobs_output_dir = os.path.join(root, "data", "jobs")
    analysis_dir = os.path.join(root, "data", "analysis")
    reports_dir = os.path.join(root, "reports")

    # Create input directory if it doesn't exist
    os.makedirs(jobs_input_dir, exist_ok=True)
    os.makedirs(jobs_output_dir, exist_ok=True)
    os.makedirs(analysis_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    print("🚀 Phase 1: Job Market Analysis")
    print("=" * 50)

    if DEBUG:
        print("[DEBUG MODE ON]", file=sys.stderr)

    # Process all job postings
    postings = process_all_postings(jobs_input_dir, jobs_output_dir)

    if not postings:
        print("❌ No postings were processed successfully")
        sys.exit(1)

    print(f"\n✅ Processed {len(postings)} postings total")

    # Generate market analysis
    analysis = generate_market_analysis(postings, analysis_dir)

    # Generate market report
    generate_market_report(analysis, postings, reports_dir)

    print("\n🎉 Phase 1 complete!")
    print(f"   📁 Job data: data/jobs/")
    print(f"   📊 Analysis: data/analysis/market-analysis.json")
    print(f"   📝 Report: reports/market-analysis.md")


if __name__ == "__main__":
    main()