#!/bin/bash
# loop-sessions.sh - Session management for loop orchestration
#
# Usage:
#   ./loop-sessions.sh list            - Show all sessions
#   ./loop-sessions.sh show ID         - Display session details
#   ./loop-sessions.sh resume ID       - Continue a session
#   ./loop-sessions.sh delete ID       - Remove a session

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

# Parse arguments
show_help() {
    echo "Usage: ./loop-sessions.sh COMMAND [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  list                  List all sessions"
    echo "  show SESSION_ID       Display session details"
    echo "  resume SESSION_ID     Continue a session (shows command)"
    echo "  delete SESSION_ID     Remove a session"
    echo ""
    echo "Options:"
    echo "  -n, --limit N         Number of sessions to show (list)"
    echo "  -v, --verbose         Show more details (show)"
    echo "  -f, --force           Skip confirmation (delete)"
    echo "  -h, --help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./loop-sessions.sh list"
    echo "  ./loop-sessions.sh show 20240115-abc123"
    echo "  ./loop-sessions.sh delete 20240115-abc123 --force"
}

COMMAND=""
SESSION_ID=""
PYTHON_ARGS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        list|show|resume|delete)
            COMMAND="$1"
            shift
            ;;
        -n|--limit)
            PYTHON_ARGS+=("--limit" "$2")
            shift 2
            ;;
        -v|--verbose)
            PYTHON_ARGS+=("--verbose")
            shift
            ;;
        -f|--force)
            PYTHON_ARGS+=("--force")
            shift
            ;;
        *)
            # Session ID
            if [[ -z "$SESSION_ID" ]]; then
                SESSION_ID="$1"
            fi
            shift
            ;;
    esac
done

# Validate and execute
case "$COMMAND" in
    list)
        exec "$PYTHON" -m src.session_cli list "${PYTHON_ARGS[@]}"
        ;;
    show)
        if [[ -z "$SESSION_ID" ]]; then
            echo "Error: Session ID required"
            echo "Usage: ./loop-sessions.sh show SESSION_ID"
            exit 1
        fi
        exec "$PYTHON" -m src.session_cli show "$SESSION_ID" "${PYTHON_ARGS[@]}"
        ;;
    resume)
        if [[ -z "$SESSION_ID" ]]; then
            echo "Error: Session ID required"
            echo "Usage: ./loop-sessions.sh resume SESSION_ID"
            exit 1
        fi
        exec "$PYTHON" -m src.session_cli resume "$SESSION_ID"
        ;;
    delete)
        if [[ -z "$SESSION_ID" ]]; then
            echo "Error: Session ID required"
            echo "Usage: ./loop-sessions.sh delete SESSION_ID"
            exit 1
        fi
        exec "$PYTHON" -m src.session_cli delete "$SESSION_ID" "${PYTHON_ARGS[@]}"
        ;;
    *)
        show_help
        exit 0
        ;;
esac
