"""Base skill class that all skills inherit from."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable


class SkillToolType(Enum):
    """Types of tools available to skills."""
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    LIST_DIR = "list_dir"
    SEARCH_FILES = "search_files"
    RUN_COMMAND = "run_command"


@dataclass
class SkillTool:
    """Definition of a tool available to a skill.

    Attributes:
        name: Tool identifier
        tool_type: Type of tool
        description: Human-readable description
        handler: Function to execute the tool
    """
    name: str
    tool_type: SkillToolType
    description: str
    handler: Callable[..., Any]


@dataclass
class SkillContext:
    """Context passed to skill execution.

    Attributes:
        project_root: Root directory of the project
        task_description: Current task being worked on
        conversation_history: Previous messages in the conversation
        phase: Current workflow phase
        skill_outputs: Outputs from previous skills
        metadata: Additional context data
    """
    project_root: str
    task_description: str
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    phase: str = ""
    skill_outputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillOutput:
    """Output from skill execution.

    Attributes:
        success: Whether the skill completed successfully
        content: The main output content
        artifacts: Any files or data created
        next_action: Suggested next action
        error: Error message if failed
        metadata: Additional output data
    """
    success: bool
    content: str
    artifacts: dict[str, str] = field(default_factory=dict)
    next_action: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseSkill(ABC):
    """Abstract base class for all skills.

    Skills are specialized agents that perform specific tasks
    in the development workflow.
    """

    def __init__(self) -> None:
        """Initialize the skill."""
        self._tools: list[SkillTool] = []
        self._log_entries: list[dict[str, Any]] = []

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the skill name.

        Returns:
            Skill identifier
        """
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Get the skill description.

        Returns:
            Human-readable description
        """
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Get the system prompt for this skill.

        Returns:
            System prompt string for the LLM
        """
        ...

    @abstractmethod
    def execute(self, context: SkillContext) -> SkillOutput:
        """Execute the skill.

        Args:
            context: Execution context

        Returns:
            SkillOutput with results
        """
        ...

    @abstractmethod
    def reset(self) -> None:
        """Reset the skill state."""
        ...

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """Get current skill state for persistence.

        Returns:
            State dictionary
        """
        ...

    @abstractmethod
    def set_state(self, state: dict[str, Any]) -> None:
        """Restore skill state.

        Args:
            state: State dictionary
        """
        ...

    def get_tools(self) -> list[SkillTool]:
        """Get available tools for this skill.

        Returns:
            List of available tools
        """
        return list(self._tools)

    def register_tool(self, tool: SkillTool) -> None:
        """Register a tool for this skill.

        Args:
            tool: Tool to register
        """
        self._tools.append(tool)

    def log_action(
        self,
        action: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Log an action performed by the skill.

        Args:
            action: Description of the action
            details: Optional additional details
        """
        entry: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "skill": self.name,
            "action": action,
        }
        if details:
            entry["details"] = details
        self._log_entries.append(entry)

    def get_log_entries(self) -> list[dict[str, Any]]:
        """Get all log entries from this skill.

        Returns:
            List of log entries
        """
        return list(self._log_entries)

    def clear_log(self) -> None:
        """Clear log entries."""
        self._log_entries.clear()

    def format_output(
        self,
        content: str,
        section_title: str | None = None,
        code_blocks: dict[str, str] | None = None,
    ) -> str:
        """Format output as markdown.

        Args:
            content: Main content text
            section_title: Optional section header
            code_blocks: Optional code blocks (language -> code)

        Returns:
            Formatted markdown string
        """
        parts: list[str] = []

        if section_title:
            parts.append(f"## {section_title}\n")

        parts.append(content)

        if code_blocks:
            for lang, code in code_blocks.items():
                parts.append(f"\n```{lang}\n{code}\n```")

        return "\n".join(parts)

    def create_success_output(
        self,
        content: str,
        artifacts: dict[str, str] | None = None,
        next_action: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SkillOutput:
        """Create a successful output.

        Args:
            content: Output content
            artifacts: Optional artifacts created
            next_action: Optional suggested next action
            metadata: Optional metadata

        Returns:
            SkillOutput with success=True
        """
        return SkillOutput(
            success=True,
            content=content,
            artifacts=artifacts or {},
            next_action=next_action,
            metadata=metadata or {},
        )

    def create_error_output(
        self,
        error: str,
        content: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> SkillOutput:
        """Create an error output.

        Args:
            error: Error message
            content: Optional content
            metadata: Optional metadata

        Returns:
            SkillOutput with success=False
        """
        return SkillOutput(
            success=False,
            content=content,
            error=error,
            metadata=metadata or {},
        )

    def validate_context(self, context: SkillContext) -> str | None:
        """Validate execution context.

        Override in subclasses to add custom validation.

        Args:
            context: Context to validate

        Returns:
            Error message if invalid, None if valid
        """
        if not context.project_root:
            return "Project root is required"
        return None

    def __repr__(self) -> str:
        """Get string representation."""
        return f"{self.__class__.__name__}(name={self.name!r})"
