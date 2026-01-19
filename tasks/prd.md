# PRD: Loop Orchestration

## Introduction

Loop Orchestration is a local LLM-powered autonomous development workflow tool. It replicates the core functionality of the Pickle Rick Gemini CLI extension but runs entirely on local infrastructure using Ollama. The system creates self-referential agent loops through hooks - executing tasks, intercepting exits, re-feeding prompts, and repeating until completion criteria are met.

This eliminates cloud API costs by leveraging existing compute resources (NVIDIA DGX Spark) while maintaining the structured development workflow: PRD drafting → ticket breakdown → research → planning → implementation → refactoring.

## Goals

- Run autonomous development loops entirely on local LLM via Ollama
- Implement structured phases for software development workflow
- Provide 5 specialized Skills (PRD interviewer, researcher, reviewer, implementer, refactorer)
- Zero dependency on Gemini CLI or cloud APIs
- Simple wrapper scripts for easy team adoption
- Session persistence for resuming interrupted workflows

## User Stories

### US-001: Set up Ollama client module
**Description:** As a developer, I need a Python module that communicates with Ollama's REST API so the system can send prompts and receive completions.

**Acceptance Criteria:**
- [ ] Create `src/ollama_client.py` with `OllamaClient` class
- [ ] Implement `generate(prompt, model, system_prompt)` method
- [ ] Implement `chat(messages, model)` method for multi-turn conversations
- [ ] Handle connection errors gracefully with retry logic (3 retries, exponential backoff)
- [ ] Support configurable base URL (default: http://localhost:11434)
- [ ] Clear error message if Ollama not running: "Cannot connect to Ollama at {url}. Is it running?"
- [ ] Clear error message if model not found: "Model '{model}' not found. Run: ollama pull {model}"
- [ ] Handle LLM timeout (configurable, default 5 minutes for long generations)
- [ ] Typecheck passes

### US-002: Create configuration system
**Description:** As a user, I need a configuration file so I can specify which model to use and customize behavior without editing code.

**Acceptance Criteria:**
- [ ] Create `src/config.py` that loads from `~/.loop-orchestration/config.yaml`
- [ ] Support settings: model name, ollama_url, max_iterations, session_dir
- [ ] Create default config on first run if missing
- [ ] Validate config on load and report clear errors for: invalid YAML, missing required fields, invalid values
- [ ] Reject negative or zero max_iterations with clear error
- [ ] Handle config directory not writable (suggest fix)
- [ ] Typecheck passes

### US-003: Startup health check
**Description:** As a user, I want the system to verify Ollama is ready before starting so I get immediate feedback instead of cryptic errors later.

**Acceptance Criteria:**
- [ ] Create `src/health.py` with `check_ollama_health()` function
- [ ] Check Ollama is reachable at startup (GET /api/tags)
- [ ] Check configured model is available
- [ ] If Ollama not running: "Ollama not running. Start with: ollama serve"
- [ ] If model missing: "Model '{model}' not found. Install with: ollama pull {model}"
- [ ] Health check completes in under 2 seconds (timeout)
- [ ] Skip health check with --skip-check flag for advanced users
- [ ] Typecheck passes

### US-004: Implement session persistence
**Description:** As a user, I want my work sessions saved so I can resume interrupted workflows.

**Acceptance Criteria:**
- [ ] Create `src/session.py` with `Session` class
- [ ] Sessions stored in `~/.loop-orchestration/sessions/[session-id]/`
- [ ] Save: current phase, task description, conversation history, skill outputs
- [ ] Implement `save()`, `load()`, `list_sessions()` methods
- [ ] Generate unique session IDs (timestamp + short hash)
- [ ] Handle corrupted session files: warn user, offer to start fresh or delete
- [ ] Handle disk full errors gracefully with clear message
- [ ] Atomic writes (write to temp file, then rename) to prevent corruption on crash
- [ ] Typecheck passes

### US-005: Add file operation tools
**Description:** As a skill, I need tools to read and write files so I can interact with the codebase.

**Acceptance Criteria:**
- [ ] Create `src/tools/file_ops.py` with functions: read_file, write_file, list_dir, search_files
- [ ] All tools return structured results (success/error, output, metadata)
- [ ] Block path traversal attacks: reject paths containing `..` that escape project root
- [ ] Handle file not found with clear error (not stack trace)
- [ ] Handle permission denied with clear error
- [ ] Skip binary files when reading (detect via null bytes in first 1KB)
- [ ] Typecheck passes

### US-006: Add shell command tool
**Description:** As a skill, I need a tool to run shell commands so I can execute builds, tests, and other operations.

**Acceptance Criteria:**
- [ ] Create `src/tools/shell.py` with function: run_command (with timeout, output capture)
- [ ] Return structured results (success/error, stdout, stderr, exit_code)
- [ ] Block dangerous shell commands: rm -rf /, mkfs, dd if=, shutdown, reboot
- [ ] Shell command timeout (default 60 seconds, configurable)
- [ ] Truncate shell output over 100KB with "[output truncated]" message
- [ ] Typecheck passes

### US-007: Implement completion detection
**Description:** As the loop engine, I need to detect when a task is complete so I know when to stop iterating.

**Acceptance Criteria:**
- [ ] Create `src/completion.py` with `CompletionDetector` class
- [ ] Detect explicit markers: `[TASK_COMPLETE]`, `[PHASE_COMPLETE]`, `[NEEDS_USER_INPUT]`
- [ ] Detect implicit completion: no more actions proposed, tests passing mentioned
- [ ] Return completion status and reason
- [ ] Typecheck passes

### US-008: Add progress display and logging
**Description:** As a user, I want to see what the system is doing so I can monitor progress.

**Acceptance Criteria:**
- [ ] Create `src/display.py` with progress output functions
- [ ] Show current phase, iteration count, last action
- [ ] Log all LLM interactions to session directory
- [ ] Support quiet mode (minimal output) via flag
- [ ] Typecheck passes

### US-009: Implement phase management
**Description:** As a user, I want the system to progress through structured phases so development follows a logical order.

**Acceptance Criteria:**
- [ ] Create `src/phases.py` defining phases: PRD, TICKETS, RESEARCH, PLANNING, IMPLEMENTATION, REFACTORING
- [ ] Each phase has: name, description, entry_prompt, completion_criteria
- [ ] Implement `PhaseManager` that tracks current phase and transitions
- [ ] Phases transition automatically when completion criteria met
- [ ] Allow manual phase override via command
- [ ] Typecheck passes

### US-010: Build the core loop engine
**Description:** As a developer, I need the main loop mechanism that executes tasks, checks completion, and re-feeds prompts until done.

**Acceptance Criteria:**
- [ ] Create `src/loop_engine.py` with `LoopEngine` class
- [ ] Accept task description and run until completion markers detected
- [ ] Implement configurable max iterations (default: 50) to prevent infinite loops
- [ ] Integrate with PhaseManager for phase transitions
- [ ] Integrate with CompletionDetector for stop conditions
- [ ] Log each iteration to session
- [ ] Support graceful interruption (Ctrl+C saves state)
- [ ] Typecheck passes

### US-011: Create base skill class
**Description:** As a developer, I need a base class that all skills inherit from so they share common functionality.

**Acceptance Criteria:**
- [ ] Create `src/skills/base.py` with `BaseSkill` abstract class
- [ ] Define abstract method `execute(context) -> SkillOutput`
- [ ] Define `system_prompt` property
- [ ] Define `get_tools()` method returning available tools
- [ ] Include common utilities: format_output, log_action
- [ ] Typecheck passes

### US-012: Create interactive PRD skill
**Description:** As a user, I want the system to ask me questions about what I want to build so it understands my requirements before coding.

**Acceptance Criteria:**
- [ ] Create `src/skills/prd_interviewer.py` with `PRDInterviewerSkill` class
- [ ] Asks discovery questions one at a time: problem, users, core features, success criteria, scope
- [ ] Offers multiple-choice options (A/B/C/D style) for quick answers
- [ ] Challenges vague answers and asks for specifics
- [ ] Generates structured PRD document from answers
- [ ] Saves PRD to session directory as `prd.md`
- [ ] Handle empty answers: re-prompt with "Please provide an answer to continue"
- [ ] Allow user to type "back" to revisit previous question
- [ ] Truncate very long answers (>2000 chars) with warning
- [ ] Typecheck passes

### US-013: Create Researcher skill
**Description:** As a user, I want a Researcher skill that investigates codebases and gathers context before implementation.

**Acceptance Criteria:**
- [ ] Create `src/skills/researcher.py` with `ResearcherSkill` class
- [ ] System prompt focuses on: reading files, understanding architecture, documenting findings
- [ ] Output structured findings as markdown
- [ ] Can search codebase, read files, analyze dependencies
- [ ] Typecheck passes

### US-014: Create Reviewer skill
**Description:** As a user, I want a Reviewer skill that checks code quality and suggests improvements.

**Acceptance Criteria:**
- [ ] Create `src/skills/reviewer.py` with `ReviewerSkill` class
- [ ] System prompt focuses on: code review, bug detection, best practices
- [ ] Output structured review with severity levels (critical, warning, suggestion)
- [ ] Check for common issues: error handling, edge cases, security
- [ ] Typecheck passes

### US-015: Create Implementer skill
**Description:** As a user, I want an Implementer skill that writes and modifies code based on plans.

**Acceptance Criteria:**
- [ ] Create `src/skills/implementer.py` with `ImplementerSkill` class
- [ ] System prompt focuses on: writing code, following specs, minimal changes
- [ ] Can create files, edit files, run commands
- [ ] Outputs clear diffs or file contents
- [ ] Typecheck passes

### US-016: Create Refactorer skill
**Description:** As a user, I want a Refactorer skill that improves code quality without changing behavior.

**Acceptance Criteria:**
- [ ] Create `src/skills/refactorer.py` with `RefactorerSkill` class
- [ ] System prompt focuses on: code cleanup, DRY, readability, performance
- [ ] Must preserve existing behavior (no functional changes)
- [ ] Output refactoring plan before making changes
- [ ] Typecheck passes

### US-017: Create skill orchestrator
**Description:** As a developer, I need a system that selects and invokes the appropriate skill based on the current phase.

**Acceptance Criteria:**
- [ ] Create `src/skill_orchestrator.py` with `SkillOrchestrator` class
- [ ] Map phases to default skills (PRD→PRDInterviewer, RESEARCH→Researcher, IMPLEMENTATION→Implementer, etc.)
- [ ] Allow explicit skill selection override
- [ ] Pass context between skills (previous outputs available to next skill)
- [ ] Typecheck passes

### US-018: Build main CLI wrapper script
**Description:** As a user, I want a simple command to start a task so I don't need to understand the internals.

**Acceptance Criteria:**
- [ ] Create `loop.sh` wrapper script
- [ ] Usage: `./loop.sh "task description"` to start new session
- [ ] Usage: `./loop.sh --resume [session-id]` to continue session
- [ ] Usage: `./loop.sh --list` to show recent sessions
- [ ] Display clear progress output during execution
- [ ] Create `src/main.py` as Python entry point
- [ ] Typecheck passes

### US-019: Create session management script
**Description:** As a user, I want helper scripts to manage sessions (list, resume, delete).

**Acceptance Criteria:**
- [ ] Create `loop-sessions.sh` wrapper script
- [ ] `./loop-sessions.sh list` - show all sessions with status
- [ ] `./loop-sessions.sh show [id]` - display session details
- [ ] `./loop-sessions.sh resume [id]` - continue a session
- [ ] `./loop-sessions.sh delete [id]` - remove a session
- [ ] Typecheck passes

## Functional Requirements

- FR-1: All LLM calls go through Ollama REST API at configurable endpoint
- FR-2: Sessions persist to disk and can be resumed after interruption
- FR-3: Loop engine iterates until completion markers or max iterations reached
- FR-4: Each skill has a specialized system prompt defining its role and capabilities
- FR-5: Skills can read files, write files, and execute shell commands
- FR-6: Phase transitions happen automatically based on completion criteria
- FR-7: All Python code passes type checking (mypy or pyright)
- FR-8: Wrapper scripts provide simple CLI interface without Python knowledge required

## Non-Goals

- No web UI or graphical interface
- No support for cloud LLM APIs (Gemini, OpenAI, Anthropic)
- No "Rick" persona or character behavior
- No built-in code execution sandbox (trust local environment)
- No multi-user support or authentication
- No automatic model downloading (user must have Ollama model ready)

## Technical Considerations

- Python 3.10+ for modern type hints
- Use `httpx` for async HTTP calls to Ollama
- YAML for configuration (human-readable)
- JSON for session state (machine-readable)
- Bash wrapper scripts call Python entry points
- Directory structure:
  ```
  loop-orchestration/
  ├── loop.sh              # Main entry point
  ├── loop-sessions.sh     # Session management
  ├── src/
  │   ├── __init__.py
  │   ├── main.py
  │   ├── ollama_client.py
  │   ├── config.py
  │   ├── health.py
  │   ├── session.py
  │   ├── loop_engine.py
  │   ├── phases.py
  │   ├── completion.py
  │   ├── display.py
  │   ├── skill_orchestrator.py
  │   ├── skills/
  │   │   ├── __init__.py
  │   │   ├── base.py
  │   │   ├── prd_interviewer.py
  │   │   ├── researcher.py
  │   │   ├── reviewer.py
  │   │   ├── implementer.py
  │   │   └── refactorer.py
  │   └── tools/
  │       ├── __init__.py
  │       ├── file_ops.py
  │       └── shell.py
  └── tests/
  ```

## Success Metrics

- Team can start a task with single command: `./loop.sh "build feature X"`
- System runs autonomously through all phases without manual intervention
- Sessions can be resumed after interruption with no lost progress
- Zero calls to external cloud APIs during operation
- All 5 skills produce useful, actionable output

## Open Questions

- What Ollama model should be the default? (llama3, codellama, deepseek-coder?)
- Should we add a "dry run" mode that shows what would happen without executing?
- Do we need rate limiting for Ollama calls or is local unlimited fine?
