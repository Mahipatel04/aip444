
# judge.py - The "Lead Developer" who synthesizes both reviews
# into a single beautiful HTML report.
# The judge reads both JSON reports, removes duplicates,
# filters bad suggestions, and writes the final HTML output.

import os
import sys
from openai import OpenAI

# Set up OpenAI client pointing to OpenRouter
client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

MODEL = "openai/gpt-4o-mini"

JUDGE_PROMPT = """
You are the "Lead Developer" — an extremely experienced, pragmatic, and empathetic
senior engineer with 20+ years of experience. You are reviewing the findings of two
junior code reviewers and producing the final official code review report.

## Your Job
You will receive two JSON arrays of issues:
1. From "The Security Auditor" — focused on security vulnerabilities
2. From "The Performance Optimizer" — focused on performance issues

Your job is to:
1. DE-DUPLICATE: If both reviewers flagged the same issue, merge them into one
2. FILTER: Remove hallucinations, nitpicks, or issues that are too minor to act on
3. CLARIFY: Rewrite any confusing descriptions in plain, actionable English
4. RESOLVE: If reviewers disagree, use your judgment to decide what's correct
5. PRIORITIZE: Order issues from most critical to least critical
6. FORMAT: Produce a beautiful HTML report

## Output Format
Produce a complete, beautiful HTML report (HTML + CSS in a single file).
The report should:
- Have a clean, modern design with a professional color scheme
- Use a dark header with the title "AI Code Review Report"
- Show a summary section with total issues count by severity
- List each issue in a card with: severity badge, file path, line number, category, description
- Color code severity: red for critical, orange for warn, blue for info
- Be fully self-contained (no external CSS or JS files needed)
- Look like something a professional team would actually use

## Severity Colors
- critical: red background badge (#dc3545)
- warn: orange background badge (#fd7e14)
- info: blue background badge (#0d6efd)

## Example Card Layout
Each issue should look like a card with:
- Left colored border matching severity
- Severity badge in top right
- File path and line number
- Category tag
- Description text

## Rules
- Output ONLY the HTML, no other text before or after
- Make it beautiful — use proper CSS, spacing, and typography
- Do not include issues that are clearly wrong or hallucinated
- If there are no real issues, say so clearly in the report
""".strip()


def run_judge(security_issues: list, performance_issues: list, debug: bool = False) -> str:
    """
    Runs the Lead Developer judge to synthesize both reviews
    into a final HTML report.
    Returns the HTML string.
    """
    if debug:
        print("\n[Judge] Starting synthesis...", file=sys.stderr)
        print(f"[Judge] Security issues: {len(security_issues)}", file=sys.stderr)
        print(f"[Judge] Performance issues: {len(performance_issues)}", file=sys.stderr)

    import json

    # Build the user message with both JSON reports
    user_message = f"""
Please synthesize these two code review reports into a final HTML report.

## Security Auditor Findings:
```json
{json.dumps(security_issues, indent=2)}
```

## Performance Optimizer Findings:
```json
{json.dumps(performance_issues, indent=2)}
```

Produce the final HTML report now.
""".strip()

    if debug:
        print("[Judge] Calling LLM...", file=sys.stderr)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": JUDGE_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
    )

    html_report = response.choices[0].message.content

    # Clean up in case model wrapped it in markdown
    html_report = html_report.strip()
    if html_report.startswith("```"):
        parts = html_report.split("```")
        if len(parts) >= 2:
            html_report = parts[1]
            if html_report.startswith("html"):
                html_report = html_report[4:]
    html_report = html_report.strip()

    if debug:
        print(f"[Judge] HTML report generated ({len(html_report)} characters)", file=sys.stderr)

    return html_report