"""Minimal Gemini connection and structured-output test."""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from google import genai


MODEL_NAME = "gemini-3.1-flash-lite"
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "message": {"type": "string"},
    },
    "required": ["status", "message"],
    "additionalProperties": False,
}


def main() -> None:
    load_dotenv()
    if not os.getenv("GEMINI_API_KEY"):
        raise SystemExit("GEMINI_API_KEY is missing from .env")

    client = genai.Client(
        http_options={
            "timeout": 30_000,
            "retry_options": {"attempts": 1},
        }
    )
    interaction = client.interactions.create(
        model=MODEL_NAME,
        input=(
            "This is an API connection test. Return status 'ok' and a short "
            "message confirming that structured JSON works."
        ),
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": RESPONSE_SCHEMA,
        },
    )

    result = json.loads(interaction.output_text)
    if set(result) != {"status", "message"} or result["status"] != "ok":
        raise SystemExit(f"Unexpected structured response: {result}")

    print("Gemini connection: OK")
    print(f"Model: {MODEL_NAME}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
