"""Session persistence for saving and resuming workflows."""

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


class SessionError(Exception):
    """Base exception for session errors."""
    pass


class SessionCorruptedError(SessionError):
    """Raised when a session file is corrupted."""
    pass


class SessionNotFoundError(SessionError):
    """Raised when a session is not found."""
    pass


@dataclass
class SessionMessage:
    """A message in the conversation history."""
    role: str  # "user", "assistant", or "system"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Session:
    """A workflow session that can be persisted and resumed.

    Attributes:
        session_id: Unique identifier for the session
        task_description: The original task description
        current_phase: Current workflow phase
        conversation_history: List of messages in the conversation
        skill_outputs: Dictionary of outputs from each skill
        created_at: Timestamp when session was created
        updated_at: Timestamp of last update
        metadata: Additional session metadata
    """
    session_id: str
    task_description: str
    current_phase: str = "PRD"
    conversation_history: list[SessionMessage] = field(default_factory=list)
    skill_outputs: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation history.

        Args:
            role: The role of the message sender
            content: The message content
        """
        self.conversation_history.append(SessionMessage(role=role, content=content))
        self.updated_at = datetime.now().isoformat()

    def set_skill_output(self, skill_name: str, output: Any) -> None:
        """Store the output from a skill.

        Args:
            skill_name: Name of the skill
            output: The skill's output
        """
        self.skill_outputs[skill_name] = output
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary for serialization.

        Returns:
            Dictionary representation of the session
        """
        return {
            "session_id": self.session_id,
            "task_description": self.task_description,
            "current_phase": self.current_phase,
            "conversation_history": [
                {"role": m.role, "content": m.content, "timestamp": m.timestamp}
                for m in self.conversation_history
            ],
            "skill_outputs": self.skill_outputs,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """Create a session from a dictionary.

        Args:
            data: Dictionary representation of a session

        Returns:
            Session object

        Raises:
            SessionCorruptedError: If the data is invalid
        """
        try:
            history = [
                SessionMessage(
                    role=m["role"],
                    content=m["content"],
                    timestamp=m.get("timestamp", datetime.now().isoformat()),
                )
                for m in data.get("conversation_history", [])
            ]

            return cls(
                session_id=data["session_id"],
                task_description=data["task_description"],
                current_phase=data.get("current_phase", "PRD"),
                conversation_history=history,
                skill_outputs=data.get("skill_outputs", {}),
                created_at=data.get("created_at", datetime.now().isoformat()),
                updated_at=data.get("updated_at", datetime.now().isoformat()),
                metadata=data.get("metadata", {}),
            )
        except (KeyError, TypeError) as e:
            raise SessionCorruptedError(f"Invalid session data: {e}") from e


def generate_session_id() -> str:
    """Generate a unique session ID.

    Format: YYYYMMDD-HHMMSS-XXXX where XXXX is a short hash.

    Returns:
        Unique session ID string
    """
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    # Add some randomness via hash of timestamp + microseconds
    hash_input = f"{timestamp}-{now.microsecond}".encode()
    short_hash = hashlib.sha256(hash_input).hexdigest()[:4]
    return f"{timestamp}-{short_hash}"


def get_session_dir(base_dir: Path, session_id: str) -> Path:
    """Get the directory path for a session.

    Args:
        base_dir: Base sessions directory
        session_id: Session identifier

    Returns:
        Path to the session directory
    """
    return base_dir / session_id


def save(session: Session, base_dir: Path) -> None:
    """Save a session to disk using atomic writes.

    Uses write-to-temp-then-rename pattern to prevent corruption
    if the process is interrupted during write.

    Args:
        session: Session to save
        base_dir: Base sessions directory

    Raises:
        SessionError: If the session cannot be saved
    """
    session_dir = get_session_dir(base_dir, session.session_id)

    try:
        session_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        raise SessionError(
            f"Cannot create session directory at {session_dir}. "
            f"Please check permissions."
        ) from e
    except OSError as e:
        if "No space left" in str(e) or "disk full" in str(e).lower():
            raise SessionError(
                "Disk full. Cannot save session. "
                "Please free up disk space and try again."
            ) from e
        raise SessionError(f"Error creating session directory: {e}") from e

    state_file = session_dir / "state.json"
    data = session.to_dict()

    # Atomic write: write to temp file, then rename
    try:
        # Create temp file in same directory for atomic rename
        fd, temp_path = tempfile.mkstemp(
            dir=session_dir,
            prefix=".state-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # Atomic rename
            os.replace(temp_path, state_file)
        except Exception:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    except PermissionError as e:
        raise SessionError(
            f"Cannot write session file at {state_file}. "
            f"Please check permissions."
        ) from e
    except OSError as e:
        if "No space left" in str(e) or "disk full" in str(e).lower():
            raise SessionError(
                "Disk full. Cannot save session. "
                "Please free up disk space and try again."
            ) from e
        raise SessionError(f"Error saving session: {e}") from e


def load(session_id: str, base_dir: Path) -> Session:
    """Load a session from disk.

    Args:
        session_id: Session identifier
        base_dir: Base sessions directory

    Returns:
        Loaded Session object

    Raises:
        SessionNotFoundError: If the session does not exist
        SessionCorruptedError: If the session file is corrupted
        SessionError: For other errors
    """
    session_dir = get_session_dir(base_dir, session_id)
    state_file = session_dir / "state.json"

    if not session_dir.exists():
        raise SessionNotFoundError(f"Session '{session_id}' not found")

    if not state_file.exists():
        raise SessionCorruptedError(
            f"Session '{session_id}' is corrupted (missing state.json). "
            f"You can delete it with: rm -rf {session_dir}"
        )

    try:
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise SessionCorruptedError(
            f"Session '{session_id}' is corrupted (invalid JSON). "
            f"You can delete it with: rm -rf {session_dir}\n"
            f"Error: {e}"
        ) from e
    except PermissionError as e:
        raise SessionError(
            f"Cannot read session file at {state_file}. "
            f"Please check permissions."
        ) from e
    except OSError as e:
        raise SessionError(f"Error reading session: {e}") from e

    return Session.from_dict(data)


@dataclass
class SessionInfo:
    """Summary information about a session."""
    session_id: str
    task_description: str
    current_phase: str
    created_at: str
    updated_at: str


def list_sessions(base_dir: Path) -> list[SessionInfo]:
    """List all sessions in the sessions directory.

    Args:
        base_dir: Base sessions directory

    Returns:
        List of SessionInfo objects, sorted by updated_at (most recent first)
    """
    if not base_dir.exists():
        return []

    sessions: list[SessionInfo] = []

    for session_dir in base_dir.iterdir():
        if not session_dir.is_dir():
            continue

        state_file = session_dir / "state.json"
        if not state_file.exists():
            continue

        try:
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            sessions.append(SessionInfo(
                session_id=data.get("session_id", session_dir.name),
                task_description=data.get("task_description", "Unknown"),
                current_phase=data.get("current_phase", "Unknown"),
                created_at=data.get("created_at", "Unknown"),
                updated_at=data.get("updated_at", "Unknown"),
            ))
        except (json.JSONDecodeError, KeyError, OSError):
            # Skip corrupted sessions in listing
            continue

    # Sort by updated_at, most recent first
    sessions.sort(key=lambda s: s.updated_at, reverse=True)
    return sessions


def delete_session(session_id: str, base_dir: Path) -> None:
    """Delete a session and all its files.

    Args:
        session_id: Session identifier
        base_dir: Base sessions directory

    Raises:
        SessionNotFoundError: If the session does not exist
        SessionError: If the session cannot be deleted
    """
    session_dir = get_session_dir(base_dir, session_id)

    if not session_dir.exists():
        raise SessionNotFoundError(f"Session '{session_id}' not found")

    try:
        # Remove all files in the session directory
        for file in session_dir.iterdir():
            file.unlink()
        session_dir.rmdir()
    except PermissionError as e:
        raise SessionError(
            f"Cannot delete session directory at {session_dir}. "
            f"Please check permissions."
        ) from e
    except OSError as e:
        raise SessionError(f"Error deleting session: {e}") from e


def create_session(task_description: str, base_dir: Path) -> Session:
    """Create a new session and save it to disk.

    Args:
        task_description: Description of the task
        base_dir: Base sessions directory

    Returns:
        New Session object
    """
    session = Session(
        session_id=generate_session_id(),
        task_description=task_description,
    )
    save(session, base_dir)
    return session
