# This is a simple client script to test our running API server.
# It reads the notes.md file, sends it to the server via POST request,
# and prints the structured JSON response we get back.

import requests
import json
import time

# Path to our test notes file
notes_path = "notes.md"

def test_server():
    try:
        # Step 1: Read the notes file
        print(f"📖 Reading notes from: {notes_path}")
        with open(notes_path, "r", encoding="utf-8") as f:
            notes_content = f.read()

        # Step 2: Prepare the request payload
        # We send the notes text and ask for 2 flashcards
        payload = {
            "notes": notes_content,
            "cards": 2
        }

        print("⚡ Sending request to server...")
        start_time = time.time()

        # Step 3: Send POST request to our running server
        response = requests.post(
            "http://localhost:3000/api/generate",
            json=payload
        )

        end_time = time.time()
        print(f"⏱️  Request took {end_time - start_time:.2f}s")

        # Step 4: Handle the response
        if response.status_code != 200:
            print(f"❌ Server error {response.status_code}: {response.text}")
            return

        data = response.json()

        # Step 5: Pretty print the JSON so it's easy to read
        print("\n✅ Success! Received Structured Data:")
        print(json.dumps(data, indent=2))

    except FileNotFoundError:
        print(f"❌ Error: Could not find file at {notes_path}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_server()