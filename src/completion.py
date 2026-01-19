"""Completion detection for knowing when to stop iterating."""

import re
from dataclasses import dataclass
from enum import Enum


class CompletionStatus(Enum):
    """Status of completion detection."""
    NOT_COMPLETE = "not_complete"
    TASK_COMPLETE = "task_complete"
    PHASE_COMPLETE = "phase_complete"
    NEEDS_USER_INPUT = "needs_user_input"
    MAX_ITERATIONS = "max_iterations"
    ERROR = "error"


@dataclass
class CompletionResult:
    """Result of completion detection.

    Attributes:
        status: The completion status
        reason: Human-readable reason for the status
        confidence: Confidence level (0.0 to 1.0) for implicit detection
    """
    status: CompletionStatus
    reason: str
    confidence: float = 1.0


class CompletionDetector:
    """Detects when a task or phase is complete.

    Looks for explicit markers in LLM output as well as
    implicit signals like tests passing or no more actions proposed.
    """

    # Explicit completion markers
    TASK_COMPLETE_MARKERS = [
        "[TASK_COMPLETE]",
        "[TASK COMPLETE]",
        "TASK_COMPLETE",
        "<task_complete>",
    ]

    PHASE_COMPLETE_MARKERS = [
        "[PHASE_COMPLETE]",
        "[PHASE COMPLETE]",
        "PHASE_COMPLETE",
        "<phase_complete>",
    ]

    NEEDS_INPUT_MARKERS = [
        "[NEEDS_USER_INPUT]",
        "[NEEDS USER INPUT]",
        "NEEDS_USER_INPUT",
        "<needs_user_input>",
        "[WAITING_FOR_USER]",
    ]

    # Patterns for implicit completion detection
    IMPLICIT_COMPLETE_PATTERNS = [
        # Tests passing
        (r"all\s+tests?\s+pass", 0.7),
        (r"tests?\s+passed", 0.6),
        (r"✓.*tests?\s+pass", 0.7),
        # Implementation complete phrases
        (r"implementation\s+is\s+complete", 0.8),
        (r"feature\s+is\s+complete", 0.8),
        (r"successfully\s+implemented", 0.7),
        # No more work needed
        (r"no\s+(more\s+)?changes?\s+(are\s+)?needed", 0.8),
        (r"nothing\s+(more\s+)?(to|left\s+to)\s+do", 0.8),
    ]

    # Patterns suggesting more work is needed
    ACTION_PATTERNS = [
        r"(let\s+me|i('ll|\s+will)|going\s+to)\s+(create|write|implement|add|fix|update)",
        r"(need\s+to|should|must)\s+(create|write|implement|add|fix|update)",
        r"(creating|writing|implementing|adding|fixing|updating)\s+",
        r"next,?\s+(i('ll|\s+will)|we\s+should)",
    ]

    def __init__(self) -> None:
        """Initialize the completion detector."""
        # Compile patterns for efficiency
        self._implicit_patterns = [
            (re.compile(pattern, re.IGNORECASE), confidence)
            for pattern, confidence in self.IMPLICIT_COMPLETE_PATTERNS
        ]
        self._action_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.ACTION_PATTERNS
        ]

    def detect(self, output: str) -> CompletionResult:
        """Detect completion status from LLM output.

        Args:
            output: The output text from the LLM

        Returns:
            CompletionResult with status and reason
        """
        output_upper = output.upper()

        # Check for explicit markers first (highest priority)

        # Check for user input needed
        for marker in self.NEEDS_INPUT_MARKERS:
            if marker.upper() in output_upper:
                return CompletionResult(
                    status=CompletionStatus.NEEDS_USER_INPUT,
                    reason=f"Explicit marker found: {marker}",
                    confidence=1.0,
                )

        # Check for task complete
        for marker in self.TASK_COMPLETE_MARKERS:
            if marker.upper() in output_upper:
                return CompletionResult(
                    status=CompletionStatus.TASK_COMPLETE,
                    reason=f"Explicit marker found: {marker}",
                    confidence=1.0,
                )

        # Check for phase complete
        for marker in self.PHASE_COMPLETE_MARKERS:
            if marker.upper() in output_upper:
                return CompletionResult(
                    status=CompletionStatus.PHASE_COMPLETE,
                    reason=f"Explicit marker found: {marker}",
                    confidence=1.0,
                )

        # Check for implicit completion signals
        for pattern, confidence in self._implicit_patterns:
            match = pattern.search(output)
            if match:
                # Check if there are also action patterns (suggesting more work)
                has_actions = any(
                    p.search(output) for p in self._action_patterns
                )
                if not has_actions:
                    return CompletionResult(
                        status=CompletionStatus.TASK_COMPLETE,
                        reason=f"Implicit completion detected: '{match.group()}'",
                        confidence=confidence,
                    )

        # Default: not complete
        return CompletionResult(
            status=CompletionStatus.NOT_COMPLETE,
            reason="No completion markers or signals detected",
            confidence=1.0,
        )

    def is_complete(self, output: str) -> bool:
        """Simple check if the output indicates completion.

        Args:
            output: The output text from the LLM

        Returns:
            True if task or phase is complete
        """
        result = self.detect(output)
        return result.status in (
            CompletionStatus.TASK_COMPLETE,
            CompletionStatus.PHASE_COMPLETE,
        )

    def needs_user_input(self, output: str) -> bool:
        """Check if the output indicates user input is needed.

        Args:
            output: The output text from the LLM

        Returns:
            True if user input is needed
        """
        result = self.detect(output)
        return result.status == CompletionStatus.NEEDS_USER_INPUT
