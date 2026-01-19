"""Ollama client module for communicating with Ollama's REST API."""

import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class Message:
    """A message in a chat conversation."""
    role: str  # "system", "user", or "assistant"
    content: str


@dataclass
class OllamaResponse:
    """Response from Ollama API."""
    content: str
    model: str
    done: bool
    total_duration: int | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None


class OllamaError(Exception):
    """Base exception for Ollama client errors."""
    pass


class OllamaConnectionError(OllamaError):
    """Raised when cannot connect to Ollama."""
    pass


class OllamaModelNotFoundError(OllamaError):
    """Raised when the requested model is not found."""
    pass


class OllamaTimeoutError(OllamaError):
    """Raised when a request times out."""
    pass


class OllamaClient:
    """Client for communicating with Ollama's REST API.

    Supports text generation and multi-turn chat conversations with
    configurable retry logic and timeout handling.
    """

    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_TIMEOUT = 300  # 5 minutes in seconds
    DEFAULT_RETRIES = 3

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the Ollama client.

        Args:
            base_url: Base URL for Ollama API. Defaults to http://localhost:11434
            timeout: Request timeout in seconds. Defaults to 300 (5 minutes)
            max_retries: Maximum number of retry attempts. Defaults to 3
        """
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        self.max_retries = max_retries if max_retries is not None else self.DEFAULT_RETRIES

    def _make_request(
        self,
        endpoint: str,
        method: str = "POST",
        json_data: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Make a request to the Ollama API with retry logic.

        Args:
            endpoint: API endpoint (e.g., "/api/generate")
            method: HTTP method
            json_data: JSON payload for the request
            timeout: Request timeout in seconds (overrides instance default)

        Returns:
            JSON response from the API

        Raises:
            OllamaConnectionError: If cannot connect to Ollama
            OllamaModelNotFoundError: If the requested model is not found
            OllamaTimeoutError: If the request times out
            OllamaError: For other API errors
        """
        url = f"{self.base_url}{endpoint}"
        request_timeout = timeout if timeout is not None else self.timeout

        last_exception: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                with httpx.Client(timeout=request_timeout) as client:
                    if method == "POST":
                        response = client.post(url, json=json_data)
                    elif method == "GET":
                        response = client.get(url)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                # Check for model not found error
                if response.status_code == 404:
                    model = json_data.get("model", "unknown") if json_data else "unknown"
                    raise OllamaModelNotFoundError(
                        f"Model '{model}' not found. Run: ollama pull {model}"
                    )

                response.raise_for_status()
                result: dict[str, Any] = response.json()
                return result

            except httpx.ConnectError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                raise OllamaConnectionError(
                    f"Cannot connect to Ollama at {self.base_url}. Is it running?"
                ) from e

            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                raise OllamaTimeoutError(
                    f"Request to Ollama timed out after {request_timeout} seconds"
                ) from e

            except httpx.HTTPStatusError as e:
                raise OllamaError(f"Ollama API error: {e}") from e

        if last_exception:
            raise OllamaError(f"Request failed after {self.max_retries} retries") from last_exception
        raise OllamaError(f"Request failed after {self.max_retries} retries")

    def generate(
        self,
        prompt: str,
        model: str,
        system_prompt: str | None = None,
        timeout: int | None = None,
    ) -> OllamaResponse:
        """Generate a completion for a single prompt.

        Args:
            prompt: The prompt to generate a completion for
            model: The model to use for generation
            system_prompt: Optional system prompt to set context
            timeout: Optional timeout override in seconds

        Returns:
            OllamaResponse with the generated content

        Raises:
            OllamaConnectionError: If cannot connect to Ollama
            OllamaModelNotFoundError: If the requested model is not found
            OllamaTimeoutError: If the request times out
        """
        json_data: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }

        if system_prompt:
            json_data["system"] = system_prompt

        response = self._make_request("/api/generate", json_data=json_data, timeout=timeout)

        return OllamaResponse(
            content=response.get("response", ""),
            model=response.get("model", model),
            done=response.get("done", True),
            total_duration=response.get("total_duration"),
            prompt_eval_count=response.get("prompt_eval_count"),
            eval_count=response.get("eval_count"),
        )

    def chat(
        self,
        messages: list[Message],
        model: str,
        timeout: int | None = None,
    ) -> OllamaResponse:
        """Have a multi-turn conversation with the model.

        Args:
            messages: List of Message objects representing the conversation
            model: The model to use for the conversation
            timeout: Optional timeout override in seconds

        Returns:
            OllamaResponse with the assistant's reply

        Raises:
            OllamaConnectionError: If cannot connect to Ollama
            OllamaModelNotFoundError: If the requested model is not found
            OllamaTimeoutError: If the request times out
        """
        json_data: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ],
            "stream": False,
        }

        response = self._make_request("/api/chat", json_data=json_data, timeout=timeout)

        message = response.get("message", {})

        return OllamaResponse(
            content=message.get("content", ""),
            model=response.get("model", model),
            done=response.get("done", True),
            total_duration=response.get("total_duration"),
            prompt_eval_count=response.get("prompt_eval_count"),
            eval_count=response.get("eval_count"),
        )

    def list_models(self) -> list[str]:
        """List all available models.

        Returns:
            List of model names

        Raises:
            OllamaConnectionError: If cannot connect to Ollama
        """
        response = self._make_request("/api/tags", method="GET")
        models = response.get("models", [])
        return [model.get("name", "") for model in models]

    def is_healthy(self) -> bool:
        """Check if Ollama is reachable.

        Returns:
            True if Ollama is reachable, False otherwise
        """
        try:
            self._make_request("/api/tags", method="GET", timeout=2)
            return True
        except OllamaError:
            return False
