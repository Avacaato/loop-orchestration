"""Shell command execution tool."""

import re
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class ShellResult:
    """Result of a shell command execution.

    Attributes:
        success: Whether the command succeeded (exit code 0)
        stdout: Standard output from the command
        stderr: Standard error from the command
        exit_code: Exit code of the command
        error: Error message if command was blocked or failed to execute
        metadata: Additional metadata about the execution
    """
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    error: str = ""
    metadata: dict[str, Any] | None = None


class ShellError(Exception):
    """Base exception for shell errors."""
    pass


class DangerousCommandError(ShellError):
    """Raised when a dangerous command is detected."""
    pass


# Patterns for dangerous commands that should be blocked
DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+(-[rf]+\s+)*[/\\]", "rm -rf / (delete root filesystem)"),
    (r"\brm\s+(-[rf]+\s+)*~", "rm -rf ~ (delete home directory)"),
    (r"\bmkfs\b", "mkfs (format filesystem)"),
    (r"\bdd\s+if=", "dd if= (low-level disk write)"),
    (r"\bshutdown\b", "shutdown (system shutdown)"),
    (r"\breboot\b", "reboot (system reboot)"),
    (r"\bhalt\b", "halt (system halt)"),
    (r"\bpoweroff\b", "poweroff (system poweroff)"),
    (r">\s*/dev/sd[a-z]", "write to raw disk device"),
    (r"\bformat\s+[a-z]:", "format drive (Windows)"),
    (r"\:(fork\s*bomb|:\(\)\{)", "fork bomb"),
]

# Maximum output size before truncation (100KB)
MAX_OUTPUT_SIZE = 100 * 1024


def _check_dangerous_command(command: str) -> None:
    """Check if a command matches dangerous patterns.

    Args:
        command: Command to check

    Raises:
        DangerousCommandError: If the command is dangerous
    """
    command_lower = command.lower()

    for pattern, description in DANGEROUS_PATTERNS:
        if re.search(pattern, command_lower):
            raise DangerousCommandError(
                f"Blocked dangerous command: {description}"
            )


def _truncate_output(output: str, max_size: int = MAX_OUTPUT_SIZE) -> tuple[str, bool]:
    """Truncate output if it exceeds max size.

    Args:
        output: Output string to potentially truncate
        max_size: Maximum size in bytes

    Returns:
        Tuple of (possibly truncated output, was_truncated)
    """
    if len(output.encode("utf-8")) <= max_size:
        return output, False

    # Truncate to max_size bytes
    encoded = output.encode("utf-8")[:max_size]
    # Decode safely, ignoring incomplete characters at the end
    truncated = encoded.decode("utf-8", errors="ignore")

    return truncated + "\n\n[output truncated]", True


def run_command(
    command: str,
    cwd: str | None = None,
    timeout: int = 60,
    env: dict[str, str] | None = None,
) -> ShellResult:
    """Run a shell command with safety checks.

    Args:
        command: Shell command to execute
        cwd: Working directory for the command
        timeout: Timeout in seconds (default: 60)
        env: Optional environment variables to set

    Returns:
        ShellResult with command output and status
    """
    # Check for dangerous commands
    try:
        _check_dangerous_command(command)
    except DangerousCommandError as e:
        return ShellResult(
            success=False,
            error=str(e),
            metadata={"blocked": True},
        )

    try:
        # Run the command
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )

        # Truncate outputs if necessary
        stdout, stdout_truncated = _truncate_output(result.stdout)
        stderr, stderr_truncated = _truncate_output(result.stderr)

        return ShellResult(
            success=result.returncode == 0,
            stdout=stdout,
            stderr=stderr,
            exit_code=result.returncode,
            metadata={
                "command": command,
                "cwd": cwd,
                "timeout": timeout,
                "stdout_truncated": stdout_truncated,
                "stderr_truncated": stderr_truncated,
            },
        )

    except subprocess.TimeoutExpired:
        return ShellResult(
            success=False,
            error=f"Command timed out after {timeout} seconds",
            metadata={
                "command": command,
                "timeout": timeout,
                "timed_out": True,
            },
        )

    except FileNotFoundError:
        return ShellResult(
            success=False,
            error="Shell not found. Cannot execute commands.",
        )

    except PermissionError:
        return ShellResult(
            success=False,
            error="Permission denied executing command",
        )

    except OSError as e:
        return ShellResult(
            success=False,
            error=f"Error executing command: {e}",
        )
