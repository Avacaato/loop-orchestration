"""Configuration system for Loop Orchestration."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Base exception for configuration errors."""
    pass


class ConfigValidationError(ConfigError):
    """Raised when configuration validation fails."""
    pass


class ConfigFileError(ConfigError):
    """Raised when there are issues with the config file."""
    pass


@dataclass
class Config:
    """Configuration for Loop Orchestration.

    Attributes:
        model: The Ollama model to use for generation
        ollama_url: Base URL for the Ollama API
        max_iterations: Maximum loop iterations before stopping
        session_dir: Directory to store session data
    """
    model: str = "llama3.2"
    ollama_url: str = "http://localhost:11434"
    max_iterations: int = 50
    session_dir: Path = field(default_factory=lambda: Path.home() / ".loop-orchestration" / "sessions")

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values.

        Raises:
            ConfigValidationError: If any configuration value is invalid
        """
        errors: list[str] = []

        if not self.model:
            errors.append("model: Cannot be empty")

        if not self.ollama_url:
            errors.append("ollama_url: Cannot be empty")
        elif not self.ollama_url.startswith(("http://", "https://")):
            errors.append("ollama_url: Must start with http:// or https://")

        if self.max_iterations <= 0:
            errors.append(f"max_iterations: Must be positive, got {self.max_iterations}")

        if errors:
            raise ConfigValidationError("Configuration validation failed:\n  - " + "\n  - ".join(errors))


def get_config_dir() -> Path:
    """Get the configuration directory path.

    Returns:
        Path to ~/.loop-orchestration/
    """
    return Path.home() / ".loop-orchestration"


def get_config_path() -> Path:
    """Get the configuration file path.

    Returns:
        Path to ~/.loop-orchestration/config.yaml
    """
    return get_config_dir() / "config.yaml"


def _create_default_config() -> dict[str, Any]:
    """Create the default configuration dictionary.

    Returns:
        Default configuration as a dictionary
    """
    return {
        "model": "llama3.2",
        "ollama_url": "http://localhost:11434",
        "max_iterations": 50,
        "session_dir": str(Path.home() / ".loop-orchestration" / "sessions"),
    }


def _ensure_config_dir() -> None:
    """Ensure the configuration directory exists.

    Raises:
        ConfigFileError: If the directory cannot be created or is not writable
    """
    config_dir = get_config_dir()

    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        raise ConfigFileError(
            f"Cannot create config directory at {config_dir}. "
            f"Please check permissions or create it manually:\n"
            f"  mkdir -p {config_dir}"
        ) from e
    except OSError as e:
        raise ConfigFileError(f"Error creating config directory: {e}") from e

    # Check if directory is writable
    if not os.access(config_dir, os.W_OK):
        raise ConfigFileError(
            f"Config directory {config_dir} is not writable. "
            f"Please fix permissions:\n"
            f"  chmod 755 {config_dir}"
        )


def _create_default_config_file() -> None:
    """Create the default configuration file.

    Raises:
        ConfigFileError: If the file cannot be created
    """
    _ensure_config_dir()
    config_path = get_config_path()

    default_config = _create_default_config()

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
    except PermissionError as e:
        raise ConfigFileError(
            f"Cannot write config file at {config_path}. "
            f"Please check permissions."
        ) from e
    except OSError as e:
        raise ConfigFileError(f"Error writing config file: {e}") from e


def load_config() -> Config:
    """Load configuration from file, creating default if missing.

    Returns:
        Config object with loaded or default values

    Raises:
        ConfigFileError: If there are issues reading/writing the config file
        ConfigValidationError: If the configuration is invalid
    """
    config_path = get_config_path()

    # Create default config if it doesn't exist
    if not config_path.exists():
        _create_default_config_file()
        return Config()

    # Load existing config
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigFileError(
            f"Invalid YAML in config file {config_path}:\n{e}"
        ) from e
    except PermissionError as e:
        raise ConfigFileError(
            f"Cannot read config file at {config_path}. "
            f"Please check permissions."
        ) from e
    except OSError as e:
        raise ConfigFileError(f"Error reading config file: {e}") from e

    if data is None:
        data = {}

    if not isinstance(data, dict):
        raise ConfigFileError(
            f"Config file must contain a YAML dictionary, got {type(data).__name__}"
        )

    # Merge with defaults
    default = _create_default_config()
    for key in default:
        if key not in data:
            data[key] = default[key]

    # Handle session_dir as Path
    session_dir = data.get("session_dir", default["session_dir"])
    if isinstance(session_dir, str):
        session_dir = Path(session_dir)

    # Create and validate config
    return Config(
        model=data.get("model", default["model"]),
        ollama_url=data.get("ollama_url", default["ollama_url"]),
        max_iterations=data.get("max_iterations", default["max_iterations"]),
        session_dir=session_dir,
    )


def save_config(config: Config) -> None:
    """Save configuration to file.

    Args:
        config: Config object to save

    Raises:
        ConfigFileError: If the file cannot be written
    """
    _ensure_config_dir()
    config_path = get_config_path()

    data = {
        "model": config.model,
        "ollama_url": config.ollama_url,
        "max_iterations": config.max_iterations,
        "session_dir": str(config.session_dir),
    }

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    except PermissionError as e:
        raise ConfigFileError(
            f"Cannot write config file at {config_path}. "
            f"Please check permissions."
        ) from e
    except OSError as e:
        raise ConfigFileError(f"Error writing config file: {e}") from e
