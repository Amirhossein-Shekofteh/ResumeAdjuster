"""
Quick manual smoke test for the configured Gemini model.

Usage:
    python scripts/test_gemini.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import CONFIG
from src.llm_client import LLMClient, LLMClientError


def main() -> None:
    if not CONFIG.gemini_api_key:
        print("GEMINI_API_KEY is not set. Add it to your .env file first.")
        sys.exit(1)

    print(f"Testing model: {CONFIG.gemini_model}")

    client = LLMClient(provider="gemini")

    try:
        response = client.invoke_text(
            system_prompt="You are a helpful assistant.",
            user_prompt="Reply with a short sentence confirming you're working.",
        )
    except LLMClientError as exc:
        print(f"Call failed: {exc}")
        sys.exit(1)

    print(f"Response: {response}")


if __name__ == "__main__":
    main()
