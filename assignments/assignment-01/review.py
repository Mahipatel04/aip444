# review.py - Main CLI tool for AI code review
# Usage:
#   Git Mode:  python review.py
#   File Mode: python review.py --file bad_code.py
#   Debug:     python review.py --debug --file bad_code.py
#   Output:    python review.py --file bad_code.py --output report.html

import sys
import os
import asyncio
import argparse
import subprocess
from datetime import datetime

# Load API key before importing reviewers
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

load_env()

from reviewers import run_all_reviewers
from judge import run_judge


# ─────────────────────────────────────────────
# GET INPUT (Git Mode or File Mode)
# ─────────────────────────────────────────────

def get_git_diff(debug: bool = False) -> str:
    """Gets the staged git diff."""
    if debug:
        print("[Main] Running git diff --staged...", file=sys.stderr)

    result = subprocess.run(
        ["git", "diff", "--staged"],
        capture_output=True,
        text=True
    )

    diff = result.stdout.strip()

    if not diff:
        print("❌ No staged changes found.")
        print("   Stage some changes first with: git add <file>")
        sys.exit(1)

    if debug:
        print(f"[Main] Git diff: {len(diff)} characters", file=sys.stderr)

    return diff


def get_file_content(file_path: str, debug: bool = False) -> str:
    """Reads a file from disk for File Mode."""
    if debug:
        print(f"[Main] Reading file: {file_path}", file=sys.stderr)

    if not os.path.exists(file_path):
        print(f"❌ Error: File not found: {file_path}")
        sys.exit(1)

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if not content.strip():
            print(f"❌ Error: File is empty: {file_path}")
            sys.exit(1)

        if debug:
            print(f"[Main] File content: {len(content)} characters", file=sys.stderr)

        return f"# File: {file_path}\n\n{content}"

    except Exception as e:
        print(f"❌ Error reading file: {e}")
        sys.exit(1)


# ─────────────────────────────────────────────
# SAVE OUTPUT
# ─────────────────────────────────────────────

def save_report(html: str, output_path: str, debug: bool = False):
    """Saves the HTML report to a file."""
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n✅ Report saved to: {output_path}")
        if debug:
            print(f"[Main] Report size: {len(html)} characters", file=sys.stderr)
    except Exception as e:
        print(f"❌ Error saving report: {e}")
        sys.exit(1)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="AI Code Review Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python review.py                          # Git Mode (staged changes)
  python review.py --file bad_code.py      # File Mode
  python review.py --debug --file bad_code.py  # Debug Mode
  python review.py --file bad_code.py --output my_report.html  # Custom output
        """
    )
    parser.add_argument("--file", type=str, help="File to review (File Mode)")
    parser.add_argument("--output", type=str, help="Output HTML file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()
    debug = args.debug

    # Generate default output filename if not specified
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now().strftime("%d-%m-%Y-%H-%M-%S")
        output_path = f"review-{timestamp}.html"

    print("🔍 AI Code Review Tool")
    print("=" * 40)

    # Get the code to review
    if args.file:
        print(f"📄 Mode: File Review ({args.file})")
        code_input = get_file_content(args.file, debug)
    else:
        print("📦 Mode: Git Staged Changes")
        code_input = get_git_diff(debug)

    if debug:
        print(f"\n[Main] Debug mode enabled", file=sys.stderr)
        print(f"[Main] Code input: {len(code_input)} characters", file=sys.stderr)

    # Phase 1: Run both reviewers in parallel
    print("\n🤖 Phase 1: Running reviewers in parallel...")
    security_issues, performance_issues = await run_all_reviewers(code_input, debug)

    print(f"   🔒 Security Auditor found: {len(security_issues)} issues")
    print(f"   ⚡ Performance Optimizer found: {len(performance_issues)} issues")

    total = len(security_issues) + len(performance_issues)
    if total == 0:
        print("\n✅ No issues found! Your code looks good.")

    # Phase 2: Judge synthesizes everything into HTML
    print("\n⚖️  Phase 2: Lead Developer synthesizing report...")
    html_report = run_judge(security_issues, performance_issues, debug)

    # Save the report
    save_report(html_report, output_path)
    print(f"🌐 Open the report in your browser to view it!")


if __name__ == "__main__":
    asyncio.run(main())