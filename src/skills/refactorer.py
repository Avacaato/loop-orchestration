"""Refactorer skill for improving code quality."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import BaseSkill, SkillContext, SkillOutput, SkillTool, SkillToolType
from ..tools import read_file, write_file, search_files, run_command, FileResult, ShellResult


@dataclass
class RefactorItem:
    """A refactoring to perform.

    Attributes:
        file: File path
        category: Type of refactoring
        description: What to refactor
        completed: Whether completed
    """
    file: str
    category: str
    description: str
    completed: bool = False


@dataclass
class RefactorState:
    """State of refactoring.

    Attributes:
        items: Refactoring items
        files_modified: Files modified during refactoring
    """
    items: list[RefactorItem] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)


class RefactorerSkill(BaseSkill):
    """Skill for refactoring and improving code.

    Reviews code for improvement opportunities and applies
    refactoring while maintaining functionality.
    """

    def __init__(self) -> None:
        """Initialize the refactorer skill."""
        super().__init__()
        self._state = RefactorState()
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
            name="search_files",
            tool_type=SkillToolType.SEARCH_FILES,
            description="Search for files by pattern",
            handler=self._search_files,
        ))
        self.register_tool(SkillTool(
            name="run_command",
            tool_type=SkillToolType.RUN_COMMAND,
            description="Run tests or type checks",
            handler=self._run_command,
        ))

    @property
    def name(self) -> str:
        """Get skill name."""
        return "refactorer"

    @property
    def description(self) -> str:
        """Get skill description."""
        return "Improves code quality through refactoring"

    @property
    def system_prompt(self) -> str:
        """Get system prompt for the LLM."""
        return """You are a Code Refactorer. Your job is to improve code quality.

Look for these improvement opportunities:
1. **Duplication**: Extract common code into functions/classes
2. **Naming**: Improve variable/function/class names for clarity
3. **Complexity**: Simplify complex functions, reduce nesting
4. **Error Handling**: Add missing error handling
5. **Performance**: Optimize obvious inefficiencies
6. **Documentation**: Add missing docstrings/comments for complex logic

Available tools:
- read_file(path): Read a file's contents
- write_file(path, content): Write content to a file
- search_files(pattern): Search for files
- run_command(cmd): Run tests to verify changes don't break anything

Refactoring process:
1. Read files to analyze
2. Identify improvement opportunities
3. Make one change at a time
4. Run tests after each change
5. Only proceed if tests pass

IMPORTANT:
- Do NOT change functionality
- Run tests after every change
- Revert if tests fail
- Keep changes small and focused

When refactoring is complete and tests pass, mark [TASK_COMPLETE]."""

    def execute(self, context: SkillContext) -> SkillOutput:
        """Execute the refactorer skill.

        Args:
            context: Execution context

        Returns:
            SkillOutput with refactoring status
        """
        # Validate context
        validation_error = self.validate_context(context)
        if validation_error:
            return self.create_error_output(validation_error)

        # Check for review findings to guide refactoring
        if not self._state.items:
            self._load_from_review(context)

        # Check if all items done
        completed = all(i.completed for i in self._state.items)
        if completed and self._state.items:
            return self._generate_summary(context.project_root)

        # Get next item to work on
        next_item = self._get_next_item()
        if next_item:
            return SkillOutput(
                success=True,
                content=f"Refactoring: {next_item.file}\n"
                        f"Category: {next_item.category}\n"
                        f"Task: {next_item.description}\n\n"
                        "Read the file, make improvements, run tests, "
                        "then mark complete.",
                metadata={"current_file": next_item.file},
            )

        return SkillOutput(
            success=True,
            content="No refactoring items. Review code and add items, "
                    "or mark [TASK_COMPLETE] if done.",
        )

    def _load_from_review(self, context: SkillContext) -> None:
        """Load refactoring items from review findings.

        Args:
            context: Execution context
        """
        review_data = context.skill_outputs.get("reviewer", {})
        items = review_data.get("items", [])

        for item in items:
            if isinstance(item, dict):
                severity = item.get("severity", "low")
                # Skip high severity - those should be fixed, not refactored
                if severity != "high":
                    self._state.items.append(RefactorItem(
                        file=item.get("file", ""),
                        category=item.get("category", "general"),
                        description=item.get("message", ""),
                    ))

    def _get_next_item(self) -> RefactorItem | None:
        """Get the next item to refactor.

        Returns:
            Next item or None
        """
        for item in self._state.items:
            if not item.completed:
                return item
        return None

    def _generate_summary(self, project_root: str) -> SkillOutput:
        """Generate refactoring summary.

        Args:
            project_root: Project root directory

        Returns:
            SkillOutput with summary
        """
        completed = len([i for i in self._state.items if i.completed])
        total = len(self._state.items)

        summary = f"""# Refactoring Summary

## Progress
- Completed: {completed}/{total} items
- Files modified: {len(self._state.files_modified)}

## Refactoring Completed
"""
        for item in self._state.items:
            status = "✓" if item.completed else "○"
            summary += f"- [{status}] {item.file}: {item.description[:50]}\n"

        if self._state.files_modified:
            summary += "\n## Files Modified\n"
            for f in set(self._state.files_modified):
                summary += f"- {f}\n"

        # Save summary
        summary_path = Path(project_root) / "tasks" / "refactoring-summary.md"
        try:
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(summary, encoding="utf-8")
        except OSError:
            pass  # Non-critical

        return SkillOutput(
            success=True,
            content=summary + "\n\n[TASK_COMPLETE]",
            artifacts={"refactoring-summary.md": summary},
        )

    def add_item(
        self,
        file: str,
        category: str,
        description: str,
    ) -> None:
        """Add a refactoring item.

        Args:
            file: File to refactor
            category: Type of refactoring
            description: What to do
        """
        self._state.items.append(RefactorItem(
            file=file,
            category=category,
            description=description,
        ))
        self.log_action("item_added", {"file": file, "category": category})

    def mark_complete(self, file: str) -> bool:
        """Mark a refactoring item as complete.

        Args:
            file: File that was refactored

        Returns:
            True if found and marked
        """
        for item in self._state.items:
            if item.file == file and not item.completed:
                item.completed = True
                self.log_action("item_completed", {"file": file})
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
        result = write_file(path, content, project_root)
        if result.success:
            if path not in self._state.files_modified:
                self._state.files_modified.append(path)
            self.log_action("write_file", {"path": path})
        return result

    def _search_files(self, pattern: str, project_root: str) -> FileResult:
        """Tool handler for searching files."""
        result = search_files(pattern, project_root)
        if result.success:
            self.log_action("search_files", {"pattern": pattern})
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
        """Reset refactoring state."""
        self._state = RefactorState()
        self.clear_log()

    def get_state(self) -> dict[str, Any]:
        """Get current state."""
        return {
            "items": [
                {
                    "file": i.file,
                    "category": i.category,
                    "description": i.description,
                    "completed": i.completed,
                }
                for i in self._state.items
            ],
            "files_modified": list(self._state.files_modified),
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore state."""
        self._state = RefactorState()
        for item_data in state.get("items", []):
            self._state.items.append(RefactorItem(
                file=item_data.get("file", ""),
                category=item_data.get("category", ""),
                description=item_data.get("description", ""),
                completed=item_data.get("completed", False),
            ))
        self._state.files_modified = list(state.get("files_modified", []))
