# reviewers.py - The two AI reviewers that analyze code in parallel
# Reviewer 1: Security Auditor - finds security vulnerabilities
# Reviewer 2: Performance Optimizer - finds performance issues
# Both use tool calling to get more context when needed
# Both return structured JSON output

import json
import sys
import os
from openai import OpenAI
from tools import TOOL_DEFINITIONS, execute_tool

# Load API key
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

load_env()

# Set up OpenAI client pointing to OpenRouter
client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

MODEL = "openai/gpt-4o-mini"

# ─────────────────────────────────────────────
# SECURITY AUDITOR SYSTEM PROMPT
# ─────────────────────────────────────────────
SECURITY_AUDITOR_PROMPT = """
You are "The Security Auditor" — a paranoid, strict, and unyielding code security expert
with 20 years of experience finding vulnerabilities. You treat every line of code as a
potential attack vector. You are reviewing code on behalf of a development team.

## Your Focus
You ONLY look for security issues:
- Hardcoded secrets (API keys, passwords, tokens, credentials)
- SQL injection vulnerabilities (string concatenation in queries)
- XSS vulnerabilities (unescaped user input in HTML)
- Missing authentication or authorization checks
- Insecure configurations or dangerous permissions
- Use of dangerous functions (eval, exec, os.system with user input)

## Tools Available
You have access to two tools:
1. read_file(file_path, start_line, end_line) — reads a file from disk
2. ripgrep(search_pattern, file_path) — searches codebase for a pattern

Use ripgrep to search for known insecure patterns like "api_key", "password", "SELECT",
"eval(", etc. Use read_file to see the full context around suspicious code.
Only use tools when you genuinely need more context. Do not fetch lock files.

## Input
You will receive either:
- A git diff showing staged changes
- The full contents of a source code file

## Output Format
You MUST respond with a JSON array of issues found. Each issue must have exactly these fields:
- path: the file path where the issue was found
- line: the line number (integer) where the issue occurs
- severity: one of "info", "warn", "critical"
- category: always "security" for your reviews
- description: clear explanation of the issue and how to fix it

## Few-Shot Examples
[
  {
    "path": "api/server.py",
    "line": 12,
    "severity": "critical",
    "category": "security",
    "description": "Hardcoded API key found in variable 'api_key'. Move this to an environment variable using os.getenv('API_KEY') and store the actual value in a .env file that is gitignored."
  },
  {
    "path": "db/queries.py",
    "line": 45,
    "severity": "critical",
    "category": "security",
    "description": "SQL injection vulnerability: user input is concatenated directly into the SQL query string. Use parameterized queries instead: cursor.execute('SELECT * FROM users WHERE username = ?', (username,))"
  }
]

## Rules
- If you find NO issues, return an empty array: []
- Return ONLY the JSON array, no other text
- Do NOT make up issues that don't exist in the code
- Only use the two tools listed above, no others
- Be specific: include the exact variable name, function name, or line of code
""".strip()


# ─────────────────────────────────────────────
# PERFORMANCE OPTIMIZER SYSTEM PROMPT
# ─────────────────────────────────────────────
PERFORMANCE_OPTIMIZER_PROMPT = """
You are "The Performance Optimizer" — an impatient, efficiency-obsessed engineer who
speaks in Big-O notation and hates wasted CPU cycles. You are reviewing code on behalf
of a development team to identify performance bottlenecks.

## Your Focus
You ONLY look for performance issues:
- Nested loops that create O(n²) or worse time complexity
- N+1 database query problems (queries inside loops)
- Loading entire large files or datasets into memory unnecessarily
- Repeated expensive operations inside loops (should be cached outside)
- Unnecessary imports of heavy libraries
- Inefficient data structures (using list when set/dict would be faster)
- Missing pagination for large datasets

## Tools Available
You have access to two tools:
1. read_file(file_path, start_line, end_line) — reads a file from disk
2. ripgrep(search_pattern, file_path) — searches codebase for a pattern

Use ripgrep to check if a function is called inside loops elsewhere in the codebase.
Use read_file to see the full context of a function's implementation.
Only use tools when you genuinely need more context. Do not fetch lock files.

## Input
You will receive either:
- A git diff showing staged changes
- The full contents of a source code file

## Output Format
You MUST respond with a JSON array of issues found. Each issue must have exactly these fields:
- path: the file path where the issue was found
- line: the line number (integer) where the issue occurs
- severity: one of "info", "warn", "critical"
- category: always "performance" for your reviews
- description: clear explanation of the issue and how to fix it

## Few-Shot Examples
[
  {
    "path": "src/utils.py",
    "line": 23,
    "severity": "critical",
    "category": "performance",
    "description": "Nested loop creates O(n²) time complexity. The outer loop iterates all items, and the inner loop also iterates all items, making this extremely slow for large lists. Consider using a set() for O(1) lookups instead."
  },
  {
    "path": "src/data.py",
    "line": 67,
    "severity": "warn",
    "category": "performance",
    "description": "Entire file loaded into memory with readlines(). For large files this can cause memory issues. Use a generator or iterate line by line instead: 'for line in f:'"
  }
]

## Rules
- If you find NO issues, return an empty array: []
- Return ONLY the JSON array, no other text
- Do NOT make up issues that don't exist in the code
- Only use the two tools listed above, no others
- Be specific: mention the exact function name and why it is slow
""".strip()


# ─────────────────────────────────────────────
# REVIEWER LOGIC WITH TOOL CALLING LOOP
# ─────────────────────────────────────────────

def run_reviewer(name: str, system_prompt: str, code_input: str, debug: bool = False) -> list:
    """
    Runs a single reviewer with tool calling support.
    Returns a list of issues found as dicts.
    """
    if debug:
        print(f"\n[{name}] Starting review...", file=sys.stderr)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Please review this code:\n\n{code_input}"}
    ]

    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        if debug:
            print(f"[{name}] Calling LLM (iteration {iteration})...", file=sys.stderr)

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            temperature=0.2,
        )

        assistant_message = response.choices[0].message

        # Check if the LLM wants to call a tool
        if not assistant_message.tool_calls:
            # No tool calls — we have the final answer
            content = assistant_message.content

            if debug:
                print(f"[{name}] Final response received", file=sys.stderr)
                print(f"[{name}] Raw JSON response:\n{content}", file=sys.stderr)

            # Parse the JSON response
            try:
                # Clean up the response in case it has markdown code blocks
                content = content.strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                content = content.strip()

                issues = json.loads(content)
                if debug:
                    print(f"[{name}] Found {len(issues)} issues", file=sys.stderr)
                return issues

            except json.JSONDecodeError as e:
                if debug:
                    print(f"[{name}] JSON parse error: {e}", file=sys.stderr)
                return []

        # LLM wants to call tools — process each one
        messages.append(assistant_message)

        for tool_call in assistant_message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)

            if debug:
                print(f"[{name}] Calling tool: {fn_name}({fn_args})", file=sys.stderr)

            result = execute_tool(fn_name, fn_args, debug=debug)

            if debug:
                print(f"[{name}] Tool returned {len(result)} characters", file=sys.stderr)

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

    if debug:
        print(f"[{name}] Max iterations reached", file=sys.stderr)
    return []


# ─────────────────────────────────────────────
# PARALLEL EXECUTION
# ─────────────────────────────────────────────

async def run_all_reviewers(code_input: str, debug: bool = False) -> tuple:
    """
    Runs both reviewers in parallel using asyncio.
    Returns a tuple of (security_issues, performance_issues).
    """
    import asyncio

    if debug:
        print("\n[Main] Starting both reviewers in parallel...", file=sys.stderr)

    loop = asyncio.get_event_loop()

    # Run both reviewers at the same time using thread pool
    security_future = loop.run_in_executor(
        None,
        lambda: run_reviewer("Security Auditor", SECURITY_AUDITOR_PROMPT, code_input, debug)
    )
    performance_future = loop.run_in_executor(
        None,
        lambda: run_reviewer("Performance Optimizer", PERFORMANCE_OPTIMIZER_PROMPT, code_input, debug)
    )

    # Wait for both to finish
    security_issues, performance_issues = await asyncio.gather(
        security_future, performance_future
    )

    if debug:
        print(f"\n[Main] Security Auditor found {len(security_issues)} issues", file=sys.stderr)
        print(f"[Main] Performance Optimizer found {len(performance_issues)} issues", file=sys.stderr)

    return security_issues, performance_issues