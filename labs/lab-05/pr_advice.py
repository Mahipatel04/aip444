"""
pr-advice (Lab 5): A CLI tool that explains GitHub Pull Requests using an LLM.
Now with Tool Calling — the LLM can fetch full file contents when it needs more context.
Usage: python pr_advice.py <github-pr-url>
"""

import sys
import re
import json
import requests
import os
from tools import read_github_files

# Load API key
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
# STEP 1: URL PARSING (same as lab 3)
# ─────────────────────────────────────────────

def parse_github_pr_url(url: str) -> tuple:
    pattern = r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.match(pattern, url.strip())

    if not match:
        print("❌ Error: That doesn't look like a valid GitHub PR URL.")
        print("   Expected format: https://github.com/OWNER/REPO/pull/NUMBER")
        sys.exit(1)

    owner  = match.group(1)
    repo   = match.group(2)
    pr_num = int(match.group(3))

    return owner, repo, pr_num


# ─────────────────────────────────────────────
# STEP 2: FETCH THE DIFF (same as lab 3)
# ─────────────────────────────────────────────

MAX_DIFF_CHARS = 95_000

def fetch_diff(owner: str, repo: str, pr_num: int) -> str:
    url = f"https://github.com/{owner}/{repo}/pull/{pr_num}.diff"
    response = requests.get(url, headers={"User-Agent": "AIP444-Lab-05"})

    if response.status_code != 200:
        print(f"❌ Error fetching diff: HTTP {response.status_code}")
        sys.exit(1)

    diff_text = response.text

    if len(diff_text) > MAX_DIFF_CHARS:
        print(f"⚠️  Diff is large ({len(diff_text):,} chars). Truncating.")
        diff_text = diff_text[:MAX_DIFF_CHARS] + "\n...[Diff Truncated]..."

    return diff_text


# ─────────────────────────────────────────────
# STEP 3: FETCH COMMENTS (same as lab 3)
# ─────────────────────────────────────────────

def fetch_comments(owner: str, repo: str, pr_num: int) -> list:
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_num}/comments"

    headers = {
        "User-Agent": "AIP444-Lab-05",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"❌ GitHub API Error: HTTP {response.status_code}")
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
# STEP 4: SYSTEM PROMPT
# Updated to tell the LLM about the tool
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """
You are a Senior Software Engineer with 15+ years of experience. You are mentoring
a junior developer who needs help understanding a GitHub Pull Request — both the
code changes and the human discussion around it.

Your tone is: educational, rigorous, and patient. You explain the "why" behind
decisions, not just the "what." You value code safety and maintainability over
cleverness. You flag risks honestly.

## Tool Available: read_github_files
You have access to a tool called `read_github_files` that lets you fetch the full
content of any file from a GitHub repository.

### When TO use it:
- ALWAYS fetch at least one file that was modified in the diff to provide better context
- When the diff modifies a function and you need to see the full function to understand it
- When the diff references variables, classes, or imports that aren't visible in the diff
- When you need to understand the structure of a config file like package.json or pyproject.toml
- When understanding the change requires seeing surrounding code that wasn't modified

### When NOT to use it:
- Do NOT fetch files just because they appear in the diff — only fetch when you genuinely
  need more context to explain the change
- Do NOT fetch large files like lock files (package-lock.json, yarn.lock, poetry.lock)
- Do NOT fetch files that are clearly self-contained (e.g. a new file added from scratch)
- Do NOT fetch more than 3 files total — be selective

### How to use it:
- Use the owner and repo from the PR URL
- Use "main" as the ref unless the diff shows a different branch
- Always tell the user what you are fetching and why, before calling the tool

## Your Reasoning Process
Before writing your report, think through the PR in this exact order:

1. ANALYZE THE DIFF: What files changed? What was added, removed, or refactored?
   Do you need more context? If yes, use read_github_files now.

2. ANALYZE THE THREAD: Who is involved? What concerns were raised?

3. REFLECT: What assumptions does this PR make? Are there hidden risks?

4. SYNTHESIZE: Combine everything into the final report.

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


# ─────────────────────────────────────────────
# STEP 5: TOOL DEFINITION
# Tells the LLM what our tool does and how to call it
# ─────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_github_files",
            "description": (
                "Fetches the full raw content of one or more files from a GitHub repository. "
                "Use this when the diff alone is not enough to understand a change — for example, "
                "when you need to see the full function, class, or config file that was modified. "
                "Only use this for files you know exist in the repo. "
                "Avoid fetching lock files or files that are clearly self-contained."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "description": "List of files to fetch from GitHub.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "owner": {
                                    "type": "string",
                                    "description": "GitHub username or org. e.g. 'microsoft'"
                                },
                                "repo": {
                                    "type": "string",
                                    "description": "Repository name. e.g. 'vscode'"
                                },
                                "path": {
                                    "type": "string",
                                    "description": "File path in the repo. e.g. 'package.json' or 'src/main.py'"
                                },
                                "ref": {
                                    "type": "string",
                                    "description": "Branch name, tag, or commit SHA. e.g. 'main'"
                                },
                            },
                            "required": ["owner", "repo", "path", "ref"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["files"],
                "additionalProperties": False,
            },
        },
    }
]


# ─────────────────────────────────────────────
# STEP 6: BUILD USER MESSAGE (same as lab 3)
# ─────────────────────────────────────────────

def build_user_message(owner: str, repo: str, pr_num: int, diff: str, comments: list) -> str:
    pr_url = f"https://github.com/{owner}/{repo}/pull/{pr_num}"

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
# STEP 7: TOOL CALLING LOOP
# This is the new part — handles back-and-forth
# between the LLM and our tool
# ─────────────────────────────────────────────

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-4o-mini"

def call_llm_with_tools(system_prompt: str, user_message: str) -> str:
    if not API_KEY:
        print("❌ Error: OPENROUTER_API_KEY not found.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    # Start with the system and user messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_message},
    ]

    max_iterations = 5  # Prevent infinite loops
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        print(f"\n🤖 Calling LLM (iteration {iteration})...")

        payload = {
            "model": MODEL,
            "messages": messages,
            "tools": TOOLS,
        }

        response = requests.post(OPENROUTER_URL, headers=headers, json=payload)

        if response.status_code != 200:
            print(f"❌ LLM API Error: HTTP {response.status_code}")
            print(response.text)
            sys.exit(1)

        data = response.json()
        assistant_message = data["choices"][0]["message"]

        # Check if the LLM wants to call a tool
        if not assistant_message.get("tool_calls"):
            # No tool calls — we have the final answer!
            print("✅ LLM returned final answer")
            return assistant_message["content"]

        # LLM wants to call a tool — add its message to history
        messages.append(assistant_message)

        # Execute each tool call the LLM requested
        for tool_call in assistant_message["tool_calls"]:
            fn_name = tool_call["function"]["name"]
            fn_args = json.loads(tool_call["function"]["arguments"])

            print(f"🔧 LLM requested tool: {fn_name}")
            print(f"   Args: {json.dumps(fn_args, indent=2)}")

            # Execute our read_github_files function
            if fn_name == "read_github_files":
                result = read_github_files(fn_args["files"])
            else:
                result = f"❌ Unknown tool: {fn_name}"

            print(f"   ✅ Tool returned {len(result):,} characters")

            # Add the tool result back to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": result,
            })

    return "❌ Max iterations reached without a final answer."


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

    report = call_llm_with_tools(SYSTEM_PROMPT, user_message)

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)


if __name__ == "__main__":
    main()