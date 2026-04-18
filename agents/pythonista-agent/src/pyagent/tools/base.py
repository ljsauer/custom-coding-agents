"""Base interface for agent tools."""

from dataclasses import dataclass
from typing import Protocol

from pyagent.context import CodebaseContext
from pyagent.rag import KnowledgeBase


@dataclass(frozen=True)
class ToolResult:
    """The output of a tool execution.

    Attributes:
        content: The main output text (review findings, refactored code, etc.).
        metadata: Optional structured metadata about the operation.
    """

    content: str
    metadata: dict[str, object] | None = None


class Tool(Protocol):
    """Protocol that all agent tools must satisfy."""

    @property
    def name(self) -> str:
        """Short identifier for the tool."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description of what the tool does."""
        ...

    def relevant_sources(self) -> list[str]:
        """Return doc source names most relevant to this tool.

        Used to scope RAG retrieval to the most useful documents.
        """
        ...

    async def execute(
        self,
        code: str,
        *,
        filename: str = "",
        user_request: str = "",
        codebase: CodebaseContext | None = None,
        knowledge_base: KnowledgeBase | None = None,
    ) -> ToolResult:
        """Execute the tool on the given code.

        Args:
            code: Source code to operate on.
            filename: Optional filename for context.
            user_request: Additional user instructions.
            codebase: Optional broader codebase context.
            knowledge_base: Optional knowledge base for RAG retrieval.

        Returns:
            A ``ToolResult`` with the tool's output.
        """
        ...
