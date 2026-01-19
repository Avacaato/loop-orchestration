"""Health check module for verifying Ollama availability."""

from dataclasses import dataclass

from .config import Config
from .ollama_client import OllamaClient, OllamaConnectionError, OllamaError


@dataclass
class HealthCheckResult:
    """Result of a health check.

    Attributes:
        healthy: Whether the system is healthy
        ollama_reachable: Whether Ollama is reachable
        model_available: Whether the configured model is available
        message: Human-readable status message
        available_models: List of available models (if Ollama is reachable)
    """
    healthy: bool
    ollama_reachable: bool
    model_available: bool
    message: str
    available_models: list[str]


def check_ollama_health(
    config: Config,
    timeout: int = 2,
) -> HealthCheckResult:
    """Check if Ollama is ready and the configured model is available.

    Performs a health check with a short timeout to provide quick feedback
    to the user about system readiness.

    Args:
        config: Configuration containing Ollama URL and model name
        timeout: Maximum time to wait for health check in seconds (default: 2)

    Returns:
        HealthCheckResult with detailed status information
    """
    client = OllamaClient(
        base_url=config.ollama_url,
        timeout=timeout,
        max_retries=1,  # Don't retry during health check for speed
    )

    # Check if Ollama is reachable
    try:
        available_models = client.list_models()
    except OllamaConnectionError:
        return HealthCheckResult(
            healthy=False,
            ollama_reachable=False,
            model_available=False,
            message=f"Ollama not running. Start with: ollama serve",
            available_models=[],
        )
    except OllamaError as e:
        return HealthCheckResult(
            healthy=False,
            ollama_reachable=False,
            model_available=False,
            message=f"Error connecting to Ollama: {e}",
            available_models=[],
        )

    # Check if the configured model is available
    # Models may have tags like "llama3.2:latest", so check for prefix match
    model_name = config.model
    model_available = any(
        m == model_name or m.startswith(f"{model_name}:")
        for m in available_models
    )

    if not model_available:
        # Provide helpful message with available models
        if available_models:
            available_str = ", ".join(available_models[:5])
            if len(available_models) > 5:
                available_str += f" (+{len(available_models) - 5} more)"
            return HealthCheckResult(
                healthy=False,
                ollama_reachable=True,
                model_available=False,
                message=(
                    f"Model '{model_name}' not found. Install with: ollama pull {model_name}\n"
                    f"Available models: {available_str}"
                ),
                available_models=available_models,
            )
        else:
            return HealthCheckResult(
                healthy=False,
                ollama_reachable=True,
                model_available=False,
                message=(
                    f"Model '{model_name}' not found. Install with: ollama pull {model_name}\n"
                    f"No models currently installed."
                ),
                available_models=[],
            )

    return HealthCheckResult(
        healthy=True,
        ollama_reachable=True,
        model_available=True,
        message=f"Ollama ready with model '{model_name}'",
        available_models=available_models,
    )


def print_health_status(result: HealthCheckResult) -> None:
    """Print health check result to stdout.

    Args:
        result: Health check result to display
    """
    if result.healthy:
        print(f"✓ {result.message}")
    else:
        print(f"✗ {result.message}")
