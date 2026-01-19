# Loop Orchestration

Local LLM-powered autonomous development workflow tool. Runs entirely on your own hardware using Ollama - no cloud API costs.

## What It Does

Loop Orchestration creates self-referential agent loops that autonomously handle software development tasks. It walks you through defining what you want to build, then executes a structured workflow:

1. **PRD Phase** - Interactive discovery interview to understand your requirements
2. **Tickets Phase** - Breaks down the PRD into actionable user stories
3. **Research Phase** - Explores the codebase to understand architecture
4. **Planning Phase** - Creates an implementation plan
5. **Implementation Phase** - Writes the code
6. **Refactoring Phase** - Improves code quality

Each phase uses a specialized "skill" with a focused system prompt and access to file/shell tools.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.ai/) running locally
- An Ollama model (e.g., `llama3.2`, `codellama`, `deepseek-coder`)

## Installation

```bash
# Clone the repo
git clone https://github.com/Avacaato/loop-orchestration.git
cd loop-orchestration

# Install Python dependencies
pip install httpx pyyaml

# Install type stubs (for development)
pip install types-PyYAML

# Pull an Ollama model
ollama pull llama3.2
```

## Configuration

Create `~/.loop-orchestration/config.yaml`:

```yaml
model: llama3.2
ollama_url: http://localhost:11434
max_iterations: 50
```

**Configuration options:**
- `model` - Ollama model to use (default: `llama3.2`)
- `ollama_url` - Ollama API endpoint (default: `http://localhost:11434`)
- `max_iterations` - Maximum loop iterations before stopping (default: `50`)

## Usage

### Start a new project

```bash
./loop.sh "Build a todo app with React"
```

Or with Python directly:

```bash
python -m src.main start "Build a todo app with React"
```

The tool will start an interactive PRD interview, asking questions like:
- What problem does this solve?
- Who are the target users?
- What are the core features?

Answer with A/B/C/D options or type your own response.

### Resume a session

```bash
./loop.sh --resume SESSION_ID
```

### List sessions

```bash
./loop.sh --list
```

### Session management

```bash
# List all sessions
./loop-sessions.sh list

# Show session details
./loop-sessions.sh show SESSION_ID

# Delete a session
./loop-sessions.sh delete SESSION_ID
```

## Project Structure

```
src/
├── ollama_client.py    # Ollama REST API client
├── config.py           # Configuration management
├── health.py           # Startup health checks
├── session.py          # Session persistence
├── completion.py       # Completion detection
├── display.py          # Progress display
├── phases.py           # Phase management
├── loop_engine.py      # Core autonomous loop
├── skill_orchestrator.py # Skill selection
├── main.py             # CLI entry point
├── session_cli.py      # Session management CLI
├── tools/
│   ├── file_ops.py     # File read/write/search
│   └── shell.py        # Shell command execution
└── skills/
    ├── base.py             # Abstract base skill
    ├── prd_interviewer.py  # PRD discovery interview
    ├── researcher.py       # Codebase exploration
    ├── reviewer.py         # Code review
    ├── implementer.py      # Code implementation
    └── refactorer.py       # Code improvement
```

## How It Works

1. **Loop Engine** sends prompts to Ollama and checks responses for completion markers
2. **Completion Detector** looks for explicit markers (`[TASK_COMPLETE]`, `[PHASE_COMPLETE]`) or implicit signals
3. **Phase Manager** automatically transitions between phases when completion criteria are met
4. **Skills** provide specialized system prompts and tool access for each phase
5. **Session Persistence** saves state so you can interrupt (Ctrl+C) and resume later

## Safety Features

- **Dangerous command blocking** - Blocks `rm -rf /`, `mkfs`, `shutdown`, etc.
- **Path traversal protection** - Prevents escaping project root with `..`
- **Configurable timeouts** - Shell commands timeout after 60 seconds
- **Max iteration limit** - Prevents infinite loops
- **Graceful interruption** - Ctrl+C saves state before exiting

## Development

Run type checks:

```bash
python -m mypy src --strict
```

## License

MIT
