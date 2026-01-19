"""Progress display and logging for user feedback."""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO


class Display:
    """Handles progress display and logging.

    Provides methods for showing progress to the user and
    logging LLM interactions to files.
    """

    def __init__(
        self,
        quiet: bool = False,
        log_dir: Path | None = None,
        output: TextIO | None = None,
    ) -> None:
        """Initialize the display.

        Args:
            quiet: If True, only show minimal output
            log_dir: Directory to write log files to
            output: Output stream (defaults to stdout)
        """
        self.quiet = quiet
        self.log_dir = log_dir
        self.output = output or sys.stdout
        self._log_file: TextIO | None = None

    def _write(self, message: str, end: str = "\n") -> None:
        """Write a message to the output stream.

        Args:
            message: Message to write
            end: String to append after message
        """
        self.output.write(message + end)
        self.output.flush()

    def show_phase(self, phase: str, description: str = "") -> None:
        """Display the current phase.

        Args:
            phase: Name of the current phase
            description: Optional description
        """
        if self.quiet:
            return

        self._write("")
        self._write(f"{'=' * 50}")
        self._write(f"Phase: {phase}")
        if description:
            self._write(f"  {description}")
        self._write(f"{'=' * 50}")
        self._write("")

    def show_iteration(self, iteration: int, max_iterations: int) -> None:
        """Display the current iteration.

        Args:
            iteration: Current iteration number
            max_iterations: Maximum number of iterations
        """
        if self.quiet:
            return

        self._write(f"\n--- Iteration {iteration}/{max_iterations} ---")

    def show_action(self, action: str) -> None:
        """Display the current action being performed.

        Args:
            action: Description of the action
        """
        if self.quiet:
            return

        # Truncate long actions
        if len(action) > 100:
            action = action[:97] + "..."

        self._write(f"  → {action}")

    def show_status(self, status: str, is_error: bool = False) -> None:
        """Display a status message.

        Args:
            status: Status message
            is_error: If True, format as error
        """
        prefix = "✗" if is_error else "✓"
        if not self.quiet or is_error:
            self._write(f"{prefix} {status}")

    def show_progress(
        self,
        current: int,
        total: int,
        label: str = "",
    ) -> None:
        """Display a progress indicator.

        Args:
            current: Current progress value
            total: Total value
            label: Optional label
        """
        if self.quiet:
            return

        percentage = (current / total * 100) if total > 0 else 0
        bar_width = 30
        filled = int(bar_width * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        label_str = f" {label}" if label else ""
        self._write(f"\r  [{bar}] {percentage:.0f}%{label_str}", end="")

        if current >= total:
            self._write("")  # New line when complete

    def show_summary(
        self,
        phase: str,
        iteration: int,
        status: str,
    ) -> None:
        """Display a summary of the current state.

        Args:
            phase: Current phase name
            iteration: Current iteration number
            status: Current status message
        """
        self._write(f"\n[{phase}] Iteration {iteration}: {status}")

    def log_interaction(
        self,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log an LLM interaction.

        Args:
            role: The role (user, assistant, system)
            content: The message content
            metadata: Optional metadata
        """
        if not self.log_dir:
            return

        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create or append to log file
        log_file = self.log_dir / "interactions.jsonl"

        entry: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
        }
        if metadata:
            entry["metadata"] = metadata

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            # Silently ignore logging errors
            pass

    def start_session_log(self, session_id: str) -> None:
        """Start logging for a session.

        Args:
            session_id: The session identifier
        """
        if not self.log_dir:
            return

        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Log session start
        self.log_interaction(
            role="system",
            content=f"Session started: {session_id}",
            metadata={"event": "session_start", "session_id": session_id},
        )

    def end_session_log(self, session_id: str, reason: str = "") -> None:
        """End logging for a session.

        Args:
            session_id: The session identifier
            reason: Reason for ending
        """
        if not self.log_dir:
            return

        self.log_interaction(
            role="system",
            content=f"Session ended: {session_id}",
            metadata={
                "event": "session_end",
                "session_id": session_id,
                "reason": reason,
            },
        )


def create_display(
    quiet: bool = False,
    log_dir: Path | None = None,
) -> Display:
    """Create a Display instance.

    Args:
        quiet: If True, minimal output
        log_dir: Optional directory for logs

    Returns:
        Configured Display instance
    """
    return Display(quiet=quiet, log_dir=log_dir)
