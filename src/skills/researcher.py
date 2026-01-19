"""Researcher skill for investigating codebases and gathering context."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import BaseSkill, SkillContext, SkillOutput, SkillTool, SkillToolType
from ..tools import read_file, list_dir, search_files, FileResult


@dataclass
class ResearchFindings:
    """Collected research findings.

    Attributes:
        architecture: Architecture notes
        key_files: Important files discovered
        patterns: Code patterns found
        dependencies: Dependencies identified
        notes: General notes
    """
    architecture: list[str] = field(default_factory=list)
    key_files: dict[str, str] = field(default_factory=dict)
    patterns: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class ResearcherSkill(BaseSkill):
    """Skill for researching codebases and gathering context.

    Explores file structure, reads key files, and documents
    architecture findings.
    """

    def __init__(self) -> None:
        """Initialize the researcher skill."""
        super().__init__()
        self._findings = ResearchFindings()
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
            name="list_dir",
            tool_type=SkillToolType.LIST_DIR,
            description="List directory contents",
            handler=self._list_dir,
        ))
        self.register_tool(SkillTool(
            name="search_files",
            tool_type=SkillToolType.SEARCH_FILES,
            description="Search for files by pattern",
            handler=self._search_files,
        ))

    @property
    def name(self) -> str:
        """Get skill name."""
        return "researcher"

    @property
    def description(self) -> str:
        """Get skill description."""
        return "Investigates codebases to understand architecture and gather context"

    @property
    def system_prompt(self) -> str:
        """Get system prompt for the LLM."""
        return """You are a Code Researcher. Your job is to explore and understand codebases.

Your goals:
1. Understand the project structure and architecture
2. Identify key files and their purposes
3. Document patterns and conventions used
4. Note dependencies and integrations
5. Gather context needed for implementation

Available tools:
- read_file(path): Read a file's contents
- list_dir(path): List directory contents
- search_files(pattern): Search for files matching a glob pattern

Research strategy:
1. Start by listing the root directory to understand structure
2. Read README, package.json, requirements.txt, or similar for overview
3. Explore src/ or main code directories
4. Read key configuration files
5. Document your findings as you go

Output your findings as structured markdown with sections:
- Architecture Overview
- Key Files
- Patterns & Conventions
- Dependencies
- Notes for Implementation

When you have gathered sufficient context, mark [PHASE_COMPLETE]."""

    def execute(self, context: SkillContext) -> SkillOutput:
        """Execute the researcher skill.

        Args:
            context: Execution context

        Returns:
            SkillOutput with research findings
        """
        # Validate context
        validation_error = self.validate_context(context)
        if validation_error:
            return self.create_error_output(validation_error)

        project_root = context.project_root

        # Auto-explore if this is initial execution
        if not self._findings.key_files:
            return self._initial_exploration(project_root)

        # Generate findings report
        return self._generate_report(project_root)

    def _initial_exploration(self, project_root: str) -> SkillOutput:
        """Perform initial exploration of the codebase.

        Args:
            project_root: Root directory to explore

        Returns:
            SkillOutput with exploration results
        """
        self.log_action("initial_exploration", {"root": project_root})

        # List root directory
        root_result = list_dir(".", project_root)
        if not root_result.success:
            return self.create_error_output(
                f"Failed to list root directory: {root_result.error}"
            )

        root_contents = root_result.output
        self._findings.notes.append(f"Root contents:\n{root_contents}")

        # Look for common project files
        common_files = [
            "README.md",
            "readme.md",
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "Cargo.toml",
            "go.mod",
            "pom.xml",
        ]

        for filename in common_files:
            result = read_file(filename, project_root)
            if result.success:
                self._findings.key_files[filename] = result.output[:500]
                self._analyze_project_file(filename, result.output)
                break

        # Search for source directories
        for pattern in ["src/**/*.py", "src/**/*.ts", "src/**/*.js", "lib/**/*.py"]:
            result = search_files(pattern, project_root)
            if result.success and result.output:
                files = result.output.split("\n")[:10]  # First 10 files
                self._findings.notes.append(f"Source files ({pattern}): {len(files)} found")
                break

        # Build initial report
        content = self._build_exploration_summary()
        content += "\n\nContinue exploring with read_file() and list_dir() tools."
        content += "\nMark [PHASE_COMPLETE] when you have enough context."

        return SkillOutput(
            success=True,
            content=content,
            metadata={"exploration": "initial"},
        )

    def _analyze_project_file(self, filename: str, content: str) -> None:
        """Analyze a project configuration file.

        Args:
            filename: Name of the file
            content: File contents
        """
        if filename == "package.json":
            self._findings.architecture.append("Node.js/JavaScript project")
            if '"dependencies"' in content:
                self._findings.dependencies.append("See package.json for npm dependencies")

        elif filename in ("requirements.txt", "pyproject.toml"):
            self._findings.architecture.append("Python project")
            if "pyproject.toml" in filename:
                self._findings.patterns.append("Uses modern pyproject.toml configuration")

        elif filename == "Cargo.toml":
            self._findings.architecture.append("Rust project")

        elif filename == "go.mod":
            self._findings.architecture.append("Go project")

    def _build_exploration_summary(self) -> str:
        """Build summary of exploration so far.

        Returns:
            Summary string
        """
        parts = ["## Initial Exploration Results\n"]

        if self._findings.architecture:
            parts.append("### Architecture")
            for item in self._findings.architecture:
                parts.append(f"- {item}")
            parts.append("")

        if self._findings.key_files:
            parts.append("### Key Files Found")
            for filename in self._findings.key_files:
                parts.append(f"- {filename}")
            parts.append("")

        if self._findings.notes:
            parts.append("### Notes")
            for note in self._findings.notes[:5]:  # First 5 notes
                parts.append(f"- {note[:200]}")

        return "\n".join(parts)

    def _generate_report(self, project_root: str) -> SkillOutput:
        """Generate final research report.

        Args:
            project_root: Project root directory

        Returns:
            SkillOutput with report
        """
        report = self._build_report()

        # Save report
        report_path = Path(project_root) / "tasks" / "research-findings.md"
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(report, encoding="utf-8")
        except OSError as e:
            return self.create_error_output(f"Failed to save report: {e}")

        self.log_action("report_generated", {"path": str(report_path)})

        return SkillOutput(
            success=True,
            content=f"Research report saved to {report_path}\n\n[PHASE_COMPLETE]",
            artifacts={"research-findings.md": report},
        )

    def _build_report(self) -> str:
        """Build the full research report.

        Returns:
            Report as markdown
        """
        parts = ["# Research Findings\n"]

        parts.append("## Architecture Overview\n")
        if self._findings.architecture:
            for item in self._findings.architecture:
                parts.append(f"- {item}")
        else:
            parts.append("- No architecture notes recorded")
        parts.append("")

        parts.append("## Key Files\n")
        if self._findings.key_files:
            for filename, summary in self._findings.key_files.items():
                parts.append(f"### {filename}")
                parts.append(f"```\n{summary[:300]}...\n```\n")
        else:
            parts.append("- No key files recorded")
        parts.append("")

        parts.append("## Patterns & Conventions\n")
        if self._findings.patterns:
            for pattern in self._findings.patterns:
                parts.append(f"- {pattern}")
        else:
            parts.append("- No patterns noted")
        parts.append("")

        parts.append("## Dependencies\n")
        if self._findings.dependencies:
            for dep in self._findings.dependencies:
                parts.append(f"- {dep}")
        else:
            parts.append("- No dependencies noted")
        parts.append("")

        parts.append("## Notes for Implementation\n")
        if self._findings.notes:
            for note in self._findings.notes:
                parts.append(f"- {note[:500]}")
        else:
            parts.append("- No additional notes")

        return "\n".join(parts)

    def _read_file(self, path: str, project_root: str) -> FileResult:
        """Tool handler for reading files.

        Args:
            path: File path
            project_root: Project root

        Returns:
            FileResult
        """
        result = read_file(path, project_root)
        if result.success:
            self._findings.key_files[path] = result.output[:500]
            self.log_action("read_file", {"path": path})
        return result

    def _list_dir(self, path: str, project_root: str) -> FileResult:
        """Tool handler for listing directories.

        Args:
            path: Directory path
            project_root: Project root

        Returns:
            FileResult
        """
        result = list_dir(path, project_root)
        if result.success:
            self.log_action("list_dir", {"path": path})
        return result

    def _search_files(self, pattern: str, project_root: str) -> FileResult:
        """Tool handler for searching files.

        Args:
            pattern: Glob pattern
            project_root: Project root

        Returns:
            FileResult
        """
        result = search_files(pattern, project_root)
        if result.success:
            self.log_action("search_files", {"pattern": pattern})
        return result

    def add_finding(
        self,
        category: str,
        finding: str,
    ) -> None:
        """Add a finding to the appropriate category.

        Args:
            category: Category (architecture, patterns, dependencies, notes)
            finding: The finding to add
        """
        if category == "architecture":
            self._findings.architecture.append(finding)
        elif category == "patterns":
            self._findings.patterns.append(finding)
        elif category == "dependencies":
            self._findings.dependencies.append(finding)
        else:
            self._findings.notes.append(finding)

    def reset(self) -> None:
        """Reset research findings."""
        self._findings = ResearchFindings()
        self.clear_log()

    def get_state(self) -> dict[str, Any]:
        """Get current state.

        Returns:
            State dictionary
        """
        return {
            "architecture": list(self._findings.architecture),
            "key_files": dict(self._findings.key_files),
            "patterns": list(self._findings.patterns),
            "dependencies": list(self._findings.dependencies),
            "notes": list(self._findings.notes),
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore state.

        Args:
            state: State dictionary
        """
        self._findings.architecture = list(state.get("architecture", []))
        self._findings.key_files = dict(state.get("key_files", {}))
        self._findings.patterns = list(state.get("patterns", []))
        self._findings.dependencies = list(state.get("dependencies", []))
        self._findings.notes = list(state.get("notes", []))
