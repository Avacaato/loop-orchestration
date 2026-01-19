"""Session management CLI for loop orchestration."""

import argparse
import sys
from pathlib import Path

from .config import load_config
from .session import (
    load as load_session,
    list_sessions,
    delete_session,
    Session,
)


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    print(f"Error: {message}", file=sys.stderr)


def cmd_list(args: argparse.Namespace, session_dir: Path) -> int:
    """List all sessions.

    Args:
        args: Parsed arguments
        session_dir: Sessions directory

    Returns:
        Exit code
    """
    sessions = list_sessions(session_dir)

    if not sessions:
        print("No sessions found.")
        return 0

    print(f"\n{'ID':<20} {'Phase':<15} {'Task':<40} {'Created'}")
    print("-" * 90)

    for info in sessions[:args.limit]:
        task = info.task_description
        task_preview = task[:37] + "..." if len(task) > 40 else task
        created = info.created_at[:16]
        print(f"{info.session_id:<20} {info.current_phase:<15} {task_preview:<40} {created}")

    print(f"\nTotal: {len(sessions)} sessions")
    return 0


def cmd_show(args: argparse.Namespace, session_dir: Path) -> int:
    """Show session details.

    Args:
        args: Parsed arguments
        session_dir: Sessions directory

    Returns:
        Exit code
    """
    session_id = args.session_id

    try:
        session = load_session(session_id, session_dir)
    except FileNotFoundError:
        print_error(f"Session not found: {session_id}")
        return 1
    except ValueError as e:
        print_error(f"Failed to load session: {e}")
        return 1

    print(f"\nSession: {session.session_id}")
    print(f"{'=' * 60}")
    print(f"Task: {session.task_description}")
    print(f"Phase: {session.current_phase}")
    print(f"Created: {session.created_at}")
    print(f"Updated: {session.updated_at}")
    print(f"Messages: {len(session.conversation_history)}")

    if args.verbose:
        print(f"\n{'Conversation History':-^60}")
        for i, msg in enumerate(session.conversation_history[-10:], 1):
            role = msg.role.upper()
            content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            print(f"{i}. [{role}] {content}")

        if session.skill_outputs:
            print(f"\n{'Skill Outputs':-^60}")
            for skill, output in session.skill_outputs.items():
                print(f"- {skill}: {len(str(output))} chars")

    return 0


def cmd_resume(args: argparse.Namespace, session_dir: Path) -> int:
    """Resume a session (prints command to run).

    Args:
        args: Parsed arguments
        session_dir: Sessions directory

    Returns:
        Exit code
    """
    session_id = args.session_id

    try:
        session = load_session(session_id, session_dir)
    except FileNotFoundError:
        print_error(f"Session not found: {session_id}")
        return 1
    except ValueError as e:
        print_error(f"Failed to load session: {e}")
        return 1

    print(f"To resume session '{session_id}':")
    print(f"  ./loop.sh --resume {session_id}")
    print(f"\nSession task: {session.task_description[:60]}...")

    return 0


def cmd_delete(args: argparse.Namespace, session_dir: Path) -> int:
    """Delete a session.

    Args:
        args: Parsed arguments
        session_dir: Sessions directory

    Returns:
        Exit code
    """
    session_id = args.session_id

    # Confirm deletion unless --force
    if not args.force:
        try:
            session = load_session(session_id, session_dir)
            print(f"Session: {session_id}")
            print(f"Task: {session.task_description[:60]}...")
            confirm = input("Delete this session? [y/N] ")
            if confirm.lower() != "y":
                print("Cancelled.")
                return 0
        except FileNotFoundError:
            print_error(f"Session not found: {session_id}")
            return 1
        except ValueError:
            # Can't load, but try to delete anyway
            pass

    try:
        delete_session(session_id, session_dir)
        print(f"Deleted session: {session_id}")
        return 0
    except FileNotFoundError:
        print_error(f"Session not found: {session_id}")
        return 1
    except OSError as e:
        print_error(f"Failed to delete session: {e}")
        return 1


def main(argv: list[str] | None = None) -> int:
    """Main entry point.

    Args:
        argv: Command line arguments

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        prog="loop-sessions",
        description="Manage loop orchestration sessions",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List command
    list_parser = subparsers.add_parser("list", help="List all sessions")
    list_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=20,
        help="Number of sessions to show",
    )

    # Show command
    show_parser = subparsers.add_parser("show", help="Show session details")
    show_parser.add_argument(
        "session_id",
        help="Session ID",
    )
    show_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show more details",
    )

    # Resume command
    resume_parser = subparsers.add_parser("resume", help="Resume a session")
    resume_parser.add_argument(
        "session_id",
        help="Session ID",
    )

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a session")
    delete_parser.add_argument(
        "session_id",
        help="Session ID",
    )
    delete_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Skip confirmation",
    )

    args = parser.parse_args(argv)

    # Load config
    try:
        config = load_config()
    except Exception as e:
        print_error(f"Failed to load config: {e}")
        return 1

    session_dir = config.session_dir

    # Handle commands
    if args.command == "list":
        return cmd_list(args, session_dir)
    elif args.command == "show":
        return cmd_show(args, session_dir)
    elif args.command == "resume":
        return cmd_resume(args, session_dir)
    elif args.command == "delete":
        return cmd_delete(args, session_dir)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
