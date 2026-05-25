import os
import sys
import re
import argparse
from dotenv import load_dotenv
from openai import OpenAI

# -------------------------
# Load environment variables FIRST
# -------------------------
load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    print("❌ Missing OPENROUTER_API_KEY in .env file")
    sys.exit(1)

# -------------------------
# OpenRouter client
# -------------------------
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key
)

# -------------------------
# CLI arguments
# -------------------------
def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Generate ACE flashcards from course notes"
    )

    parser.add_argument(
        "notes_path",
        help="Path to notes file"
    )

    parser.add_argument(
        "--cards",
        type=int,
        default=3,
        help="Number of flashcards (1-5)"
    )

    args = parser.parse_args()

    if args.cards < 1 or args.cards > 5:
        parser.error("--cards must be between 1 and 5")

    return args


# -------------------------
# File reader
# -------------------------
def get_file_contents(path, description):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"❌ Error: {description} not found: {path}")
        sys.exit(1)
    except Exception as err:
        print(f"❌ Error reading {description}: {err}")
        sys.exit(1)


# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":

    print("====================================")
    print("Lab 2 - ACE Flashcard Generator")
    print("====================================")

    args = parse_arguments()

    system_prompt = get_file_contents("SYSTEM_PROMPT.md", "System prompt file")
    notes_content = get_file_contents(args.notes_path, "Notes file")

    print("\n✅ Files loaded successfully")
    print(f"📄 Notes length: {len(notes_content)} characters")
    print(f"🧠 System prompt loaded: {len(system_prompt)} characters")
    print(f"📚 Generating {args.cards} flashcards...\n")

    # -------------------------
    # USER PROMPT
    # -------------------------
    user_prompt = f"""
Generate EXACTLY {args.cards} ACE flashcards.

Rules:
- Only use notes
- No hallucination
- Every card must include EVIDENCE quote
- Expand acronyms in CHALLENGE
- MISCONCEPTION must be student voice

NOTES:
<NOTES>
{notes_content}
</NOTES>
"""

    # -------------------------
    # API CALL
    # -------------------------
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3.3-70b-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2
        )

        output = response.choices[0].message.content

    except Exception as err:
        print("❌ API Error:")
        print(err)
        sys.exit(1)

    # -------------------------
    # EXTRACT CARDS
    # -------------------------
    cards = re.findall(
        r'(=== CARD \d+ ===[\s\S]*?===)',
        output
    )

    # -------------------------
    # VALIDATION
    # -------------------------
    if not cards:
        print("\n❌ No cards found in output.")
        sys.exit(1)

    # -------------------------
    # OUTPUT
    # -------------------------
    print("====================================\n")
    print(f"✅ Generated {len(cards)} flashcard(s):\n")

    for card in cards:
        print(card)
        print()