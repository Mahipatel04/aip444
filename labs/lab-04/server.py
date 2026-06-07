# This is the main API server for the flashcard generator.
# It uses FastAPI to create an HTTP server that accepts POST requests
# with notes text and returns AI-generated flashcards as structured JSON.
# It includes middleware for CORS (cross-origin requests) and request timing.

import uvicorn
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# This is our AI logic — we will implement this file next
from flashcard_generator import generate_flashcards

# Create the FastAPI app instance
app = FastAPI()

# CORS middleware — allows any frontend (web/mobile) to call this API
# Without this, browsers would block requests from other origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Allow all origins
    allow_methods=["*"],   # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],   # Allow all headers
)

# Timing middleware — measures how long each request takes
# and adds it to the response headers as X-Process-Time
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# This defines the shape of the request body we expect
# notes = the text to generate flashcards from
# cards = how many flashcards to generate (defaults to 3)
class GenerateRequest(BaseModel):
    notes: str
    cards: int = 3

# The main route — accepts POST requests at /api/generate
# FastAPI automatically validates the request body against GenerateRequest
@app.post("/api/generate")
async def generate_cards(request: GenerateRequest):
    try:
        result = await generate_flashcards(request.notes, request.cards)
        return result
    except Exception as e:
        print(f"Server Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Start the server when this file is run directly
if __name__ == "__main__":
    print("🚀 Server running on http://localhost:3000")
    uvicorn.run(app, host="0.0.0.0", port=3000)