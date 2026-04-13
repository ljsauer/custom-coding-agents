"""Code refactoring tool."""

from anthropic import AsyncAnthropic

from pyagent.config import Settings
from pyagent.context import CodebaseContext
from pyagent.logging import get_logger
from pyagent.prompts import build_refactor_prompt
from pyagent.rag import KnowledgeBase
from pyagent.tools.base import ToolResult

logger = get_logger(__name__)


class RefactorTool:
    """Suggests and applies refactoring patterns from the playbook."""

    def __init__(self, client: AsyncAnthropic, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    @property
    def name(self) -> str:
        return "refactor"

    @property
    def description(self) -> str:
        return "Refactor Python code using named patterns from the playbook."

    def relevant_sources(self) -> list[str]:
        return [
            "python_standards",
            "refactoring_playbook",
            "anti_patterns",
            "architecture_patterns",
            "tech_stack",
        ]

    async def execute(
        self,
        code: str,
        *,
        filename: str = "",
        user_request: str = "",
        codebase: CodebaseContext | None = None,
        knowledge_base: KnowledgeBase | None = None,
    ) -> ToolResult:
        """Run a refactoring pass on the provided source.

        Args:
            code: Python source code to refactor.
            filename: Optional filename for context.
            user_request: Specific refactoring focus or instructions.
            codebase: Optional broader codebase context.
            knowledge_base: Knowledge base for retrieving patterns.

        Returns:
            A ``ToolResult`` containing the refactored code and explanation.
        """
        rag_context = ""
        if knowledge_base:
            query = f"refactor {user_request or ''} {filename or ''}".strip()
            rag_context = knowledge_base.retrieve_formatted(
                query,
                sources=self.relevant_sources(),
                max_tokens=4000,
            )

        system_prompt, user_message = build_refactor_prompt(
            code,
            filename=filename,
            context=rag_context,
            user_request=user_request,
        )

        logger.info(
            "Running refactor on %s (%d chars)", filename or "<stdin>", len(code)
        )

        response = await self._client.messages.create(
            model=self._settings.model,
            max_tokens=self._settings.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        content = response.content[0].text
        return ToolResult(
            content=content,
            metadata={
                "model": self._settings.model,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )
