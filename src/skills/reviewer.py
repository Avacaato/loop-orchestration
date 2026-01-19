"""Reviewer skill for checking code quality and suggesting improvements."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import BaseSkill, SkillContext, SkillOutput, SkillTool, SkillToolType
from ..tools import read_file, search_files, run_command, FileResult, ShellResult


@dataclass
class ReviewItem:
    """A single review item.

    Attributes:
        file: File path
        line: Line number (if applicable)
        severity: low, medium, high
        category: Type of issue
        message: Description of the issue
        suggestion: Suggested fix
    """
    file: str
    line: int | None
    severity: str
    category: str
    message: str
    suggestion: str = ""


@dataclass
class ReviewFindings:
    """Collected review findings.

    Attributes:
        items: List of review items
        summary: Overall summary
        passed: Whether the review passed
    """
    items: list[ReviewItem] = field(default_factory=list)
    summary: str = ""
    passed: bool = True


class ReviewerSkill(BaseSkill):
    """Skill for reviewing code quality.

    Checks for common issues, style problems, and suggests
    improvements.
    """

    def __init__(self) -> None:
        """Initialize the reviewer skill."""
        super().__init__()
        self._findings = ReviewFindings()
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
            name="search_files",
            tool_type=SkillToolType.SEARCH_FILES,
            description="Search for files by pattern",
            handler=self._search_files,
        ))
        self.register_tool(SkillTool(
            name="run_command",
            tool_type=SkillToolType.RUN_COMMAND,
            description="Run a shell command (e.g., linter)",
            handler=self._run_command,
        ))

    @property
    def name(self) -> str:
        """Get skill name."""
        return "reviewer"

    @property
    def description(self) -> str:
        """Get skill description."""
        return "Reviews code quality and suggests improvements"

    @property
    def system_prompt(self) -> str:
        """Get system prompt for the LLM."""
        return """You are a Code Reviewer. Your job is to check code quality and identify issues.

Review categories:
1. **Bugs**: Potential bugs or logic errors
2. **Security**: Security vulnerabilities (injection, XSS, etc.)
3. **Performance**: Performance issues or inefficiencies
4. **Style**: Code style and readability issues
5. **Best Practices**: Violations of language/framework best practices

Available tools:
- read_file(path): Read a file's contents
- search_files(pattern): Search for files
- run_command(cmd): Run linters or type checkers

Review process:
1. Search for source files to review
2. Read each file and analyze
3. Run available linters/checkers if applicable
4. Document issues with severity (low, medium, high)
5. Provide specific suggestions for fixes

Output format for each issue:
```
[SEVERITY] Category: File:Line
Issue: Description
Suggestion: How to fix
```

When review is complete, provide a summary with:
- Total issues by severity
- Overall assessment (PASS/FAIL)
- Priority items to address

Mark [PHASE_COMPLETE] when the review is done."""

    def execute(self, context: SkillContext) -> SkillOutput:
        """Execute the reviewer skill.

        Args:
            context: Execution context

        Returns:
            SkillOutput with review findings
        """
        # Validate context
        validation_error = self.validate_context(context)
        if validation_error:
            return self.create_error_output(validation_error)

        project_root = context.project_root

        # Run automated checks if available
        self._run_automated_checks(project_root)

        # Generate review report
        return self._generate_report(project_root)

    def _run_automated_checks(self, project_root: str) -> None:
        """Run automated code checks.

        Args:
            project_root: Project root directory
        """
        # Try running common linters/checkers
        checks = [
            ("python -m mypy . --ignore-missing-imports", "mypy"),
            ("python -m flake8 . --max-line-length=100", "flake8"),
            ("npm run lint 2>/dev/null || true", "eslint"),
        ]

        for cmd, tool_name in checks:
            result = run_command(cmd, cwd=project_root, timeout=30)
            if result.success or result.stdout or result.stderr:
                output = result.stdout or result.stderr
                if output.strip():
                    self._parse_linter_output(tool_name, output)
                    self.log_action("ran_check", {"tool": tool_name})

    def _parse_linter_output(self, tool: str, output: str) -> None:
        """Parse linter output into review items.

        Args:
            tool: Name of the linter tool
            output: Linter output
        """
        lines = output.strip().split("\n")

        for line in lines[:20]:  # Limit to first 20 issues
            if not line.strip():
                continue

            # Generic parsing - extract file:line if present
            parts = line.split(":", 3)
            if len(parts) >= 3:
                try:
                    file_path = parts[0]
                    line_num = int(parts[1])
                    message = parts[2].strip() if len(parts) > 2 else line

                    self.add_issue(
                        file=file_path,
                        line=line_num,
                        severity="medium",
                        category=tool,
                        message=message,
                    )
                except (ValueError, IndexError):
                    # Can't parse, add as generic note
                    self._findings.items.append(ReviewItem(
                        file="",
                        line=None,
                        severity="low",
                        category=tool,
                        message=line[:200],
                    ))

    def _generate_report(self, project_root: str) -> SkillOutput:
        """Generate review report.

        Args:
            project_root: Project root directory

        Returns:
            SkillOutput with report
        """
        report = self._build_report()

        # Save report
        report_path = Path(project_root) / "tasks" / "review-report.md"
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(report, encoding="utf-8")
        except OSError as e:
            return self.create_error_output(f"Failed to save report: {e}")

        self.log_action("report_generated", {"path": str(report_path)})

        status = "PASS" if self._findings.passed else "FAIL"

        return SkillOutput(
            success=True,
            content=f"Review complete: {status}\n\n"
                    f"Report saved to {report_path}\n\n[PHASE_COMPLETE]",
            artifacts={"review-report.md": report},
            metadata={"passed": self._findings.passed},
        )

    def _build_report(self) -> str:
        """Build the review report.

        Returns:
            Report as markdown
        """
        parts = ["# Code Review Report\n"]

        # Count by severity
        high = len([i for i in self._findings.items if i.severity == "high"])
        medium = len([i for i in self._findings.items if i.severity == "medium"])
        low = len([i for i in self._findings.items if i.severity == "low"])

        self._findings.passed = high == 0

        parts.append("## Summary\n")
        parts.append(f"- **High severity**: {high}")
        parts.append(f"- **Medium severity**: {medium}")
        parts.append(f"- **Low severity**: {low}")
        parts.append(f"- **Status**: {'PASS' if self._findings.passed else 'FAIL'}")
        parts.append("")

        if self._findings.items:
            parts.append("## Issues\n")

            # Group by severity
            for severity in ["high", "medium", "low"]:
                items = [i for i in self._findings.items if i.severity == severity]
                if items:
                    parts.append(f"### {severity.title()} Severity\n")
                    for item in items:
                        loc = f"{item.file}"
                        if item.line:
                            loc += f":{item.line}"
                        parts.append(f"**[{item.category}]** {loc}")
                        parts.append(f"- {item.message}")
                        if item.suggestion:
                            parts.append(f"- *Suggestion*: {item.suggestion}")
                        parts.append("")
        else:
            parts.append("## Issues\n")
            parts.append("No issues found.")

        return "\n".join(parts)

    def add_issue(
        self,
        file: str,
        line: int | None,
        severity: str,
        category: str,
        message: str,
        suggestion: str = "",
    ) -> None:
        """Add a review issue.

        Args:
            file: File path
            line: Line number
            severity: low, medium, high
            category: Issue category
            message: Issue description
            suggestion: Suggested fix
        """
        self._findings.items.append(ReviewItem(
            file=file,
            line=line,
            severity=severity,
            category=category,
            message=message,
            suggestion=suggestion,
        ))

        if severity == "high":
            self._findings.passed = False

        self.log_action("issue_added", {
            "file": file,
            "severity": severity,
            "category": category,
        })

    def _read_file(self, path: str, project_root: str) -> FileResult:
        """Tool handler for reading files."""
        result = read_file(path, project_root)
        if result.success:
            self.log_action("read_file", {"path": path})
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
        self.log_action("run_command", {"command": command})
        return result

    def reset(self) -> None:
        """Reset review findings."""
        self._findings = ReviewFindings()
        self.clear_log()

    def get_state(self) -> dict[str, Any]:
        """Get current state."""
        return {
            "items": [
                {
                    "file": i.file,
                    "line": i.line,
                    "severity": i.severity,
                    "category": i.category,
                    "message": i.message,
                    "suggestion": i.suggestion,
                }
                for i in self._findings.items
            ],
            "passed": self._findings.passed,
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore state."""
        self._findings = ReviewFindings()
        for item_data in state.get("items", []):
            self._findings.items.append(ReviewItem(
                file=item_data.get("file", ""),
                line=item_data.get("line"),
                severity=item_data.get("severity", "low"),
                category=item_data.get("category", ""),
                message=item_data.get("message", ""),
                suggestion=item_data.get("suggestion", ""),
            ))
        self._findings.passed = state.get("passed", True)
