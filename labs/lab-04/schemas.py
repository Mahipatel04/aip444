# This file defines the "shape" of our flashcard data using Pydantic.
# Pydantic schemas act as a contract — the LLM MUST return data
# that matches exactly these fields and types. No more fragile text parsing!

from pydantic import BaseModel, Field
from typing import List

# This defines one single flashcard and all its required fields
class Flashcard(BaseModel):

    application: str = Field(
        description="1-2 sentence real-world workplace task where this concept is needed"
    )
    challenge: str = Field(
        description="A specific problem to solve in the scenario. Expand all acronyms"
    )
    answer: str = Field(
        description="Correct solution with brief explanation"
    )
    evidence: str = Field(
        description="Direct quote from source notes supporting this card"
    )
    misconception: str = Field(
        description="What a junior developer or student might incorrectly believe"
    )
    correction: str = Field(
        description="Why the misconception is wrong, citing the notes"
    )

# This defines the full API response — a list of flashcards
# This is what gets returned to the client as JSON
class FlashcardResponse(BaseModel):
    flashcards: List[Flashcard]