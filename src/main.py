"""Main entry point for loop orchestration CLI."""

import argparse
import sys
from pathlib import Path
from typing import NoReturn

from .config import load_config, Config
from .display import create_display, Display
from .health import check_ollama_health
from .loop_engine import create_loop_engine, LoopResult, LoopStatus
from .ollama_client import OllamaClient
from .phases import PhaseName
from .session import (
    create_session,
    save as save_session,
    load as load_session,
    list_sessions,
    Session,
)


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    print(f"Error: {message}", file=sys.stderr)


def cmd_start(args: argparse.Namespace, config: Config, display: Display) -> int:
    """Start a new session with the given task.

    Args:
        args: Parsed command line arguments
        config: Configuration
        display: Display instance

    Returns:
        Exit code
    """
    task = args.task
    project_root = args.project or str(Path.cwd())

    # Health check
    if not args.skip_check:
        health = check_ollama_health(config)
        if not health.healthy:
            print_error(health.message)
            return 1

    # Create session
    session = create_session(task, config.session_dir)
    display.show_status(f"Created session: {session.session_id}")

    # Save initial session
    save_session(session, config.session_dir)

    # Create client and engine
    client = OllamaClient(base_url=config.ollama_url)
    engine = create_loop_engine(
        client=client,
        config=config,
        display=display,
        session=session,
        initial_phase=PhaseName.PRD,
    )

    # Run the loop
    display.show_status(f"Starting task: {task[:50]}...")
    result = engine.run(
        task_description=task,
        project_root=project_root,
    )

    return _handle_result(result, display)


def cmd_resume(args: argparse.Namespace, config: Config, display: Display) -> int:
    """Resume an existing session.

    Args:
        args: Parsed command line arguments
        config: Configuration
        display: Display instance

    Returns:
        Exit code
    """
    session_id = args.session_id
    project_root = args.project or str(Path.cwd())

    # Load session
    try:
        session = load_session(session_id, config.session_dir)
    except FileNotFoundError:
        print_error(f"Session not found: {session_id}")
        return 1
    except ValueError as e:
        print_error(f"Failed to load session: {e}")
        return 1

    display.show_status(f"Resuming session: {session_id}")
    display.show_status(f"Task: {session.task_description[:50]}...")

    # Health check
    if not args.skip_check:
        health = check_ollama_health(config)
        if not health.healthy:
            print_error(health.message)
            return 1

    # Create client and engine
    client = OllamaClient(base_url=config.ollama_url)
    engine = create_loop_engine(
        client=client,
        config=config,
        display=display,
        session=session,
    )

    # Resume the loop
    result = engine.resume(
        project_root=project_root,
        user_input=args.input,
    )

    return _handle_result(result, display)


def cmd_list(args: argparse.Namespace, config: Config, display: Display) -> int:
    """List recent sessions.

    Args:
        args: Parsed command line arguments
        config: Configuration
        display: Display instance

    Returns:
        Exit code
    """
    sessions = list_sessions(config.session_dir)

    if not sessions:
        print("No sessions found.")
        return 0

    print(f"\n{'ID':<20} {'Phase':<15} {'Task':<40} {'Created'}")
    print("-" * 90)

    for info in sessions[:args.limit]:
        task = info.task_description
        task_preview = task[:37] + "..." if len(task) > 40 else task
        # created_at is already a string
        created = info.created_at[:16]  # Trim to YYYY-MM-DD HH:MM
        print(f"{info.session_id:<20} {info.current_phase:<15} {task_preview:<40} {created}")

    print(f"\nTotal: {len(sessions)} sessions")
    return 0


def _handle_result(result: LoopResult, display: Display) -> int:
    """Handle loop result and return exit code.

    Args:
        result: Loop execution result
        display: Display instance

    Returns:
        Exit code
    """
    if result.status == LoopStatus.COMPLETED:
        display.show_status(f"Task completed in {result.iterations} iterations")
        return 0

    if result.status == LoopStatus.INTERRUPTED:
        display.show_status("Session interrupted. State saved.", is_error=False)
        return 130  # Standard interrupt exit code

    if result.status == LoopStatus.NEEDS_INPUT:
        display.show_status("Waiting for user input. Resume with --resume")
        print(f"\nOutput:\n{result.output}")
        return 0

    if result.status == LoopStatus.MAX_ITERATIONS:
        display.show_status(result.reason, is_error=True)
        return 1

    if result.status == LoopStatus.ERROR:
        display.show_status(f"Error: {result.error}", is_error=True)
        return 1

    return 1


def main(argv: list[str] | None = None) -> int:
    """Main entry point.

    Args:
        argv: Command line arguments (defaults to sys.argv)

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        prog="loop",
        description="Local LLM-powered autonomous development workflow",
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output",
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip Ollama health check",
    )
    parser.add_argument(
        "--project", "-p",
        help="Project root directory (default: current directory)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show config debug info",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start a new session")
    start_parser.add_argument(
        "task",
        help="Task description",
    )

    # Resume command
    resume_parser = subparsers.add_parser("resume", help="Resume a session")
    resume_parser.add_argument(
        "session_id",
        help="Session ID to resume",
    )
    resume_parser.add_argument(
        "--input", "-i",
        help="Additional input to provide",
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List recent sessions")
    list_parser.add_argument(
        "--limit", "-n",
        type=int,
        default=10,
        help="Number of sessions to show",
    )

    args = parser.parse_args(argv)

    # Load config
    try:
        config = load_config()
    except Exception as e:
        print_error(f"Failed to load config: {e}")
        return 1

    # Debug: show config info
    if args.debug:
        from .config import get_config_path
        print(f"Config file: {get_config_path()}")
        print(f"Model: {config.model}")
        print(f"Ollama URL: {config.ollama_url}")
        print(f"Max iterations: {config.max_iterations}")
        print()

    # Create display
    display = create_display(quiet=args.quiet, log_dir=config.session_dir)

    # Handle commands
    if args.command == "start":
        return cmd_start(args, config, display)
    elif args.command == "resume":
        return cmd_resume(args, config, display)
    elif args.command == "list":
        return cmd_list(args, config, display)
    else:
        # No command - show help
        parser.print_help()
        return 0


def run() -> NoReturn:
    """Run the CLI and exit with the appropriate code."""
    sys.exit(main())


if __name__ == "__main__":
    run()
