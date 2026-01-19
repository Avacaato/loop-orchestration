# Architecture: Loop Orchestration

## Overview

Loop Orchestration is a Python-based autonomous development workflow tool that uses Ollama for local LLM inference.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                          │
│  loop.sh / loop-sessions.sh (Bash wrapper scripts)              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Python Entry Point                        │
│  src/main.py                                                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Loop Engine                              │
│  Executes task → checks completion → re-feeds prompt → repeat   │
│  src/loop_engine.py                                              │
└─────────────────────────────────────────────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
┌─────────────────────┐ ┌─────────────────┐ ┌─────────────────────┐
│   Phase Manager     │ │ Skill Orchestrator│ │ Completion Detector │
│   src/phases.py     │ │ src/skill_orch.py │ │ src/completion.py   │
└─────────────────────┘ └─────────────────┘ └─────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                           Skills                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │PRD Interviewer│ │  Researcher  │ │   Reviewer   │             │
│  └──────────────┘ └──────────────┘ └──────────────┘             │
│  ┌──────────────┐ ┌──────────────┐                               │
│  │ Implementer  │ │  Refactorer  │                               │
│  └──────────────┘ └──────────────┘                               │
│  src/skills/*.py                                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
┌─────────────────────┐ ┌─────────────────┐ ┌─────────────────────┐
│    File Operations  │ │  Shell Commands │ │   Ollama Client     │
│  src/tools/file_ops │ │ src/tools/shell │ │ src/ollama_client   │
└─────────────────────┘ └─────────────────┘ └─────────────────────┘
              │                 │                 │
              ▼                 ▼                 ▼
┌─────────────────────┐ ┌─────────────────┐ ┌─────────────────────┐
│     Filesystem      │ │   OS Shell      │ │   Ollama Server     │
│   (local codebase)  │ │   (bash/cmd)    │ │ (localhost:11434)   │
└─────────────────────┘ └─────────────────┘ └─────────────────────┘
```

## Component Details

### 1. CLI Layer (Bash Scripts)
- `loop.sh` - Main entry point, passes args to Python
- `loop-sessions.sh` - Session management commands
- Minimal logic, just wrapper for Python

### 2. Loop Engine
- Core iterate-until-done mechanism
- Tracks iteration count, enforces max limit
- Handles Ctrl+C gracefully (saves state)
- Delegates to Phase Manager and Skill Orchestrator

### 3. Phase Manager
- Defines workflow phases: PRD → TICKETS → RESEARCH → PLANNING → IMPLEMENTATION → REFACTORING
- Each phase has entry prompt and completion criteria
- Tracks current phase in session state
- Auto-transitions when criteria met

### 4. Skill Orchestrator
- Maps phases to appropriate skills
- PRD phase → PRD Interviewer
- RESEARCH phase → Researcher
- IMPLEMENTATION phase → Implementer
- REFACTORING phase → Refactorer
- Review can be invoked at any time
- Passes context between skill invocations

### 5. Skills
Each skill is a Python class with:
- `system_prompt` - Defines role and capabilities
- `execute(context)` - Run the skill with given context
- `get_tools()` - List of tools this skill can use

| Skill | Phase | Purpose |
|-------|-------|---------|
| PRD Interviewer | PRD | Ask questions, generate requirements doc |
| Researcher | RESEARCH | Investigate codebase, gather context |
| Reviewer | Any | Code review, bug detection |
| Implementer | IMPLEMENTATION | Write and modify code |
| Refactorer | REFACTORING | Improve code without behavior change |

### 6. Tools
- `file_ops.py` - read_file, write_file, list_dir, search_files
- `shell.py` - run_command with timeout and output capture
- All tools return structured JSON results

### 7. Ollama Client
- Async HTTP client using `httpx`
- `generate()` - Single prompt completion
- `chat()` - Multi-turn conversation
- Retry logic for connection errors
- Configurable model and endpoint

### 8. Session Persistence
- Sessions stored in `~/.loop-orchestration/sessions/<id>/`
- Files per session:
  - `state.json` - Current phase, iteration, metadata
  - `history.json` - Full conversation history
  - `prd.md` - Generated PRD (if PRD phase completed)
  - `outputs/` - Skill outputs

## Data Flow

1. User runs `./loop.sh "build a todo app"`
2. Bash script invokes Python entry point
3. Loop Engine creates new session
4. Phase Manager starts at PRD phase
5. Skill Orchestrator invokes PRD Interviewer
6. PRD Interviewer asks user questions via stdout/stdin
7. User answers are captured, PRD generated
8. Phase transitions to TICKETS, then RESEARCH
9. Researcher skill reads codebase, outputs findings
10. Implementation phase: Implementer writes code
11. Refactoring phase: Refactorer cleans up
12. Completion detected → session marked complete

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.10+ | Type hints, async support, LLM ecosystem |
| HTTP Client | httpx | Async support, modern API |
| Config | YAML | Human-readable |
| State | JSON | Machine-readable, easy serialization |
| CLI | Bash + argparse | Simple scripts, cross-platform Python |
| LLM | Ollama | Local, free, easy setup |

## Configuration

`~/.loop-orchestration/config.yaml`:
```yaml
model: llama3.2
ollama_url: http://localhost:11434
max_iterations: 50
session_dir: ~/.loop-orchestration/sessions
```

## Security Considerations

### Attack Surfaces
1. **Shell command execution** - Skills can run arbitrary commands
2. **File system access** - Skills can read/write files
3. **LLM prompt injection** - User input goes to LLM

### Mitigations
1. **Command blocklist** - Reject dangerous commands (rm -rf /, etc.)
2. **Working directory restriction** - Operations limited to project dir
3. **No secrets in config** - Ollama is local, no API keys needed
4. **Input sanitization** - Escape special characters in file paths
5. **Timeout on commands** - Prevent hanging processes
6. **Max iteration limit** - Prevent infinite loops

### Trust Model
- This tool runs locally on trusted hardware (DGX Spark)
- Users are team members with legitimate access
- LLM is local (Ollama), no data leaves the machine
- No authentication needed (single-user/team assumption)

### Data Sensitivity
- Session data may contain code snippets (sensitive IP)
- Sessions stored only on local disk
- No telemetry or external reporting
