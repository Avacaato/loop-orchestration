"""Phase management for structured development workflow."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class PhaseName(Enum):
    """Names of workflow phases."""
    PRD = "prd"
    TICKETS = "tickets"
    RESEARCH = "research"
    PLANNING = "planning"
    IMPLEMENTATION = "implementation"
    REFACTORING = "refactoring"


@dataclass
class Phase:
    """Definition of a workflow phase.

    Attributes:
        name: The phase identifier
        description: Human-readable description
        entry_prompt: Prompt to send when entering this phase
        completion_criteria: Description of what triggers phase completion
        next_phase: The phase to transition to (None if final)
    """
    name: PhaseName
    description: str
    entry_prompt: str
    completion_criteria: str
    next_phase: PhaseName | None = None


# Define all workflow phases
PHASES: dict[PhaseName, Phase] = {
    PhaseName.PRD: Phase(
        name=PhaseName.PRD,
        description="Product Requirements Document - define what to build",
        entry_prompt=(
            "You are a PRD (Product Requirements Document) interviewer. "
            "DO NOT write any code yet. Your job is to ask the user questions to understand what they want to build.\n\n"
            "Ask ONE question at a time and wait for the user's response. Questions to ask:\n"
            "1. What do you want to name this project?\n"
            "2. What problem does this solve?\n"
            "3. Who will use this? (A. Just me, B. My team, C. Customers, D. Public)\n"
            "4. What are the 3 most important features?\n"
            "5. What does success look like?\n"
            "6. What is explicitly out of scope?\n\n"
            "Start by asking: 'What do you want to name this project?'\n"
            "After gathering all answers, generate a PRD document and mark [PHASE_COMPLETE]."
        ),
        completion_criteria="PRD document generated and saved",
        next_phase=PhaseName.TICKETS,
    ),
    PhaseName.TICKETS: Phase(
        name=PhaseName.TICKETS,
        description="Break down PRD into actionable tickets/stories",
        entry_prompt=(
            "You are in the TICKETS phase. Read the PRD and break it down into "
            "small, actionable user stories. Each story should be completable in "
            "one coding session. Order stories by dependencies (database first, "
            "then backend, then frontend). Save the stories to prd.json. Mark "
            "[PHASE_COMPLETE] when done."
        ),
        completion_criteria="User stories created and saved to prd.json",
        next_phase=PhaseName.RESEARCH,
    ),
    PhaseName.RESEARCH: Phase(
        name=PhaseName.RESEARCH,
        description="Research codebase and gather context",
        entry_prompt=(
            "You are in the RESEARCH phase. Explore the codebase to understand "
            "the architecture, existing patterns, and relevant files. Document "
            "your findings. Identify any constraints or dependencies. Mark "
            "[PHASE_COMPLETE] when you have enough context to plan implementation."
        ),
        completion_criteria="Research findings documented",
        next_phase=PhaseName.PLANNING,
    ),
    PhaseName.PLANNING: Phase(
        name=PhaseName.PLANNING,
        description="Plan implementation approach",
        entry_prompt=(
            "You are in the PLANNING phase. Based on the user stories and research "
            "findings, create an implementation plan. Identify which files to "
            "create/modify, the order of changes, and any risks. Mark "
            "[PHASE_COMPLETE] when you have a clear plan."
        ),
        completion_criteria="Implementation plan created",
        next_phase=PhaseName.IMPLEMENTATION,
    ),
    PhaseName.IMPLEMENTATION: Phase(
        name=PhaseName.IMPLEMENTATION,
        description="Implement the planned changes",
        entry_prompt=(
            "You are in the IMPLEMENTATION phase. Follow the plan to implement "
            "each user story. Write clean, well-tested code. Run tests and fix "
            "any failures. Mark each story complete when done. Mark "
            "[PHASE_COMPLETE] when all stories are implemented."
        ),
        completion_criteria="All user stories implemented and tests passing",
        next_phase=PhaseName.REFACTORING,
    ),
    PhaseName.REFACTORING: Phase(
        name=PhaseName.REFACTORING,
        description="Refactor and improve code quality",
        entry_prompt=(
            "You are in the REFACTORING phase. Review the implemented code for "
            "improvements. Look for: code duplication, unclear naming, missing "
            "error handling, performance issues. Make improvements without "
            "changing functionality. Run tests after each change. Mark "
            "[TASK_COMPLETE] when code quality is satisfactory."
        ),
        completion_criteria="Code reviewed and refactored",
        next_phase=None,  # Final phase
    ),
}


@dataclass
class PhaseTransition:
    """Record of a phase transition.

    Attributes:
        from_phase: The phase transitioned from
        to_phase: The phase transitioned to
        reason: Why the transition occurred
    """
    from_phase: PhaseName | None
    to_phase: PhaseName
    reason: str


class PhaseManager:
    """Manages phase transitions in the workflow.

    Tracks the current phase and handles transitions when
    completion criteria are met.
    """

    def __init__(
        self,
        initial_phase: PhaseName = PhaseName.PRD,
        on_transition: Callable[[PhaseTransition], None] | None = None,
    ) -> None:
        """Initialize the phase manager.

        Args:
            initial_phase: The starting phase
            on_transition: Optional callback for phase transitions
        """
        self._current_phase = initial_phase
        self._on_transition = on_transition
        self._history: list[PhaseTransition] = []

        # Record initial state
        transition = PhaseTransition(
            from_phase=None,
            to_phase=initial_phase,
            reason="Initial phase",
        )
        self._history.append(transition)

    @property
    def current_phase(self) -> Phase:
        """Get the current phase definition."""
        return PHASES[self._current_phase]

    @property
    def current_phase_name(self) -> PhaseName:
        """Get the current phase name."""
        return self._current_phase

    @property
    def history(self) -> list[PhaseTransition]:
        """Get the history of phase transitions."""
        return list(self._history)

    def can_advance(self) -> bool:
        """Check if there is a next phase to advance to.

        Returns:
            True if there is a next phase
        """
        return self.current_phase.next_phase is not None

    def advance(self, reason: str = "Completion criteria met") -> Phase | None:
        """Advance to the next phase.

        Args:
            reason: Reason for advancing

        Returns:
            The new phase, or None if already at final phase
        """
        next_phase = self.current_phase.next_phase
        if next_phase is None:
            return None

        transition = PhaseTransition(
            from_phase=self._current_phase,
            to_phase=next_phase,
            reason=reason,
        )
        self._history.append(transition)

        self._current_phase = next_phase

        if self._on_transition:
            self._on_transition(transition)

        return PHASES[next_phase]

    def set_phase(self, phase: PhaseName, reason: str = "Manual override") -> Phase:
        """Set the current phase directly (manual override).

        Args:
            phase: The phase to switch to
            reason: Reason for the override

        Returns:
            The new phase
        """
        if phase == self._current_phase:
            return PHASES[phase]

        transition = PhaseTransition(
            from_phase=self._current_phase,
            to_phase=phase,
            reason=reason,
        )
        self._history.append(transition)

        self._current_phase = phase

        if self._on_transition:
            self._on_transition(transition)

        return PHASES[phase]

    def get_entry_prompt(self) -> str:
        """Get the entry prompt for the current phase.

        Returns:
            The entry prompt string
        """
        return self.current_phase.entry_prompt

    def is_final_phase(self) -> bool:
        """Check if currently in the final phase.

        Returns:
            True if in the final phase
        """
        return self.current_phase.next_phase is None

    def to_dict(self) -> dict[str, str | list[dict[str, str | None]]]:
        """Serialize phase manager state to dict.

        Returns:
            Dictionary representation of the state
        """
        return {
            "current_phase": self._current_phase.value,
            "history": [
                {
                    "from_phase": t.from_phase.value if t.from_phase else None,
                    "to_phase": t.to_phase.value,
                    "reason": t.reason,
                }
                for t in self._history
            ],
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, str | list[dict[str, str | None]]],
        on_transition: Callable[[PhaseTransition], None] | None = None,
    ) -> "PhaseManager":
        """Deserialize phase manager from dict.

        Args:
            data: Dictionary representation
            on_transition: Optional callback for transitions

        Returns:
            PhaseManager instance
        """
        current_phase_str = data.get("current_phase")
        if not isinstance(current_phase_str, str):
            current_phase_str = "prd"
        current_phase = PhaseName(current_phase_str)

        manager = cls(initial_phase=current_phase, on_transition=on_transition)

        # Restore history if present
        history_data = data.get("history")
        if isinstance(history_data, list):
            manager._history = []
            for item in history_data:
                if isinstance(item, dict):
                    from_str = item.get("from_phase")
                    to_str = item.get("to_phase")
                    reason = item.get("reason", "")

                    from_phase = PhaseName(from_str) if from_str else None
                    to_phase = PhaseName(to_str) if to_str else PhaseName.PRD

                    manager._history.append(PhaseTransition(
                        from_phase=from_phase,
                        to_phase=to_phase,
                        reason=str(reason),
                    ))

        return manager


def get_phase(name: PhaseName) -> Phase:
    """Get a phase definition by name.

    Args:
        name: The phase name

    Returns:
        The Phase definition
    """
    return PHASES[name]


def get_all_phases() -> list[Phase]:
    """Get all phases in order.

    Returns:
        List of phases in workflow order
    """
    return [
        PHASES[PhaseName.PRD],
        PHASES[PhaseName.TICKETS],
        PHASES[PhaseName.RESEARCH],
        PHASES[PhaseName.PLANNING],
        PHASES[PhaseName.IMPLEMENTATION],
        PHASES[PhaseName.REFACTORING],
    ]
