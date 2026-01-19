"""Skill orchestrator for selecting and invoking appropriate skills."""

from dataclasses import dataclass, field
from typing import Any

from .phases import PhaseName
from .skills import (
    BaseSkill,
    SkillContext,
    SkillOutput,
    PRDInterviewerSkill,
    ResearcherSkill,
    ReviewerSkill,
    ImplementerSkill,
    RefactorerSkill,
)


@dataclass
class SkillExecutionResult:
    """Result of skill execution.

    Attributes:
        skill_name: Name of the skill that was executed
        output: The skill's output
        phase: Phase during which skill was executed
        context_updates: Updates to pass to subsequent skills
    """
    skill_name: str
    output: SkillOutput
    phase: str
    context_updates: dict[str, Any] = field(default_factory=dict)


class SkillOrchestrator:
    """Orchestrates skill selection and execution.

    Maps phases to appropriate skills and manages context
    passing between skills.
    """

    # Default mapping of phases to skills
    PHASE_SKILL_MAP: dict[PhaseName, type[BaseSkill]] = {
        PhaseName.PRD: PRDInterviewerSkill,
        PhaseName.TICKETS: PRDInterviewerSkill,  # PRD skill can also handle tickets
        PhaseName.RESEARCH: ResearcherSkill,
        PhaseName.PLANNING: ResearcherSkill,  # Research skill can help with planning
        PhaseName.IMPLEMENTATION: ImplementerSkill,
        PhaseName.REFACTORING: RefactorerSkill,
    }

    def __init__(self) -> None:
        """Initialize the orchestrator."""
        self._skills: dict[str, BaseSkill] = {}
        self._skill_outputs: dict[str, SkillOutput] = {}
        self._context_data: dict[str, Any] = {}

        # Initialize all skills
        self._initialize_skills()

    def _initialize_skills(self) -> None:
        """Initialize all available skills."""
        skill_classes: list[type[BaseSkill]] = [
            PRDInterviewerSkill,
            ResearcherSkill,
            ReviewerSkill,
            ImplementerSkill,
            RefactorerSkill,
        ]

        for skill_class in skill_classes:
            skill = skill_class()
            self._skills[skill.name] = skill

    def get_skill_for_phase(self, phase: PhaseName) -> BaseSkill:
        """Get the default skill for a phase.

        Args:
            phase: The workflow phase

        Returns:
            The appropriate skill instance
        """
        skill_class = self.PHASE_SKILL_MAP.get(phase)
        if skill_class:
            # Find the initialized instance
            for skill in self._skills.values():
                if isinstance(skill, skill_class):
                    return skill

        # Fallback to implementer if no mapping
        return self._skills.get("implementer", list(self._skills.values())[0])

    def get_skill_by_name(self, name: str) -> BaseSkill | None:
        """Get a skill by name.

        Args:
            name: Skill name

        Returns:
            Skill instance or None
        """
        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        """List all available skill names.

        Returns:
            List of skill names
        """
        return list(self._skills.keys())

    def execute_skill(
        self,
        skill_name: str,
        project_root: str,
        task_description: str,
        conversation_history: list[dict[str, str]] | None = None,
        phase: str = "",
        additional_context: dict[str, Any] | None = None,
    ) -> SkillExecutionResult:
        """Execute a specific skill.

        Args:
            skill_name: Name of the skill to execute
            project_root: Project root directory
            task_description: Current task description
            conversation_history: Previous conversation messages
            phase: Current workflow phase
            additional_context: Additional context data

        Returns:
            SkillExecutionResult with output and updates
        """
        skill = self._skills.get(skill_name)
        if not skill:
            return SkillExecutionResult(
                skill_name=skill_name,
                output=SkillOutput(
                    success=False,
                    content="",
                    error=f"Skill '{skill_name}' not found",
                ),
                phase=phase,
            )

        # Build context
        context = self._build_context(
            project_root=project_root,
            task_description=task_description,
            conversation_history=conversation_history or [],
            phase=phase,
            additional_context=additional_context,
        )

        # Execute skill
        output = skill.execute(context)

        # Store output for future skills
        self._skill_outputs[skill_name] = output

        # Extract context updates from output
        context_updates: dict[str, Any] = {}
        if output.success:
            context_updates[skill_name] = {
                "content": output.content,
                "artifacts": output.artifacts,
                "metadata": output.metadata,
            }
            self._context_data.update(context_updates)

        return SkillExecutionResult(
            skill_name=skill_name,
            output=output,
            phase=phase,
            context_updates=context_updates,
        )

    def execute_for_phase(
        self,
        phase: PhaseName,
        project_root: str,
        task_description: str,
        conversation_history: list[dict[str, str]] | None = None,
        skill_override: str | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> SkillExecutionResult:
        """Execute the appropriate skill for a phase.

        Args:
            phase: The workflow phase
            project_root: Project root directory
            task_description: Current task description
            conversation_history: Previous conversation messages
            skill_override: Optional skill name to use instead of default
            additional_context: Additional context data

        Returns:
            SkillExecutionResult with output and updates
        """
        # Determine which skill to use
        if skill_override:
            skill = self.get_skill_by_name(skill_override)
            if not skill:
                return SkillExecutionResult(
                    skill_name=skill_override,
                    output=SkillOutput(
                        success=False,
                        content="",
                        error=f"Skill override '{skill_override}' not found",
                    ),
                    phase=phase.value,
                )
        else:
            skill = self.get_skill_for_phase(phase)

        return self.execute_skill(
            skill_name=skill.name,
            project_root=project_root,
            task_description=task_description,
            conversation_history=conversation_history,
            phase=phase.value,
            additional_context=additional_context,
        )

    def _build_context(
        self,
        project_root: str,
        task_description: str,
        conversation_history: list[dict[str, str]],
        phase: str,
        additional_context: dict[str, Any] | None,
    ) -> SkillContext:
        """Build execution context for a skill.

        Args:
            project_root: Project root directory
            task_description: Current task
            conversation_history: Previous messages
            phase: Current phase
            additional_context: Additional context

        Returns:
            SkillContext instance
        """
        # Combine stored context with additional
        skill_outputs = dict(self._context_data)
        if additional_context:
            skill_outputs.update(additional_context)

        return SkillContext(
            project_root=project_root,
            task_description=task_description,
            conversation_history=conversation_history,
            phase=phase,
            skill_outputs=skill_outputs,
        )

    def get_skill_output(self, skill_name: str) -> SkillOutput | None:
        """Get stored output from a skill.

        Args:
            skill_name: Name of the skill

        Returns:
            SkillOutput or None if not available
        """
        return self._skill_outputs.get(skill_name)

    def get_all_outputs(self) -> dict[str, SkillOutput]:
        """Get all stored skill outputs.

        Returns:
            Dictionary of skill name to output
        """
        return dict(self._skill_outputs)

    def clear_outputs(self) -> None:
        """Clear all stored skill outputs."""
        self._skill_outputs.clear()
        self._context_data.clear()

    def reset_skill(self, skill_name: str) -> bool:
        """Reset a specific skill's state.

        Args:
            skill_name: Name of the skill to reset

        Returns:
            True if skill was found and reset
        """
        skill = self._skills.get(skill_name)
        if skill:
            skill.reset()
            if skill_name in self._skill_outputs:
                del self._skill_outputs[skill_name]
            if skill_name in self._context_data:
                del self._context_data[skill_name]
            return True
        return False

    def reset_all(self) -> None:
        """Reset all skills and clear outputs."""
        for skill in self._skills.values():
            skill.reset()
        self.clear_outputs()

    def get_state(self) -> dict[str, Any]:
        """Get orchestrator state for persistence.

        Returns:
            State dictionary
        """
        skill_states: dict[str, Any] = {}
        for name, skill in self._skills.items():
            skill_states[name] = skill.get_state()

        return {
            "skill_states": skill_states,
            "context_data": dict(self._context_data),
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore orchestrator state.

        Args:
            state: State dictionary
        """
        # Restore skill states
        skill_states = state.get("skill_states", {})
        for name, skill_state in skill_states.items():
            skill = self._skills.get(name)
            if skill:
                skill.set_state(skill_state)

        # Restore context data
        self._context_data = dict(state.get("context_data", {}))


def create_orchestrator() -> SkillOrchestrator:
    """Create a new skill orchestrator.

    Returns:
        Configured SkillOrchestrator instance
    """
    return SkillOrchestrator()
