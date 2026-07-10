from __future__ import annotations

from typing import Any, TypeVar

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import CONFIG, require_gemini_api_key, require_openai_api_key


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMClientError(Exception):
    """
    Base exception for LLM client errors.
    """


class LLMConfigurationError(LLMClientError):
    """
    Raised when the LLM client is missing required configuration.
    """


class LLMResponseError(LLMClientError):
    """
    Raised when the LLM returns an invalid or unusable response.
    """


def _build_messages(system_prompt: str, user_prompt: str) -> list[tuple[str, str]]:
    """
    Build LangChain-compatible chat messages.
    """

    return [
        ("system", system_prompt.strip()),
        ("human", user_prompt.strip()),
    ]


def _extract_text_from_response(response: Any) -> str:
    """
    Extract plain text from a LangChain model response.
    """

    content = getattr(response, "content", response)

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        text_parts: list[str] = []

        for item in content:
            if isinstance(item, dict) and "text" in item:
                text_parts.append(str(item["text"]))
            else:
                text_parts.append(str(item))

        return "\n".join(text_parts).strip()

    return str(content).strip()


def _validate_structured_response(
    response: Any,
    output_schema: type[SchemaT],
) -> SchemaT:
    """
    Validate structured model output against the expected Pydantic schema.
    """

    if isinstance(response, output_schema):
        return response

    if isinstance(response, dict):
        # Some LangChain structured-output modes may return:
        # {"raw": ..., "parsed": ..., "parsing_error": ...}
        if "parsed" in response:
            parsed = response["parsed"]

            if isinstance(parsed, output_schema):
                return parsed

            if isinstance(parsed, dict):
                return output_schema.model_validate(parsed)

        return output_schema.model_validate(response)

    raise LLMResponseError(
        f"Expected response matching {output_schema.__name__}, "
        f"but received {type(response).__name__}."
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _invoke_with_retry(model: Any, messages: list[tuple[str, str]]) -> Any:
    """
    Invoke a LangChain model with retry handling.
    """

    return model.invoke(messages)


class LLMClient:
    """
    Thin wrapper around the project LLM.

    Agents should use this client instead of creating their own chat model
    objects. This keeps provider selection, model configuration, retries, and
    error handling in one place.
    """

    def __init__(
        self,
        provider: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
    ) -> None:
        self.provider = (provider or CONFIG.llm_provider).lower()
        self.model_name = model_name or (
            CONFIG.gemini_model if self.provider == "gemini" else CONFIG.openai_model
        )
        self.temperature = (
            CONFIG.model_temperature if temperature is None else temperature
        )

    def _build_chat_model(self) -> ChatOpenAI | ChatGoogleGenerativeAI:
        """
        Create the chat model for the selected provider.

        This is intentionally done only when an LLM call is made, so the app
        can be imported and tested before an API key exists.
        """

        if self.provider == "openai":
            try:
                api_key = require_openai_api_key()
            except RuntimeError as exc:
                raise LLMConfigurationError(str(exc)) from exc

            return ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                api_key=api_key,
                max_retries=0,
            )

        if self.provider == "gemini":
            try:
                api_key = require_gemini_api_key()
            except RuntimeError as exc:
                raise LLMConfigurationError(str(exc)) from exc

            return ChatGoogleGenerativeAI(
                model=self.model_name,
                temperature=self.temperature,
                google_api_key=api_key,
                max_retries=0,
            )

        raise LLMConfigurationError(f"Unsupported LLM provider: {self.provider!r}")

    def invoke_text(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Invoke the LLM and return a plain text response.
        """

        messages = _build_messages(system_prompt, user_prompt)
        model = self._build_chat_model()

        try:
            response = _invoke_with_retry(model, messages)
        except Exception as exc:
            raise LLMClientError(f"Plain LLM call failed: {exc}") from exc

        text = _extract_text_from_response(response)

        if not text:
            raise LLMResponseError("The LLM returned an empty text response.")

        return text

    def invoke_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[SchemaT],
    ) -> SchemaT:
        """
        Invoke the LLM and return a Pydantic-validated structured response.
        """

        messages = _build_messages(system_prompt, user_prompt)
        model = self._build_chat_model()
        structured_model = model.with_structured_output(output_schema)

        try:
            response = _invoke_with_retry(structured_model, messages)
            return _validate_structured_response(response, output_schema)
        except ValidationError as exc:
            raise LLMResponseError(
                f"Structured response did not match {output_schema.__name__}: {exc}"
            ) from exc
        except Exception as exc:
            raise LLMClientError(f"Structured LLM call failed: {exc}") from exc


_default_client = LLMClient()


def generate_text_response(
    system_prompt: str,
    user_prompt: str,
) -> str:
    """
    Convenience function for plain text LLM responses.
    """

    return _default_client.invoke_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


def generate_structured_response(
    system_prompt: str,
    user_prompt: str,
    output_schema: type[SchemaT],
) -> SchemaT:
    """
    Convenience function for structured Pydantic LLM responses.
    """

    return _default_client.invoke_structured(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        output_schema=output_schema,
    )