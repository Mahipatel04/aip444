# tools.py - Implements the tools that AI reviewers can call
# to get more context about the codebase being reviewed.
# Two tools are available:
#   1. read_file - reads a file from disk
#   2. ripgrep - searches the codebase for a pattern

import subprocess
import sys
import os

# Maximum lines to return from a file to avoid token overuse
MAX_FILE_LINES = 200

# Maximum characters to return from ripgrep results
MAX_RIPGREP_CHARS = 3000


def read_file(file_path: str, start_line: int = None, end_line: int = None) -> str:
    """
    Reads a file from disk and returns its contents as a string.
    Optionally returns only a range of lines (start_line to end_line).
    Truncates files that are too long to avoid using too many tokens.
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return f"❌ Error: File not found: {file_path}"

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        total_lines = len(lines)

        # Apply line range if specified
        if start_line is not None and end_line is not None:
            # Convert to 0-indexed
            start = max(0, start_line - 1)
            end = min(total_lines, end_line)
            lines = lines[start:end]
            header = f"# File: {file_path} (lines {start_line}-{end_line} of {total_lines})\n\n"
        elif start_line is not None:
            start = max(0, start_line - 1)
            lines = lines[start:]
            header = f"# File: {file_path} (lines {start_line}-end of {total_lines})\n\n"
        else:
            header = f"# File: {file_path} ({total_lines} lines total)\n\n"

        # Truncate if too long
        if len(lines) > MAX_FILE_LINES:
            truncated = lines[:MAX_FILE_LINES]
            content = "".join(truncated)
            content += f"\n\n[File truncated: showing {MAX_FILE_LINES} of {len(lines)} lines]"
        else:
            content = "".join(lines)

        return header + content

    except Exception as e:
        return f"❌ Error reading file: {str(e)}"


def ripgrep(search_pattern: str, file_path: str = ".") -> str:
    """
    Searches the codebase recursively for a pattern using ripgrep.
    Returns matching lines with file names and line numbers.
    Truncates results if too long.
    """
    try:
        # Run ripgrep command
        # -n = show line numbers
        # -i = case insensitive
        # --no-heading = cleaner output
        # file_path = where to search (default is current directory)
        result = subprocess.run(
            ["rg", "-n", "-i", "--no-heading", search_pattern, file_path],
            capture_output=True,
            text=True,
            timeout=10
        )

        output = result.stdout

        if not output:
            return f"No matches found for pattern: '{search_pattern}'"

        # Truncate if too long
        if len(output) > MAX_RIPGREP_CHARS:
            output = output[:MAX_RIPGREP_CHARS]
            output += f"\n\n[Results truncated at {MAX_RIPGREP_CHARS} characters]"

        return f"Search results for '{search_pattern}':\n\n{output}"

    except subprocess.TimeoutExpired:
        return "❌ Error: ripgrep timed out after 10 seconds"
    except FileNotFoundError:
        return "❌ Error: ripgrep not found. Please install it first."
    except Exception as e:
        return f"❌ Error running ripgrep: {str(e)}"


# Tool definitions — these tell the LLM what tools exist and how to call them
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Reads the contents of a file from disk. Use this when you need to see "
                "the full file to understand the context of a change — for example, to "
                "check imports, class definitions, or surrounding functions. "
                "Only use this for files you know exist. "
                "Avoid reading lock files like package-lock.json."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to read. e.g. 'src/main.py' or 'bad_code.py'"
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Optional: line number to start reading from (1-indexed)"
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Optional: line number to stop reading at (1-indexed, inclusive)"
                    }
                },
                "required": ["file_path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ripgrep",
            "description": (
                "Searches the codebase recursively for a text pattern using ripgrep. "
                "Use this to find where a function is defined, where a variable is used, "
                "or to search for insecure patterns like hardcoded secrets or dangerous functions. "
                "Returns matching lines with file names and line numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "search_pattern": {
                        "type": "string",
                        "description": "The pattern to search for. e.g. 'api_key' or 'SELECT.*WHERE'"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Optional: path to search in. Defaults to current directory '.'"
                    }
                },
                "required": ["search_pattern"],
                "additionalProperties": False,
            },
        },
    },
]


def execute_tool(name: str, args: dict, debug: bool = False) -> str:
    """
    Executes a tool by name with the given arguments.
    Returns the result as a string.
    """
    if name == "read_file":
        file_path = args.get("file_path")
        start_line = args.get("start_line")
        end_line = args.get("end_line")
        if debug:
            print(f"[Tool] read_file({file_path}, start={start_line}, end={end_line})", file=sys.stderr)
        result = read_file(file_path, start_line, end_line)
        if debug:
            print(f"[Tool] read_file returned {len(result)} characters", file=sys.stderr)
        return result

    elif name == "ripgrep":
        pattern = args.get("search_pattern")
        path = args.get("file_path", ".")
        if debug:
            print(f"[Tool] ripgrep('{pattern}', path='{path}')", file=sys.stderr)
        result = ripgrep(pattern, path)
        if debug:
            print(f"[Tool] ripgrep returned {len(result)} characters", file=sys.stderr)
        return result

    else:
        return f"❌ Unknown tool: {name}"