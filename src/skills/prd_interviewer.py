"""PRD Interviewer skill for gathering product requirements."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import BaseSkill, SkillContext, SkillOutput


MAX_ANSWER_LENGTH = 2000


@dataclass
class InterviewQuestion:
    """A question in the PRD interview.

    Attributes:
        id: Question identifier
        question: The question text
        options: Optional A/B/C/D options
        follow_up: Follow-up prompt for vague answers
        required: Whether an answer is required
    """
    id: str
    question: str
    options: list[str] = field(default_factory=list)
    follow_up: str = ""
    required: bool = True


@dataclass
class InterviewState:
    """State of the PRD interview.

    Attributes:
        current_question: Index of current question
        answers: Collected answers
        project_name: Name of the project
    """
    current_question: int = 0
    answers: dict[str, str] = field(default_factory=dict)
    project_name: str = ""


# Interview questions for PRD discovery
INTERVIEW_QUESTIONS: list[InterviewQuestion] = [
    InterviewQuestion(
        id="project_name",
        question="What do you want to name this project? (one or two words)",
        follow_up="Please provide a short project name (1-2 words).",
    ),
    InterviewQuestion(
        id="description",
        question=(
            "Tell me about what you want to build. What is it and what "
            "problem does it solve?"
        ),
        follow_up=(
            "Could you be more specific? What exactly will this do? "
            "What problem will it solve for users?"
        ),
    ),
    InterviewQuestion(
        id="problem",
        question=(
            "What specific problem does this solve? "
            "What happens if this doesn't exist?"
        ),
        follow_up=(
            "Can you describe the pain point more specifically? "
            "What do users currently do without this solution?"
        ),
    ),
    InterviewQuestion(
        id="users",
        question=(
            "Who exactly will use this? Be specific - is it you, customers, "
            "employees, everyone?"
        ),
        options=[
            "A. Just me / personal use",
            "B. My team / internal use",
            "C. Customers / external users",
            "D. Everyone / public",
        ],
        follow_up="Please specify who the primary users will be.",
    ),
    InterviewQuestion(
        id="core_features",
        question="If this could only do 3 things, what would they be?",
        follow_up=(
            "Please list exactly 3 core features. What are the most "
            "important capabilities?"
        ),
    ),
    InterviewQuestion(
        id="success",
        question=(
            "How will you know this is working? What does success look like?"
        ),
        options=[
            "A. I can complete a specific workflow",
            "B. Users adopt it and give positive feedback",
            "C. Metrics improve (speed, cost, errors)",
            "D. Something else (please describe)",
        ],
        follow_up="What specific outcome would tell you this succeeded?",
    ),
    InterviewQuestion(
        id="scope",
        question="What should this explicitly NOT do? What's out of scope for now?",
        follow_up=(
            "It helps to know boundaries. What features or integrations "
            "are you intentionally leaving out?"
        ),
    ),
    InterviewQuestion(
        id="platform",
        question="What's the primary platform?",
        options=[
            "A. Web app",
            "B. Mobile app",
            "C. Desktop app",
            "D. API/Backend only",
            "E. CLI tool",
        ],
    ),
    InterviewQuestion(
        id="tech_preferences",
        question="Do you have any technology preferences or constraints?",
        options=[
            "A. No preferences - use what's best",
            "B. Python",
            "C. JavaScript/TypeScript",
            "D. Other (please specify)",
        ],
        required=False,
    ),
]


class PRDInterviewerSkill(BaseSkill):
    """Skill for conducting PRD discovery interviews.

    Asks questions to understand what the user wants to build,
    then generates a structured PRD document.
    """

    def __init__(self) -> None:
        """Initialize the PRD interviewer skill."""
        super().__init__()
        self._state = InterviewState()

    @property
    def name(self) -> str:
        """Get skill name."""
        return "prd_interviewer"

    @property
    def description(self) -> str:
        """Get skill description."""
        return "Conducts discovery interviews to create Product Requirements Documents"

    @property
    def system_prompt(self) -> str:
        """Get system prompt for the LLM."""
        return """You are a Product Requirements Document (PRD) interviewer.

Your job is to understand what the user wants to build through a discovery interview.

Guidelines:
1. Ask ONE question at a time
2. Offer A/B/C/D options when helpful for quick answers
3. Challenge vague answers - ask for specifics
4. Be conversational but focused on gathering requirements
5. When you have enough information, generate a structured PRD

Question flow:
1. Project name
2. What they want to build (high-level description)
3. Problem being solved
4. Target users
5. Core features (top 3)
6. Success criteria
7. Out of scope items
8. Platform
9. Tech preferences (optional)

After gathering all answers, generate a structured PRD with:
- Introduction (what and why)
- Goals (bulleted list)
- User Stories (numbered, in format "As a [user], I want [feature], so that [benefit]")
- Out of Scope
- Technical Notes (if applicable)

Mark [PHASE_COMPLETE] when the PRD is generated and saved."""

    def execute(self, context: SkillContext) -> SkillOutput:
        """Execute the PRD interviewer skill.

        Args:
            context: Execution context

        Returns:
            SkillOutput with interview progress or PRD
        """
        # Validate context
        validation_error = self.validate_context(context)
        if validation_error:
            return self.create_error_output(validation_error)

        # Check for user input in conversation history
        user_input = self._get_last_user_input(context)

        # Handle "back" command
        if user_input and user_input.strip().lower() == "back":
            return self._go_back()

        # Process answer if we have one
        if user_input and self._state.current_question > 0:
            result = self._process_answer(user_input)
            if result:
                return result

        # Check if interview is complete
        if self._state.current_question >= len(INTERVIEW_QUESTIONS):
            return self._generate_prd(context)

        # Ask next question
        return self._ask_question()

    def _get_last_user_input(self, context: SkillContext) -> str | None:
        """Get the last user input from conversation history.

        Args:
            context: Execution context

        Returns:
            Last user input or None
        """
        for msg in reversed(context.conversation_history):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return None

    def _go_back(self) -> SkillOutput:
        """Go back to the previous question.

        Returns:
            SkillOutput with previous question
        """
        if self._state.current_question > 0:
            self._state.current_question -= 1
            # Remove the answer for the question we're going back to
            question = INTERVIEW_QUESTIONS[self._state.current_question]
            if question.id in self._state.answers:
                del self._state.answers[question.id]

        return self._ask_question()

    def _process_answer(self, answer: str) -> SkillOutput | None:
        """Process a user answer.

        Args:
            answer: User's answer

        Returns:
            SkillOutput if answer is invalid, None if valid
        """
        answer = answer.strip()

        # Get current question
        question_idx = self._state.current_question - 1
        if question_idx < 0 or question_idx >= len(INTERVIEW_QUESTIONS):
            return None

        question = INTERVIEW_QUESTIONS[question_idx]

        # Check for empty answer
        if not answer and question.required:
            return SkillOutput(
                success=True,
                content="Please provide an answer to continue.\n\n"
                + self._format_question(question),
            )

        # Handle option selection (A, B, C, D, E)
        if question.options and len(answer) == 1 and answer.upper() in "ABCDE":
            option_idx = ord(answer.upper()) - ord("A")
            if option_idx < len(question.options):
                answer = question.options[option_idx]

        # Truncate long answers
        if len(answer) > MAX_ANSWER_LENGTH:
            answer = answer[:MAX_ANSWER_LENGTH]
            self.log_action(
                "truncated_answer",
                {"question_id": question.id, "original_length": len(answer)},
            )

        # Check for vague answers (very short for descriptive questions)
        if len(answer) < 10 and question.id in ("description", "problem", "core_features"):
            return SkillOutput(
                success=True,
                content=question.follow_up + "\n\n" + self._format_question(question),
            )

        # Store answer
        self._state.answers[question.id] = answer

        # Special handling for project name
        if question.id == "project_name":
            self._state.project_name = answer.lower().replace(" ", "-")

        self.log_action("answer_recorded", {"question_id": question.id})

        # Move to next question
        self._state.current_question += 1

        return None

    def _ask_question(self) -> SkillOutput:
        """Ask the current question.

        Returns:
            SkillOutput with the question
        """
        if self._state.current_question >= len(INTERVIEW_QUESTIONS):
            return SkillOutput(
                success=True,
                content="All questions answered. Generating PRD...",
            )

        question = INTERVIEW_QUESTIONS[self._state.current_question]
        self._state.current_question += 1

        content = self._format_question(question)
        content += "\n\n(Type 'back' to revisit the previous question)"

        return SkillOutput(
            success=True,
            content=content,
            metadata={"question_id": question.id},
        )

    def _format_question(self, question: InterviewQuestion) -> str:
        """Format a question for display.

        Args:
            question: Question to format

        Returns:
            Formatted question string
        """
        parts = [question.question]

        if question.options:
            parts.append("")
            for option in question.options:
                parts.append(f"   {option}")

        return "\n".join(parts)

    def _generate_prd(self, context: SkillContext) -> SkillOutput:
        """Generate the PRD document.

        Args:
            context: Execution context

        Returns:
            SkillOutput with generated PRD
        """
        answers = self._state.answers

        # Build PRD content
        prd_content = self._build_prd_content(answers)

        # Save to file
        prd_path = Path(context.project_root) / "tasks" / "prd.md"
        try:
            prd_path.parent.mkdir(parents=True, exist_ok=True)
            prd_path.write_text(prd_content, encoding="utf-8")
        except OSError as e:
            return self.create_error_output(f"Failed to save PRD: {e}")

        self.log_action("prd_generated", {"path": str(prd_path)})

        return SkillOutput(
            success=True,
            content=f"PRD generated and saved to {prd_path}\n\n[PHASE_COMPLETE]",
            artifacts={"prd.md": prd_content},
            metadata={"prd_path": str(prd_path)},
        )

    def _build_prd_content(self, answers: dict[str, str]) -> str:
        """Build PRD content from answers.

        Args:
            answers: Collected interview answers

        Returns:
            PRD markdown content
        """
        project_name = answers.get("project_name", "Project")
        description = answers.get("description", "")
        problem = answers.get("problem", "")
        users = answers.get("users", "")
        core_features = answers.get("core_features", "")
        success = answers.get("success", "")
        scope = answers.get("scope", "")
        platform = answers.get("platform", "")
        tech = answers.get("tech_preferences", "")

        # Parse core features into list
        features = self._parse_features(core_features)

        content = f"""# PRD: {project_name.title()}

## Introduction

{description}

{problem}

## Goals

- Solve the problem of: {problem[:100]}...
- Target users: {users}
- Platform: {platform}
- Success criteria: {success}

## User Stories

"""
        # Generate user stories from features
        for i, feature in enumerate(features, 1):
            content += f"### US-{i:03d}: {feature}\n"
            content += f"**Description:** As a user, I want {feature.lower()}, "
            content += "so that I can accomplish my goals.\n\n"
            content += "**Acceptance Criteria:**\n"
            content += f"- [ ] {feature} is implemented\n"
            content += "- [ ] Typecheck passes\n\n"

        content += f"""## Out of Scope

{scope}

## Technical Notes

- Platform: {platform}
- Technology preferences: {tech if tech else 'No specific preferences'}
"""

        return content

    def _parse_features(self, features_str: str) -> list[str]:
        """Parse features string into list.

        Args:
            features_str: Features as string

        Returns:
            List of feature strings
        """
        features: list[str] = []

        # Try splitting by newlines, numbers, or commas
        lines = features_str.replace(",", "\n").split("\n")

        for line in lines:
            # Clean up the line
            line = line.strip()
            # Remove numbering (1., 1), etc.)
            if line and line[0].isdigit():
                line = line.lstrip("0123456789").lstrip(".)").strip()
            if line:
                features.append(line)

        # If we couldn't parse, use the whole thing
        if not features and features_str.strip():
            features = [features_str.strip()]

        return features[:10]  # Limit to 10 features

    def reset(self) -> None:
        """Reset the interview state."""
        self._state = InterviewState()
        self.clear_log()

    def get_state(self) -> dict[str, Any]:
        """Get current interview state.

        Returns:
            State dictionary
        """
        return {
            "current_question": self._state.current_question,
            "answers": dict(self._state.answers),
            "project_name": self._state.project_name,
        }

    def set_state(self, state: dict[str, Any]) -> None:
        """Restore interview state.

        Args:
            state: State dictionary
        """
        self._state.current_question = state.get("current_question", 0)
        self._state.answers = dict(state.get("answers", {}))
        self._state.project_name = state.get("project_name", "")
