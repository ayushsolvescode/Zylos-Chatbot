"""
test_api.py

Loads OPENROUTER_API_KEY from .env and sends a single test message to
the OpenRouter Chat Completions endpoint, then prints the response.

Notes:
- This script expects a valid OPENROUTER_API_KEY in the project's .env file.
- We intentionally do not include a real API key in the repository.
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv


load_dotenv()  # Load environment variables from .env into the process env

# Read API key from environment
API_KEY = os.getenv("OPENROUTER_API_KEY")

if not API_KEY or API_KEY.strip() == "" or "your_openrouter_api_key" in API_KEY:
    print("OPENROUTER_API_KEY is not set or contains a placeholder. Set it in .env before running this script.")
    sys.exit(1)


# OpenRouter chat completions endpoint
# This URL follows the OpenRouter API pattern for chat/completions.
ENDPOINT = "https://api.openrouter.ai/v1/chat/completions"


# HTTP headers for the request
# - Authorization: Bearer token for authenticating with OpenRouter
# - Content-Type: We're sending JSON in the request body
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


# Request body (JSON payload)
# - model: the model name to use. Replace with a current/free OpenRouter model if needed.
# - messages: list of message objects; here we send a single user message.
# - max_tokens: limit the response length
payload = {
    "model": "gpt-4o-mini",  # example model name; change if not available
    "messages": [
        {"role": "user", "content": "Hello, this is a test message from test_api.py. Please respond with a short acknowledgement."}
    ],
    "max_tokens": 200,
}


def main():
    try:
        # Send POST request to the OpenRouter API
        # The response typically contains a JSON object with a `choices` array
        # where each choice has a `message` with `role` and `content`.
        resp = requests.post(ENDPOINT, headers=headers, json=payload, timeout=30)

        print(f"HTTP {resp.status_code}")

        # Try to parse JSON response
        try:
            data = resp.json()
        except ValueError:
            print("Response is not valid JSON:\n", resp.text)
            return

        # Print the full parsed response for inspection
        print(json.dumps(data, indent=2))

        # Example response structure (may vary):
        # {
        #   "id": "...",
        #   "object": "chat.completion",
        #   "created": 1234567890,
        #   "choices": [
        #       {
        #           "message": {"role": "assistant", "content": "..."},
        #           "finish_reason": "stop"
        #       }
        #   ],
        #   "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        # }

        # If choices exist, print the assistant's content
        choices = data.get("choices") or []
        if choices:
            first = choices[0]
            message = first.get("message") or {}
            content = message.get("content") or message.get("text")
            print("\nAssistant response:\n")
            print(content)
        else:
            print("No choices returned in response.")

    except requests.RequestException as e:
        print("Request failed:", str(e))


if __name__ == "__main__":
    main()
