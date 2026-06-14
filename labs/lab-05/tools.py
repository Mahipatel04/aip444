# This file implements the read_github_files tool.
# It fetches raw file content from GitHub using the raw.githubusercontent.com URL pattern.
# The LLM will call this function when it needs more context to understand a PR.

import requests

# Maximum number of lines to show before truncating
# Keeps large files from eating up all our LLM tokens
MAX_LINES = 1000

def read_github_files(files: list) -> str:
    """
    Fetches one or more raw files from GitHub.
    Args:
        files: A list of dicts, each with owner, repo, path, and ref keys
    Returns:
        A string containing the file contents, separated by markdown headers
    """
    results = []

    for file in files:
        owner = file.get("owner")
        repo  = file.get("repo")
        path  = file.get("path")
        ref   = file.get("ref", "main")  # default to main branch

        # Build the raw GitHub URL
        # Format: https://raw.githubusercontent.com/{owner}/{repo}/refs/heads/{ref}/{path}
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/refs/heads/{ref}/{path}"

        print(f"🔧 Tool fetching: {url}")

        try:
            response = requests.get(url, headers={"User-Agent": "AIP444-Lab-05"})

            # Handle errors like 404 file not found or rate limits
            if response.status_code == 404:
                results.append(f"## {path}\n\n❌ Error: File not found at `{url}`")
                continue
            elif response.status_code == 429:
                results.append(f"## {path}\n\n❌ Error: GitHub rate limit hit. Try again later.")
                continue
            elif response.status_code != 200:
                results.append(f"## {path}\n\n❌ Error: HTTP {response.status_code}")
                continue

            content = response.text
            lines = content.splitlines()
            total_lines = len(lines)

            # Truncate if file is too large to prevent token overuse
            if total_lines > MAX_LINES:
                print(f"   ⚠️  File has {total_lines} lines, truncating to {MAX_LINES}")
                lines = lines[:MAX_LINES]
                truncation_note = f"\n[File truncated: showing first {MAX_LINES} of {total_lines} lines]"
                content = "\n".join(lines) + truncation_note
            else:
                content = "\n".join(lines)

            results.append(f"## {path}\n\n```\n{content}\n```")

        except Exception as e:
            results.append(f"## {path}\n\n❌ Error fetching file: {str(e)}")

    # Join all file results with a separator
    return "\n\n---\n\n".join(results)