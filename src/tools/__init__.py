"""Tools for skills to interact with the filesystem and shell."""

from .file_ops import (
    FileResult,
    read_file,
    write_file,
    list_dir,
    search_files,
)
from .shell import (
    ShellResult,
    run_command,
)

__all__ = [
    "FileResult",
    "read_file",
    "write_file",
    "list_dir",
    "search_files",
    "ShellResult",
    "run_command",
]
