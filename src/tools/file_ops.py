"""File operation tools for reading and writing files."""

import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class FileResult:
    """Result of a file operation.

    Attributes:
        success: Whether the operation succeeded
        output: The output content (for read operations)
        error: Error message if operation failed
        metadata: Additional metadata about the operation
    """
    success: bool
    output: str = ""
    error: str = ""
    metadata: dict[str, Any] | None = None


class FileOperationError(Exception):
    """Base exception for file operation errors."""
    pass


class PathTraversalError(FileOperationError):
    """Raised when a path traversal attack is detected."""
    pass


def _validate_path(path: Path, project_root: Path) -> Path:
    """Validate that a path doesn't escape the project root.

    Args:
        path: Path to validate
        project_root: Root directory that paths cannot escape

    Returns:
        Resolved absolute path

    Raises:
        PathTraversalError: If the path would escape the project root
    """
    # Resolve both paths to absolute
    resolved_path = path.resolve()
    resolved_root = project_root.resolve()

    # Check if the resolved path is within the project root
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError:
        raise PathTraversalError(
            f"Path '{path}' escapes project root. "
            f"Paths containing '..' that escape the project directory are not allowed."
        )

    return resolved_path


def _is_binary_file(file_path: Path, sample_size: int = 1024) -> bool:
    """Check if a file is binary by looking for null bytes.

    Args:
        file_path: Path to the file
        sample_size: Number of bytes to check (default: 1KB)

    Returns:
        True if the file appears to be binary
    """
    try:
        with open(file_path, "rb") as f:
            sample = f.read(sample_size)
            return b"\x00" in sample
    except OSError:
        return False


def read_file(
    path: str | Path,
    project_root: str | Path,
) -> FileResult:
    """Read a file's contents.

    Args:
        path: Path to the file (relative or absolute)
        project_root: Root directory for path validation

    Returns:
        FileResult with the file contents or error
    """
    file_path = Path(path)
    root_path = Path(project_root)

    # Handle relative paths
    if not file_path.is_absolute():
        file_path = root_path / file_path

    # Validate path doesn't escape project root
    try:
        validated_path = _validate_path(file_path, root_path)
    except PathTraversalError as e:
        return FileResult(
            success=False,
            error=str(e),
        )

    # Check file exists
    if not validated_path.exists():
        return FileResult(
            success=False,
            error=f"File not found: {path}",
        )

    if not validated_path.is_file():
        return FileResult(
            success=False,
            error=f"Not a file: {path}",
        )

    # Check if binary
    if _is_binary_file(validated_path):
        return FileResult(
            success=False,
            error=f"Cannot read binary file: {path}",
            metadata={"is_binary": True},
        )

    # Read file
    try:
        content = validated_path.read_text(encoding="utf-8")
        return FileResult(
            success=True,
            output=content,
            metadata={
                "path": str(validated_path),
                "size": validated_path.stat().st_size,
                "lines": content.count("\n") + 1,
            },
        )
    except PermissionError:
        return FileResult(
            success=False,
            error=f"Permission denied: {path}",
        )
    except UnicodeDecodeError:
        return FileResult(
            success=False,
            error=f"Cannot decode file as UTF-8: {path}",
            metadata={"encoding_error": True},
        )
    except OSError as e:
        return FileResult(
            success=False,
            error=f"Error reading file: {e}",
        )


def write_file(
    path: str | Path,
    content: str,
    project_root: str | Path,
) -> FileResult:
    """Write content to a file.

    Creates parent directories if they don't exist.

    Args:
        path: Path to the file (relative or absolute)
        content: Content to write
        project_root: Root directory for path validation

    Returns:
        FileResult indicating success or error
    """
    file_path = Path(path)
    root_path = Path(project_root)

    # Handle relative paths
    if not file_path.is_absolute():
        file_path = root_path / file_path

    # Validate path doesn't escape project root
    try:
        validated_path = _validate_path(file_path, root_path)
    except PathTraversalError as e:
        return FileResult(
            success=False,
            error=str(e),
        )

    # Create parent directories
    try:
        validated_path.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        return FileResult(
            success=False,
            error=f"Permission denied creating directory: {validated_path.parent}",
        )
    except OSError as e:
        return FileResult(
            success=False,
            error=f"Error creating directory: {e}",
        )

    # Write file
    try:
        validated_path.write_text(content, encoding="utf-8")
        return FileResult(
            success=True,
            output=f"Wrote {len(content)} bytes to {path}",
            metadata={
                "path": str(validated_path),
                "size": len(content.encode("utf-8")),
                "lines": content.count("\n") + 1,
            },
        )
    except PermissionError:
        return FileResult(
            success=False,
            error=f"Permission denied: {path}",
        )
    except OSError as e:
        return FileResult(
            success=False,
            error=f"Error writing file: {e}",
        )


def list_dir(
    path: str | Path,
    project_root: str | Path,
    pattern: str | None = None,
) -> FileResult:
    """List contents of a directory.

    Args:
        path: Path to the directory (relative or absolute)
        project_root: Root directory for path validation
        pattern: Optional glob pattern to filter results

    Returns:
        FileResult with list of files/directories
    """
    dir_path = Path(path)
    root_path = Path(project_root)

    # Handle relative paths
    if not dir_path.is_absolute():
        dir_path = root_path / dir_path

    # Validate path doesn't escape project root
    try:
        validated_path = _validate_path(dir_path, root_path)
    except PathTraversalError as e:
        return FileResult(
            success=False,
            error=str(e),
        )

    if not validated_path.exists():
        return FileResult(
            success=False,
            error=f"Directory not found: {path}",
        )

    if not validated_path.is_dir():
        return FileResult(
            success=False,
            error=f"Not a directory: {path}",
        )

    try:
        entries: list[str] = []
        for entry in sorted(validated_path.iterdir()):
            name = entry.name
            if pattern and not fnmatch.fnmatch(name, pattern):
                continue

            # Add trailing slash for directories
            if entry.is_dir():
                name += "/"
            entries.append(name)

        return FileResult(
            success=True,
            output="\n".join(entries),
            metadata={
                "path": str(validated_path),
                "count": len(entries),
            },
        )
    except PermissionError:
        return FileResult(
            success=False,
            error=f"Permission denied: {path}",
        )
    except OSError as e:
        return FileResult(
            success=False,
            error=f"Error listing directory: {e}",
        )


def search_files(
    pattern: str,
    project_root: str | Path,
    path: str | Path | None = None,
) -> FileResult:
    """Search for files matching a pattern.

    Args:
        pattern: Glob pattern to match (e.g., "*.py", "**/*.txt")
        project_root: Root directory for search
        path: Optional subdirectory to search in

    Returns:
        FileResult with list of matching files
    """
    root_path = Path(project_root)
    search_path = root_path

    if path:
        search_path = Path(path)
        if not search_path.is_absolute():
            search_path = root_path / search_path

        # Validate path doesn't escape project root
        try:
            search_path = _validate_path(search_path, root_path)
        except PathTraversalError as e:
            return FileResult(
                success=False,
                error=str(e),
            )

    if not search_path.exists():
        return FileResult(
            success=False,
            error=f"Search path not found: {path or project_root}",
        )

    try:
        matches: list[str] = []
        for match in search_path.glob(pattern):
            # Get relative path from project root
            try:
                rel_path = match.relative_to(root_path)
                matches.append(str(rel_path))
            except ValueError:
                matches.append(str(match))

        matches.sort()

        return FileResult(
            success=True,
            output="\n".join(matches),
            metadata={
                "pattern": pattern,
                "search_path": str(search_path),
                "count": len(matches),
            },
        )
    except PermissionError:
        return FileResult(
            success=False,
            error=f"Permission denied searching: {search_path}",
        )
    except OSError as e:
        return FileResult(
            success=False,
            error=f"Error searching files: {e}",
        )
