"""Core loop engine for autonomous task execution."""

import signal
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .completion import CompletionDetector, CompletionResult, CompletionStatus
from .config import Config
from .display import Display
from .ollama_client import OllamaClient, Message
from .phases import PhaseManager, PhaseName, PhaseTransition
from .session import Session, SessionMessage, save as save_session


class LoopStatus(Enum):
    """Status of the loop engine."""
    RUNNING = "running"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    MAX_ITERATIONS = "max_iterations"
    ERROR = "error"
    NEEDS_INPUT = "needs_input"


@dataclass
class LoopResult:
    """Result of loop execution.

    Attributes:
        status: Final status of the loop
        iterations: Number of iterations completed
        reason: Reason for stopping
        output: Final output from the loop
        error: Error message if applicable
    """
    status: LoopStatus
    iterations: int
    reason: str
    output: str = ""
    error: str = ""


@dataclass
class LoopContext:
    """Context passed through loop iterations.

    Attributes:
        task_description: The original task
        project_root: Root directory of the project
        current_input: Current input for the LLM
        iteration: Current iteration number
        metadata: Additional context data
    """
    task_description: str
    project_root: str
    current_input: str = ""
    iteration: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class LoopEngine:
    """Core loop engine for autonomous task execution.

    Executes tasks in a loop, sending prompts to the LLM and
    checking for completion conditions.
    """

    def __init__(
        self,
        client: OllamaClient,
        config: Config,
        display: Display,
        session: Session,
        phase_manager: PhaseManager | None = None,
    ) -> None:
        """Initialize the loop engine.

        Args:
            client: Ollama client for LLM communication
            config: Configuration settings
            display: Display for progress output
            session: Session for persistence
            phase_manager: Optional phase manager for phase transitions
        """
        self.client = client
        self.config = config
        self.display = display
        self.session = session
        self.phase_manager = phase_manager or PhaseManager()
        self.completion_detector = CompletionDetector()

        self._interrupted = False
        self._original_handler: Any = None

    def _setup_signal_handler(self) -> None:
        """Set up signal handler for graceful interruption."""
        def handler(signum: int, frame: Any) -> None:
            self._interrupted = True
            self.display.show_status(
                "Interrupt received. Saving state and stopping...",
                is_error=False,
            )

        # Only set up handler on Unix-like systems
        if hasattr(signal, 'SIGINT'):
            self._original_handler = signal.signal(signal.SIGINT, handler)

    def _restore_signal_handler(self) -> None:
        """Restore original signal handler."""
        if self._original_handler is not None and hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, self._original_handler)
            self._original_handler = None

    def _build_messages(
        self,
        context: LoopContext,
        system_prompt: str = "",
    ) -> list[Message]:
        """Build message history for the LLM.

        Args:
            context: Current loop context
            system_prompt: System prompt to prepend

        Returns:
            List of messages for the LLM
        """
        messages: list[Message] = []

        # Add system prompt first
        if system_prompt:
            messages.append(Message(role="system", content=system_prompt))

        # Add conversation history from session
        for msg in self.session.conversation_history:
            messages.append(Message(role=msg.role, content=msg.content))

        # Add current input if present
        if context.current_input:
            messages.append(Message(role="user", content=context.current_input))

        return messages

    def _process_response(
        self,
        response: str,
        context: LoopContext,
    ) -> CompletionResult:
        """Process LLM response and check for completion.

        Args:
            response: The LLM response
            context: Current loop context

        Returns:
            Completion detection result
        """
        # Log the interaction
        self.display.log_interaction(
            role="assistant",
            content=response,
            metadata={
                "iteration": context.iteration,
                "phase": self.phase_manager.current_phase_name.value,
            },
        )

        # Add to session history
        self.session.conversation_history.append(
            SessionMessage(role="assistant", content=response)
        )

        # Check for completion
        return self.completion_detector.detect(response)

    def _handle_phase_transition(
        self,
        completion_result: CompletionResult,
    ) -> bool:
        """Handle phase transition if needed.

        Args:
            completion_result: Result from completion detection

        Returns:
            True if transitioned to a new phase
        """
        if completion_result.status == CompletionStatus.PHASE_COMPLETE:
            if self.phase_manager.can_advance():
                new_phase = self.phase_manager.advance(completion_result.reason)
                if new_phase:
                    self.display.show_phase(
                        new_phase.name.value,
                        new_phase.description,
                    )
                    self.session.current_phase = new_phase.name.value
                    return True
        return False

    def run(
        self,
        task_description: str,
        project_root: str,
        max_iterations: int | None = None,
        on_iteration: Callable[[int, str], None] | None = None,
    ) -> LoopResult:
        """Run the loop engine on a task.

        Args:
            task_description: Description of the task to execute
            project_root: Root directory of the project
            max_iterations: Maximum iterations (uses config default if None)
            on_iteration: Optional callback after each iteration

        Returns:
            LoopResult with final status
        """
        max_iter = max_iterations or self.config.max_iterations
        self._interrupted = False

        # Set up context
        context = LoopContext(
            task_description=task_description,
            project_root=project_root,
            current_input=task_description,
        )

        # Update session
        self.session.task_description = task_description
        self.session.current_phase = self.phase_manager.current_phase_name.value

        # Show initial phase
        self.display.show_phase(
            self.phase_manager.current_phase_name.value,
            self.phase_manager.current_phase.description,
        )

        # Set up interrupt handler
        self._setup_signal_handler()

        try:
            # Get system prompt from current phase
            system_prompt = self.phase_manager.get_entry_prompt()

            for iteration in range(1, max_iter + 1):
                if self._interrupted:
                    self._save_state()
                    return LoopResult(
                        status=LoopStatus.INTERRUPTED,
                        iterations=iteration - 1,
                        reason="User interrupted",
                    )

                context.iteration = iteration
                self.display.show_iteration(iteration, max_iter)

                # Log the input
                if context.current_input:
                    self.display.log_interaction(
                        role="user",
                        content=context.current_input,
                        metadata={"iteration": iteration},
                    )
                    self.session.conversation_history.append(
                        SessionMessage(role="user", content=context.current_input)
                    )

                # Build messages and call LLM
                messages = self._build_messages(context, system_prompt=system_prompt)

                try:
                    response = self.client.chat(
                        messages=messages,
                        model=self.config.model,
                    )
                    output = response.content
                except Exception as e:
                    self._save_state()
                    return LoopResult(
                        status=LoopStatus.ERROR,
                        iterations=iteration,
                        reason="LLM error",
                        error=str(e),
                    )

                # Display action (truncated)
                action_preview = output[:100] if output else "(no output)"
                self.display.show_action(action_preview)

                # Process response
                completion_result = self._process_response(output, context)

                # Call iteration callback
                if on_iteration:
                    on_iteration(iteration, output)

                # Check completion status
                if completion_result.status == CompletionStatus.TASK_COMPLETE:
                    self._save_state()
                    return LoopResult(
                        status=LoopStatus.COMPLETED,
                        iterations=iteration,
                        reason=completion_result.reason,
                        output=output,
                    )

                if completion_result.status == CompletionStatus.NEEDS_USER_INPUT:
                    self._save_state()
                    return LoopResult(
                        status=LoopStatus.NEEDS_INPUT,
                        iterations=iteration,
                        reason=completion_result.reason,
                        output=output,
                    )

                # Handle phase transition
                if self._handle_phase_transition(completion_result):
                    # Reset input for new phase
                    context.current_input = self.phase_manager.get_entry_prompt()
                    system_prompt = context.current_input
                else:
                    # Continue with LLM output as context
                    context.current_input = ""

                # Save state periodically
                if iteration % 5 == 0:
                    self._save_state()

            # Max iterations reached
            self._save_state()
            return LoopResult(
                status=LoopStatus.MAX_ITERATIONS,
                iterations=max_iter,
                reason=f"Reached maximum iterations ({max_iter})",
            )

        finally:
            self._restore_signal_handler()

    def _save_state(self) -> None:
        """Save current state to session."""
        try:
            save_session(self.session, self.config.session_dir)
            self.display.show_status("State saved")
        except Exception as e:
            self.display.show_status(f"Failed to save state: {e}", is_error=True)

    def resume(
        self,
        project_root: str,
        user_input: str | None = None,
        max_iterations: int | None = None,
        on_iteration: Callable[[int, str], None] | None = None,
    ) -> LoopResult:
        """Resume a previously interrupted loop.

        Args:
            project_root: Root directory of the project
            user_input: Optional new input from user
            max_iterations: Maximum iterations
            on_iteration: Optional callback after each iteration

        Returns:
            LoopResult with final status
        """
        # Restore phase manager state
        current_phase_str = self.session.current_phase
        try:
            current_phase = PhaseName(current_phase_str)
            self.phase_manager.set_phase(current_phase, "Resumed from session")
        except ValueError:
            pass  # Keep default phase

        # Build initial input
        if user_input:
            initial_input = user_input
        elif self.session.conversation_history:
            # Continue from where we left off
            initial_input = ""
        else:
            initial_input = self.session.task_description

        # Create context
        max_iter = max_iterations or self.config.max_iterations
        self._interrupted = False

        context = LoopContext(
            task_description=self.session.task_description,
            project_root=project_root,
            current_input=initial_input,
        )

        # Run the loop (reusing run logic)
        # Note: This is a simplified resume - for full resume,
        # we would need to track iteration count in session
        return self.run(
            task_description=self.session.task_description,
            project_root=project_root,
            max_iterations=max_iter,
            on_iteration=on_iteration,
        )


def create_loop_engine(
    client: OllamaClient,
    config: Config,
    display: Display,
    session: Session,
    initial_phase: PhaseName = PhaseName.PRD,
) -> LoopEngine:
    """Create a configured loop engine.

    Args:
        client: Ollama client
        config: Configuration
        display: Display for output
        session: Session for persistence
        initial_phase: Starting phase

    Returns:
        Configured LoopEngine instance
    """
    phase_manager = PhaseManager(initial_phase=initial_phase)
    return LoopEngine(
        client=client,
        config=config,
        display=display,
        session=session,
        phase_manager=phase_manager,
    )
