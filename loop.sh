#!/bin/bash
# loop.sh - Main CLI wrapper for loop orchestration
#
# Usage:
#   ./loop.sh "task description"    - Start a new session
#   ./loop.sh --resume SESSION_ID   - Resume a session
#   ./loop.sh --list                - List recent sessions
#
# Options:
#   -q, --quiet         Minimal output
#   -p, --project DIR   Project root directory
#   --skip-check        Skip Ollama health check

set -e

# Find script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check Python is available
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "Error: Python not found. Please install Python 3.10+"
    exit 1
fi

# Use python3 if available, otherwise python
PYTHON=$(command -v python3 || command -v python)

# Parse arguments and route to appropriate command
show_help() {
    echo "Usage: ./loop.sh [OPTIONS] COMMAND"
    echo ""
    echo "Commands:"
    echo "  \"task description\"         Start a new session with the given task"
    echo "  --resume, -r SESSION_ID    Resume an existing session"
    echo "  --list, -l                  List recent sessions"
    echo "  --help, -h                  Show this help message"
    echo ""
    echo "Options:"
    echo "  -q, --quiet                 Minimal output"
    echo "  -p, --project DIR           Project root directory"
    echo "  --skip-check                Skip Ollama health check"
    echo ""
    echo "Examples:"
    echo "  ./loop.sh \"Build a todo app with React\""
    echo "  ./loop.sh --resume 20240115-abc123"
    echo "  ./loop.sh --list"
}

# Build arguments for Python
PYTHON_ARGS=()
COMMAND=""
TASK=""
SESSION_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -q|--quiet)
            PYTHON_ARGS+=("--quiet")
            shift
            ;;
        -p|--project)
            PYTHON_ARGS+=("--project" "$2")
            shift 2
            ;;
        --skip-check)
            PYTHON_ARGS+=("--skip-check")
            shift
            ;;
        -r|--resume)
            COMMAND="resume"
            SESSION_ID="$2"
            shift 2
            ;;
        -l|--list)
            COMMAND="list"
            shift
            ;;
        *)
            # If no command yet, treat as task description
            if [[ -z "$COMMAND" ]]; then
                COMMAND="start"
                TASK="$1"
            fi
            shift
            ;;
    esac
done

# Execute appropriate command
case "$COMMAND" in
    start)
        if [[ -z "$TASK" ]]; then
            echo "Error: No task description provided"
            echo "Usage: ./loop.sh \"task description\""
            exit 1
        fi
        exec "$PYTHON" -m src.main "${PYTHON_ARGS[@]}" start "$TASK"
        ;;
    resume)
        if [[ -z "$SESSION_ID" ]]; then
            echo "Error: No session ID provided"
            echo "Usage: ./loop.sh --resume SESSION_ID"
            exit 1
        fi
        exec "$PYTHON" -m src.main "${PYTHON_ARGS[@]}" resume "$SESSION_ID"
        ;;
    list)
        exec "$PYTHON" -m src.main "${PYTHON_ARGS[@]}" list
        ;;
    *)
        show_help
        exit 0
        ;;
esac
