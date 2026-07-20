# img_debug.py - Visual Debugger CLI tool
# Takes a screenshot of an error, optimizes it, and uses AI + web search to find a fix
# Usage: python img_debug.py <path_to_screenshot>

import sys
import os
import io
import base64
import json
from PIL import Image
from openai import OpenAI
from tavily import TavilyClient

# ─────────────────────────────────────────────
# LOAD ENV
# ─────────────────────────────────────────────

def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

load_env()

# Set up clients
openai_client = OpenAI(
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
)
tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

MODEL = "google/gemini-2.5-flash-lite"


# ─────────────────────────────────────────────
# STEP 1: IMAGE OPTIMIZATION
# Resize and compress the image to reduce API costs
# ─────────────────────────────────────────────

def process_image(path: str) -> str:
    """
    Loads an image, resizes it to max 1024px on longest side,
    converts to JPEG at 85% quality, and returns base64 string.
    """
    original_size = os.path.getsize(path)
    print(f"📸 Original image size: {original_size / 1024:.1f} KB", file=sys.stderr)

    with Image.open(path) as img:
        # Remove alpha channel (transparency) - JPEG doesn't support it
        img = img.convert("RGB")
        # Proportional resize - keeps aspect ratio
        img.thumbnail((1024, 1024))
        # Save to memory buffer as JPEG
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        jpeg_bytes = buffer.getvalue()

    processed_size = len(jpeg_bytes)
    print(f"🗜️  Processed JPEG size: {processed_size / 1024:.1f} KB", file=sys.stderr)

    # Convert to base64 string
    b64_string = base64.b64encode(jpeg_bytes).decode("utf-8")
    print(f"📦 Base64 string size: {len(b64_string) / 1024:.1f} KB", file=sys.stderr)

    return b64_string


# ─────────────────────────────────────────────
# STEP 2: TOOL DEFINITION
# Tells the LLM it can search the web
# ─────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_error",
            "description": (
                "Searches the web for technical documentation, coding errors, "
                "and other details to help with debugging the error in the screenshot. "
                "Use this when you see a specific error message, library name, or version number "
                "that you want to look up current documentation for."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query based on what you see in the screenshot"
                    }
                },
                "required": ["query"]
            }
        }
    }
]


# ─────────────────────────────────────────────
# STEP 3: SYSTEM PROMPT
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """
You are img-debug, an expert developer debugging assistant that analyzes screenshots of errors.

## Your Process
Follow these steps when analyzing a screenshot:

1. DESCRIBE: Look carefully at the image. Identify:
   - Any error messages or error codes
   - File names and line numbers mentioned
   - The programming language or framework involved
   - Any version numbers visible
   - The color and layout context (red text = error, etc.)

2. SEARCH: Use the lookup_error tool to search for:
   - The specific error message you see
   - The library/framework version if visible
   - Any recent changes in the technology that might explain the error
   Always search before giving a fix — don't guess from memory alone.

3. ANALYZE: Based on what you see AND what you found in the search:
   - Explain what is causing the error
   - Reference specific documentation you found

4. FIX: Provide a clear, specific fix including:
   - The exact code change needed
   - Any CLI commands to run
   - Why this fix works

## Rules
- ALWAYS use lookup_error before suggesting a fix
- If the image doesn't show a technical error (e.g. a photo of a sunset), say so clearly
- Cite the URLs of any documentation you found
- Be specific — mention exact file names and line numbers when visible
- If you can't find a fix, say so honestly
""".strip()


# ─────────────────────────────────────────────
# STEP 4: INTERACTION LOOP
# Handles tool calls between LLM and Tavily
# ─────────────────────────────────────────────

def analyze_screenshot(image_path: str, user_prompt: str = "Please debug this error."):
    """
    Main function — processes image and runs the tool calling loop.
    """
    # Process the image
    print(f"\n🔍 Processing image: {image_path}", file=sys.stderr)
    b64_image = process_image(image_path)

    # Build initial messages with image
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": user_prompt
                },
                {
                    # OpenRouter image format
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64_image}"
                    }
                }
            ]
        }
    ]

    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        print(f"\n🤖 Calling LLM (iteration {iteration})...", file=sys.stderr)

        response = openai_client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            temperature=0.2,
        )

        assistant_message = response.choices[0].message

        # Check if LLM wants to call a tool
        if not assistant_message.tool_calls:
            # No tool calls — final answer!
            print("\n✅ Got final answer!\n", file=sys.stderr)
            print(assistant_message.content)
            return

        # LLM wants to search — add its message to history
        messages.append(assistant_message)

        # Execute each tool call
        for tool_call in assistant_message.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)

            if fn_name == "lookup_error":
                query = fn_args["query"]
                print(f"\n🔎 Searching Tavily for: '{query}'", file=sys.stderr)

                # Call Tavily search
                search_results = tavily_client.search(
                    query=query,
                    max_results=5,
                )

                # Format results for the LLM
                formatted = f"Search results for '{query}':\n\n"
                for i, result in enumerate(search_results.get("results", []), 1):
                    formatted += f"{i}. {result['title']}\n"
                    formatted += f"   URL: {result['url']}\n"
                    formatted += f"   {result['content'][:300]}...\n\n"

                print(f"   Found {len(search_results.get('results', []))} results", file=sys.stderr)

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": formatted,
                })

    print("❌ Max iterations reached.", file=sys.stderr)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python img_debug.py <path_to_screenshot>")
        print("Example: python img_debug.py error.png")
        sys.exit(1)

    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print(f"❌ Error: File not found: {image_path}")
        sys.exit(1)

    # Optional custom prompt as second argument
    user_prompt = sys.argv[2] if len(sys.argv) > 2 else "Please analyze this error and provide a fix."

    analyze_screenshot(image_path, user_prompt)