from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# Project root:
# src/config.py -> src/ -> project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Load .env if it exists.
# This will not fail if .env is missing.
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class AppConfig:
    """
    Central project configuration.

    API keys are optional at import time so the project can be built,
    tested, and committed before purchasing or adding an API key.
    """

    llm_provider: str
    openai_api_key: str | None
    openai_model: str
    gemini_api_key: str | None
    gemini_model: str
    model_temperature: float
    max_input_text_length: int
    allowed_file_types: tuple[str, ...]


def _get_optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None

    value = value.strip()
    return value or None


def _get_float_env(name: str, default: float) -> float:
    value = _get_optional_env(name)
    if value is None:
        return default

    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a float. Got: {value}") from exc


def _get_int_env(name: str, default: int) -> int:
    value = _get_optional_env(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer. Got: {value}") from exc


CONFIG = AppConfig(
    llm_provider=(_get_optional_env("LLM_PROVIDER") or "openai").lower(),
    openai_api_key=_get_optional_env("OPENAI_API_KEY"),
    openai_model=_get_optional_env("OPENAI_MODEL") or "gpt-4.1-mini",
    gemini_api_key=_get_optional_env("GEMINI_API_KEY"),
    gemini_model=_get_optional_env("GEMINI_MODEL") or "gemini-2.5-flash",
    model_temperature=_get_float_env("MODEL_TEMPERATURE", 0.2),
    max_input_text_length=_get_int_env("MAX_INPUT_TEXT_LENGTH", 20_000),
    allowed_file_types=(".txt", ".pdf", ".docx"),
)


def require_openai_api_key() -> str:
    """
    Return the OpenAI API key when an LLM call is about to run.

    This prevents the project from crashing during normal imports, tests,
    or development before the user has added an API key.
    """

    if not CONFIG.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. "
            "Create a local .env file and add OPENAI_API_KEY before running the AI agents."
        )

    return CONFIG.openai_api_key


def require_gemini_api_key() -> str:
    """
    Return the Gemini API key when an LLM call is about to run.

    This prevents the project from crashing during normal imports, tests,
    or development before the user has added an API key.
    """

    if not CONFIG.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. "
            "Create a local .env file and add GEMINI_API_KEY before running the AI agents."
        )

    return CONFIG.gemini_api_key