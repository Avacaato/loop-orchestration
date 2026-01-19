"""Implementer skill for writing code to fulfill user stories."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import BaseSkill, SkillContext, SkillOutput, SkillTool, SkillToolType
from ..tools import read_file, write_file, list_dir, run_command, FileResult, ShellResult


@dataclass
class ImplementationTask:
    """A task to implement.

    Attributes:
        story_id: User story ID
        description: What to implement
        files: Files to create/modify
        completed: Whether completed
    """
    story_id: str
    description: str
    files: list[str] = field(default_factory=list)
    completed: bool = False


@dataclass
class ImplementationState:
    """State of implementation.

    Attributes:
        tasks: Tasks to implement
        current_task: Index of current task
        files_created: Files created
        files_modified: Files modified
    """
    tasks: list[ImplementationTask] = field(default_factory=list)
    current_task: int = 0
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)


class ImplementerSkill(BaseSkill):
    """Skill for implementing code changes.

    Takes user stories and implements them by creating
    or modifying code files.
    """

    def __init__(self) -> None:
        """Initialize the implementer skill."""
        super().__init__()
        self._state = ImplementationState()
        self._setup_tools()

    def _setup_tools(self) -> None:
        """Set up available tools."""
        self.register_tool(SkillTool(
            name="read_file",
            tool_type=SkillToolType.READ_FILE,
            description="Read contents of a file",
            handler=self._read_file,
        ))
        self.register_tool(SkillTool(
            name="write_file",
            tool_type=SkillToolType.WRITE_FILE,
            description="Write content to a file",
            handler=self._write_file,
        ))
        self.register_tool(SkillTool(
            name="list_dir",
            tool_type=SkillToolType.LIST_DIR,
            description="List directory contents",
            handler=self._list_dir,
        ))
        self.register_tool(SkillTool(
            name="run_command",
            tool_type=SkillToolType.RUN_COMMAND,
            description="Run a shell command",
            handler=self._run_command,
        ))

    @property
    def name(self) -> str:
        """Get skill name."""
        return "implementer"

    @property
    def description(self) -> str:
        """Get skill description."""
        return "Implements code changes based on user stories"

    @property
    def system_prompt(self) -> str:
        """Get system prompt for the LLM."""
        return """You are a Code Implementer. Your job is to write code that fulfills user stories.

Your workflow:
1. Read the current user story requirements
2. Read existing code to understand context
3. Implement the required functionality
4. Run tests to verify the implementation
5. Mark the story complete when done

Available tools:
- read_file(path): Read a file's contents
- write_file(path, content): Write content to a file
- list_dir(path): List directory contents
- run_command(cmd): Run shell commands (tests, type checks)

Implementation guidelines:
1. Write clean, readable code
2. Follow existing patterns in the codebase
3. Add appropriate error handling
4. Include type hints (for Python/TypeScript)
5. Run tests after changes
6. Keep changes focused - don't over-engineer

After implementing each story:
1. Run type checker (mypy, tsc) to verify types
2. Run tests if available
3. Mark the story as complete

When all assigned stories are complete, mark [PHASE_COMPLETE]."""

    def execute(self, context: SkillContext) -> SkillOutput:
        """Execute the implementer skill.

        Args:
            context: Execution context

        Returns:
            SkillOutput with implementation status
        """
        # Validate context
        validation_error = self.validate_context(context)
        if validation_error:
            return self.create_error_output(validation_error)

        # Check if we have tasks from skill_outputs
        if not self._state.tasks and context.skill_outputs:
            self._load_tasks_from_context(context)

        # Check if all tasks done
        completed = all(t.completed for t in self._state.tasks)
        if completed and self._state.tasks:
            return self._generate_summary(context.project_root)

        # Get current task
        current = self._get_current_task()
        if current:
            return SkillOutput(
                success=True,
                content=f"Working on: {current.story_id}\n"
                        f"Description: {current.description}\n\n"
                        "Use write_file() to implement, then run_command() "
                        "to test. Call mark_complete() when done.",
                metadata={"current_story": current.story_id},
            )

        return SkillOutput(
            success=True,
            content="No tasks to implement. Mark [PHASE_COMPLETE] if done.",
        )

    def _load_tasks_from_context(self, context: SkillContext) -> None:
        """Load implementation tasks from context.

        Args:
            context: Execution context
        """
        # Try to load from PRD artifacts
        prd_data = context.skill_outputs.get("prd_interviewer", {})
        stories = prd_data.get("stories", [])

        for story in stories:
            if isinstance(story, dict):
                self._state.tasks.append(ImplementationTask(
                    story_id=story.get("id", ""),
                    description=story.get("description", ""),
                ))

    def _get_current_task(self) -> ImplementationTask | None:
        """Get the current task to work on.

        Returns:
            Current task or None
        """
        for task in self._state.tasks:
            if not task.completed:
                return task
        return None

    def _generate_summary(self, project_root: str) -> SkillOutput:
        """Generate implementation summary.

        Args:
            project_root: Project root directory

        Returns:
            SkillOutput with summary
        """
        completed = len([t for t in self._state.tasks if t.completed])
        total = len(self._state.tasks)

        summary = f"""# Implementation Summary

## Progress
- Completed: {completed}/{total} stories
- Files created: {len(self._state.files_created)}
- Files modified: {len(self._state.files_modified)}

## Stories Completed
"""
        for task in self._state.tasks:
            status = "✓" if task.completed else "○"
            summary += f"- [{status}] {task.story_id}: {task.description[:50]}\n"

        if self._state.files_created:
            summary += "\n## Files Created\n"
            for f in self._state.files_created:
                summary += f"- {f}\n"

        if self._state.files_modified:
            summary += "\n## Files Modified\n"
            for f in self._state.files_modified:
                summary += f"- {f}\n"

        # Save summary
        summary_path = Path(project_root) / "tasks" / "implementation-summary.md"
        try:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(summary, encoding="utf-8")
        except OSError:
            pass  # Non-critical

        return SkillOutput(
            success=True,
            content=summary + "\n\n[PHASE_COMPLETE]",
            artifacts={"implementation-summary.md": summary},
        )

    def add_task(self, story_id: str, description: str) -> None:
        """Add a task to implement.

        Args:
            story_id: Story identifier
            description: What to implement
        """
        self._state.tasks.append(ImplementationTask(
            story_id=story_id,
            description=description,
        ))
        self.log_action("task_added", {"story_id": story_id})

    def mark_complete(self, story_id: str) -> bool:
        """Mark a task as complete.

        Args:
            story_id: Story to mark complete

        Returns:
            True if found and marked
        """
        for task in self._state.tasks:
            if task.story_id == story_id:
                task.completed = True
                self.log_action("task_completed", {"story_id": story_id})
                return True
        return False

    def _read_file(self, path: str, project_root: str) -> FileResult:
        """Tool handler for reading files."""
        result = read_file(path, project_root)
        if result.success:
            self.log_action("read_file", {"path": path})
        return result

    def _write_file(self, path: str, content: str, project_root: str) -> FileResult:
        """Tool handler for writing files."""
        # Check if file exists
        existing = read_file(path, project_root)
        is_new = not existing.success

        result = write_file(path, content, project_root)
        if result.success:
            if is_new:
                self._state.files_created.append(path)
            else:
                if path not in self._state.files_modified:
                    self._state.files_modified.append(path)
            self.log_action("write_file", {"path": path, "new": is_new})
        return result

    def _list_dir(self, path: str, project_root: str) -> FileResult:
        """Tool handler for listing directories."""
        result = list_dir(path, project_root)
        if result.success:
            self.log_action("list_dir", {"path": path})
        return result

    def _run_command(
        self,
        command: str,
        cwd: str | None = None,
        timeout: int = 60,
    ) -> ShellResult:
        """Tool handler for running commands."""
        result = run_command(command, cwd=cwd, timeout=timeout)
        self.log_action("run_command", {"command": command, "success": result.success})
        return result

    def reset(self) -> None:
        """Reset implementation state."""
        self._state = ImplementationState()
        self.clear_log()

    def get_state(self) -> dict[str, Any]:
        """Get current state."""
        return {
            "tasks": [
                {
                    "story_id": t.story_id,
                    "description": t.description,
                    "files": t.files,
                    "completed": t.completed,
                }
                for t in self._state.tasks
            ],
            "current_task": self._state.current_task,
            "files_created": list(self._state.files_created),
            "files_modified": list(self._state.files_modified),
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore state."""
        self._state = ImplementationState()
        for task_data in state.get("tasks", []):
            self._state.tasks.append(ImplementationTask(
                story_id=task_data.get("story_id", ""),
                description=task_data.get("description", ""),
                files=task_data.get("files", []),
                completed=task_data.get("completed", False),
            ))
        self._state.current_task = state.get("current_task", 0)
        self._state.files_created = list(state.get("files_created", []))
        self._state.files_modified = list(state.get("files_modified", []))
