"""Core agent orchestration.

This module contains the ``Agent`` class, which is the central coordinator.
It wires together the LLM client, tools, RAG knowledge base, memory, and
codebase context into a coherent reasoning loop.
"""


from anthropic import AsyncAnthropic

from pyagent.config import Settings
from pyagent.context import CodebaseContext, build_context
from pyagent.logging import get_logger
from pyagent.memory import ConversationMemory
from pyagent.prompts import build_chat_prompt
from pyagent.rag import KnowledgeBase, load_knowledge_base
from pyagent.tools.explainer import ExplainTool
from pyagent.tools.refactor import RefactorTool
from pyagent.tools.reviewer import ReviewTool

logger = get_logger(__name__)


class Agent:
    """The PyAgent orchestrator.

    Manages the lifecycle of a session: loading configuration, initializing
    the LLM client and knowledge base, running tools, and maintaining
    conversation state.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._kb = load_knowledge_base(settings.docs_path)
        self._memory = ConversationMemory()
        self._codebase: CodebaseContext | None = None

        # Initialize tools with shared client and settings.
        self._reviewer = ReviewTool(self._client, settings)
        self._refactorer = RefactorTool(self._client, settings)
        self._explainer = ExplainTool(self._client, settings)

        logger.info(
            "Agent initialized (model=%s, docs=%s)",
            settings.model,
            settings.docs_path,
        )

    @property
    def knowledge_base(self) -> KnowledgeBase:
        """The loaded knowledge base."""
        return self._kb

    @property
    def codebase(self) -> CodebaseContext | None:
        """The currently loaded codebase context, if any."""
        return self._codebase

    @property
    def memory(self) -> ConversationMemory:
        """The conversation memory for this session."""
        return self._memory

    def load_codebase(self, path_str: str) -> CodebaseContext:
        """Load and index a codebase from the given path.

        Args:
            path_str: Path to a Python file or directory.

        Returns:
            The constructed ``CodebaseContext``.

        Raises:
            FileNotFoundError: If the path does not exist.
        """
        from pathlib import Path

        path = Path(path_str).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        self._codebase = build_context(path)
        logger.info("Loaded codebase: %s (%d files)", path, self._codebase.file_count)
        return self._codebase

    async def review(
        self,
        code: str,
        *,
        filename: str = "",
        instructions: str = "",
    ) -> str:
        """Run a code review.

        Args:
            code: Python source code to review.
            filename: Optional filename for context.
            instructions: Additional review instructions.

        Returns:
            The formatted review output.
        """
        result = await self._reviewer.execute(
            code,
            filename=filename,
            user_request=instructions,
            codebase=self._codebase,
            knowledge_base=self._kb,
        )
        logger.info(
            "Review complete (%s tokens in, %s tokens out)",
            result.metadata.get("input_tokens") if result.metadata else "?",
            result.metadata.get("output_tokens") if result.metadata else "?",
        )
        return result.content

    async def refactor(
        self,
        code: str,
        *,
        filename: str = "",
        instructions: str = "",
    ) -> str:
        """Run a refactoring pass and return the raw response.

        For file-writing workflows, use ``refactor_with_plan`` instead.

        Args:
            code: Python source code to refactor.
            filename: Optional filename for context.
            instructions: Specific refactoring focus.

        Returns:
            The raw refactoring response text.
        """
        result = await self._refactorer.execute(
            code,
            filename=filename,
            user_request=instructions,
            codebase=self._codebase,
            knowledge_base=self._kb,
        )
        logger.info(
            "Refactor complete (%s tokens in, %s tokens out)",
            result.metadata.get("input_tokens") if result.metadata else "?",
            result.metadata.get("output_tokens") if result.metadata else "?",
        )
        return result.content

    async def refactor_with_plan(
        self,
        file_map: dict[str, "Path"],
        originals: dict[str, str],
        code: str,
        *,
        filename: str = "",
        instructions: str = "",
    ) -> "RefactorPlan":
        """Run a refactoring pass and return a structured plan.

        The plan contains per-file diffs that can be reviewed and applied.

        Args:
            file_map: Mapping of filename strings to absolute file paths.
            originals: Mapping of filename strings to original source content.
            code: The assembled code string sent to the LLM.
            filename: Label for the code being refactored.
            instructions: Specific refactoring focus.

        Returns:
            A ``RefactorPlan`` with parsed file changes.
        """
        from pyagent.tools.refactor import parse_refactor_response

        raw_response = await self.refactor(
            code,
            filename=filename,
            instructions=instructions,
        )
        return parse_refactor_response(raw_response, file_map, originals)

    async def explain(
        self,
        code: str,
        *,
        filename: str = "",
        question: str = "",
    ) -> str:
        """Explain code structure and design.

        Args:
            code: Python source code to explain.
            filename: Optional filename for context.
            question: Specific question about the code.

        Returns:
            The explanation text.
        """
        result = await self._explainer.execute(
            code,
            filename=filename,
            user_request=question,
            codebase=self._codebase,
            knowledge_base=self._kb,
        )
        logger.info(
            "Explain complete (%s tokens in, %s tokens out)",
            result.metadata.get("input_tokens") if result.metadata else "?",
            result.metadata.get("output_tokens") if result.metadata else "?",
        )
        return result.content

    async def chat(self, user_message: str) -> str:
        """Send a free-form message in an ongoing conversation.

        The agent maintains conversation history and retrieves relevant
        documentation context based on the message content.

        Args:
            user_message: The user's chat message.

        Returns:
            The agent's response.
        """
        self._memory.add_user_message(user_message)

        # Retrieve relevant docs based on the user's message.
        rag_context = self._kb.retrieve_formatted(user_message, max_tokens=2000)
        codebase_summary = self._codebase.summary() if self._codebase else ""

        system_prompt = build_chat_prompt(
            context=rag_context,
            codebase_summary=codebase_summary,
        )
        self._memory.system_prompt = system_prompt

        response = await self._client.messages.create(
            model=self._settings.model,
            max_tokens=self._settings.max_tokens,
            system=system_prompt,
            messages=self._memory.to_api_messages(),
        )

        assistant_message = response.content[0].text
        self._memory.add_assistant_message(assistant_message)

        logger.info(
            "Chat turn %d (%d tokens in, %d tokens out)",
            self._memory.turn_count,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        return assistant_message


def create_agent(settings: Settings | None = None) -> Agent:
    """Factory function to create a configured Agent.

    Args:
        settings: Optional settings override. If ``None``, loads from env.

    Returns:
        A fully initialized ``Agent`` instance.
    """
    if settings is None:
        settings = Settings()
    return Agent(settings)
