# This file contains the AI logic for generating flashcards.
# It reads the system prompt, calls the LLM via OpenAI SDK,
# and uses Pydantic structured outputs to guarantee valid JSON back.

import os
from openai import OpenAI
from schemas import FlashcardResponse

# Load API key the same reliable way we did in lab 3
def load_env():
    with open(".env", "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

load_env()

# Set up the OpenAI client pointing to OpenRouter
client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)

# The model we want to use — supports structured outputs
MODEL = "openai/gpt-4o-mini"

async def generate_flashcards(notes: str, cards: int) -> FlashcardResponse:
    """
    Generates flashcards from the provided notes using Structured Outputs.
    Args:
        notes: The raw text of the course notes
        cards: The number of cards to generate
    Returns:
        A FlashcardResponse object containing the list of flashcards
    """

    # Step 1: Load the system prompt from SYSTEM_PROMPT.md
    with open("SYSTEM_PROMPT.md", "r", encoding="utf-8") as f:
        system_prompt = f.read()

    # Step 2: Build the user message
    user_message = f"Please generate {cards} flashcard(s) from the following notes:\n\n{notes}"

    # Step 3: Call the LLM with structured output using our Pydantic schema
    # The parse() method forces the response to match FlashcardResponse exactly
    completion = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        response_format=FlashcardResponse,
    )

    # Step 4: Return the parsed Pydantic object
    # FastAPI will automatically convert this to JSON for the response
    parsed = completion.choices[0].message.parsed
    return parsed