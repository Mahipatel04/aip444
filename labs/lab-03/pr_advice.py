"""
pr-advice: A CLI tool that explains GitHub Pull Requests using an LLM.
Usage: python pr_advice.py <github-pr-url>
Example: python pr_advice.py https://github.com/microsoft/vscode/pull/289801
"""

import sys
import re
import requests
from dotenv import load_dotenv
import os

# Load the OPENROUTER_API_KEY from your .env file
# Load the OPENROUTER_API_KEY directly from .env file
def load_env():
    with open(".env", "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

load_env()
API_KEY = os.getenv("OPENROUTER_API_KEY")

# ─────────────────────────────────────────────
# STEP 1: URL PARSING
# ─────────────────────────────────────────────
# We accept a URL like: https://github.com/microsoft/vscode/pull/289801
# We need to extract: owner="microsoft", repo="vscode", pr_number=289801
#
# re.match() checks if the URL fits the expected pattern.
# The parts inside parentheses () are "capture groups" — they grab
# the specific pieces we care about.

def parse_github_pr_url(url: str) -> tuple:
    pattern = r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.match(pattern, url.strip())

    if not match:
        print("❌ Error: That doesn't look like a valid GitHub PR URL.")
        print("   Expected format: https://github.com/OWNER/REPO/pull/NUMBER")
        sys.exit(1)

    owner  = match.group(1)       # e.g. "microsoft"
    repo   = match.group(2)       # e.g. "vscode"
    pr_num = int(match.group(3))  # e.g. 289801

    return owner, repo, pr_num


# ─────────────────────────────────────────────
# STEP 2: FETCH THE DIFF
# ─────────────────────────────────────────────
# GitHub lets us get the raw code diff by adding ".diff" to the PR URL.
# A diff shows exactly what lines were added (+) or removed (-) in each file.
# We truncate at 95,000 characters to avoid using too many LLM tokens.

MAX_DIFF_CHARS = 95_000

def fetch_diff(owner: str, repo: str, pr_num: int) -> str:
    url = f"https://github.com/{owner}/{repo}/pull/{pr_num}.diff"
    response = requests.get(url, headers={"User-Agent": "AIP444-Lab-03"})

    if response.status_code != 200:
        print(f"❌ Error fetching diff: HTTP {response.status_code}")
        sys.exit(1)

    diff_text = response.text

    if len(diff_text) > MAX_DIFF_CHARS:
        print(f"⚠️  Diff is large ({len(diff_text):,} chars). Truncating to {MAX_DIFF_CHARS:,} chars.")
        diff_text = diff_text[:MAX_DIFF_CHARS] + "\n...[Diff Truncated]..."

    return diff_text


# ─────────────────────────────────────────────
# STEP 3: FETCH THE COMMENTS
# ─────────────────────────────────────────────
# GitHub's API lets us fetch the conversation thread on a PR.
# PRs are treated as "issues" in the GitHub API.
# We only keep three fields per comment: username, body, date.

def fetch_comments(owner: str, repo: str, pr_num: int) -> list:
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_num}/comments"

    headers = {
        "User-Agent": "AIP444-Lab-03",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"❌ GitHub API Error: HTTP {response.status_code}")
        print("   If you see 403, you may have hit the rate limit (60 req/hr). Wait and try again.")
        sys.exit(1)

    return [
        {
            "username": item["user"]["login"],
            "body":     item["body"],
            "date":     item["updated_at"],
        }
        for item in response.json()
    ]


# ─────────────────────────────────────────────
# STEP 4: BUILD THE PROMPT
# ─────────────────────────────────────────────
# We craft two messages:
#   system_prompt  → tells the LLM WHO it is and HOW to think
#   user_message   → gives the LLM the actual diff + comments data
#
# Techniques used:
#   - Persona: "You are a Senior Engineer..."
#   - Delimiters: fenced code block for diff, XML tags for comments
#   - Chain of Thought: numbered reasoning steps before writing the report
#   - Output Format: exact Markdown sections the LLM must follow

SYSTEM_PROMPT = """
You are a Senior Software Engineer with 15+ years of experience. You are mentoring
a junior developer who needs help understanding a GitHub Pull Request — both the
code changes and the human discussion around it.

Your tone is: educational, rigorous, and patient. You explain the "why" behind
decisions, not just the "what." You value code safety and maintainability over
cleverness. You flag risks honestly.

## Your Reasoning Process
Before writing your report, think through the PR in this exact order:

1. ANALYZE THE DIFF: What files changed? What was added, removed, or refactored?
   What is the technical intent?

2. ANALYZE THE THREAD: Who is involved? What concerns were raised? Was anything
   approved, rejected, or left unresolved?

3. REFLECT: What assumptions does this PR make? Are there hidden risks, edge cases,
   or dependencies not immediately obvious from the code?

4. SYNTHESIZE: Combine your analysis into the final report below.

## Output Format
Write your final report in Markdown with EXACTLY these five sections:

### tl;dr
A single sentence (max 30 words) summarizing the PR's purpose.

### Stakeholders
A bulleted list of every person who participated, with a one-line description
of their stance or contribution.

### Changes
A file-by-file breakdown of what changed and why. Write this for a junior
developer — explain concepts they might not know.

### Risks
List potential bugs, unhandled edge cases, or hidden assumptions.
Rate each as: 🟢 Low, 🟡 Medium, or 🔴 High severity.

### Learning
Write exactly 3 Socratic questions that a senior dev might ask a junior dev
to test their understanding. Reference specific files or decisions from the diff.
""".strip()


def build_user_message(owner: str, repo: str, pr_num: int, diff: str, comments: list) -> str:
    pr_url = f"https://github.com/{owner}/{repo}/pull/{pr_num}"

    # Format each comment as an XML tag with username and date as attributes
    if comments:
        formatted_comments = "\n".join(
            f'  <comment username="{c["username"]}" date="{c["date"]}">\n{c["body"]}\n  </comment>'
            for c in comments
        )
        thread_block = f"<thread>\n{formatted_comments}\n</thread>"
    else:
        thread_block = "<thread>\n  (No comments on this PR)\n</thread>"

    return f"""Please analyze this GitHub Pull Request: {pr_url}

## Code Changes (Diff)

```diff
{diff}
```

## Conversation Thread

{thread_block}
""".strip()


# ─────────────────────────────────────────────
# STEP 5: CALL THE LLM
# ─────────────────────────────────────────────
# We send our two messages to OpenRouter.
# OpenRouter uses the same format as OpenAI's API.

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash-lite"

def call_llm(system_prompt: str, user_message: str) -> str:
    if not API_KEY:
        print("❌ Error: OPENROUTER_API_KEY not found in your .env file.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
    }

    print(f"🤖 Sending to LLM ({MODEL})... please wait.")
    response = requests.post(OPENROUTER_URL, headers=headers, json=payload)

    if response.status_code != 200:
        print(f"❌ LLM API Error: HTTP {response.status_code}")
        print(response.text)
        sys.exit(1)

    data = response.json()
    return data["choices"][0]["message"]["content"]


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    if len(sys.argv) != 2:
        print("Usage:   python pr_advice.py <github-pr-url>")
        print("Example: python pr_advice.py https://github.com/microsoft/vscode/pull/289801")
        sys.exit(1)

    url = sys.argv[1]

    print(f"\n🔍 Parsing URL: {url}")
    owner, repo, pr_num = parse_github_pr_url(url)
    print(f"   ✅ Owner: {owner} | Repo: {repo} | PR #: {pr_num}")

    print(f"\n📥 Fetching diff...")
    diff = fetch_diff(owner, repo, pr_num)
    print(f"   ✅ Diff fetched: {len(diff):,} characters")

    print(f"\n💬 Fetching comments...")
    comments = fetch_comments(owner, repo, pr_num)
    print(f"   ✅ Comments fetched: {len(comments)}")

    print(f"\n📝 Building prompt...")
    user_message = build_user_message(owner, repo, pr_num, diff, comments)
    print(f"   ✅ Prompt ready")

    print(f"\n🚀 Calling LLM...\n")
    report = call_llm(SYSTEM_PROMPT, user_message)

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)


if __name__ == "__main__":
    main()