"""Code refactoring tool."""

import re
from pathlib import Path

from anthropic import AsyncAnthropic

from pyagent.config import Settings
from pyagent.context import CodebaseContext
from pyagent.logging import get_logger
from pyagent.prompts import build_refactor_prompt
from pyagent.rag import KnowledgeBase
from pyagent.tools.base import ToolResult
from pyagent.writer import RefactorPlan

logger = get_logger(__name__)

# Pattern to extract FILE sections from the LLM response.
_FILE_SECTION_RE = re.compile(
    r"### FILE:\s*(?P<filename>.+?)\s*\n"
    r"(?P<explanation>.*?)"
    r"```python\n(?P<code>.*?)```",
    re.DOTALL,
)


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
            A ``ToolResult`` containing the raw LLM response.
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

    async def plan(
            self,
            structural_summary: str,
            *,
            user_request: str = "",
            knowledge_base: KnowledgeBase | None = None,
    ) -> str:
        """Generate an overall refactoring plan from a codebase structural summary.

        This is the first phase of codebase-wide refactoring.  The LLM analyses
        the structure of the whole project and returns a strategy that subsequent
        batch-refactoring passes will follow.

        Args:
            structural_summary: Output of ``CodebaseContext.summary()``.
            user_request: Optional focus for the refactoring plan.
            knowledge_base: Knowledge base for retrieving relevant patterns.

        Returns:
            A text string describing the overall refactoring strategy.
        """
        from pyagent.prompts import build_codebase_plan_prompt

        rag_context = ""
        if knowledge_base:
            query = f"refactoring plan codebase {user_request or ''}".strip()
            rag_context = knowledge_base.retrieve_formatted(
                query,
                sources=self.relevant_sources(),
                max_tokens=4000,
            )

        system_prompt, user_message = build_codebase_plan_prompt(
            structural_summary,
            context=rag_context,
            user_request=user_request,
        )

        logger.info(
            "Generating codebase refactoring plan (%d chars summary)",
            len(structural_summary),
        )

        response = await self._client.messages.create(
            model=self._settings.model,
            max_tokens=self._settings.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        return response.content[0].text

    async def execute_batch(
            self,
            batch_code: str,
            *,
            batch_label: str = "",
            overall_plan: str = "",
            user_request: str = "",
            knowledge_base: KnowledgeBase | None = None,
    ) -> ToolResult:
        """Refactor a batch of files as part of codebase-wide refactoring.

        Args:
            batch_code: Pre-formatted string with ``### FILE:`` sections.
            batch_label: Human-readable label (e.g. ``"1/3"``).
            overall_plan: The overall refactoring plan from the planning phase.
            user_request: Specific refactoring instructions.
            knowledge_base: Knowledge base for retrieving relevant patterns.

        Returns:
            A ``ToolResult`` containing the raw LLM response.
        """
        from pyagent.prompts import build_batch_refactor_prompt

        rag_context = ""
        if knowledge_base:
            query = f"refactor {user_request or ''} {overall_plan[:200] or ''}".strip()
            rag_context = knowledge_base.retrieve_formatted(
                query,
                sources=self.relevant_sources(),
                max_tokens=3000,
            )

        system_prompt, user_message = build_batch_refactor_prompt(
            batch_code,
            batch_label=batch_label,
            overall_plan=overall_plan,
            context=rag_context,
            user_request=user_request,
        )

        logger.info(
            "Refactoring batch %s (%d chars)",
            batch_label or "?",
            len(batch_code),
        )

        response = await self._client.messages.create(
            model=self._settings.model,
            max_tokens=self._settings.batch_max_tokens,
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


def parse_refactor_response(
    response: str,
    file_map: dict[str, Path],
    originals: dict[str, str],
) -> RefactorPlan:
    """Parse the LLM's structured refactor response into a ``RefactorPlan``.

    Extracts ``### FILE:`` sections from the response, matches them to real
    file paths, and builds a plan with diffs.

    Args:
        response: The raw LLM response text.
        file_map: Mapping of filename strings (as the LLM sees them) to
            absolute ``Path`` objects.
        originals: Mapping of filename strings to their original source code.

    Returns:
        A ``RefactorPlan`` with parsed file changes.
    """
    plan = RefactorPlan()

    # Extract the summary (everything before the first ### FILE: section).
    first_file = _FILE_SECTION_RE.search(response)
    if first_file:
        plan.summary = response[: first_file.start()].strip()
    else:
        # No structured sections found — treat the whole response as summary.
        plan.summary = response
        logger.warning("No FILE sections found in refactor response")
        return plan

    for match in _FILE_SECTION_RE.finditer(response):
        raw_filename = match.group("filename").strip()
        explanation = match.group("explanation").strip()
        refactored_code = match.group("code")

        # Try to resolve the filename to a real path.
        resolved_path = _resolve_filename(raw_filename, file_map)
        if resolved_path is None:
            logger.warning(
                "Could not resolve filename '%s' from LLM response — skipping",
                raw_filename,
            )
            continue

        # Look up the original content.
        original = originals.get(raw_filename, "")
        if not original:
            # Try matching by just the filename part.
            for key, content in originals.items():
                if Path(key).name == Path(raw_filename).name:
                    original = content
                    break

        # Clean up the refactored code (remove trailing whitespace issues).
        refactored_code = refactored_code.rstrip() + "\n"

        plan.add_change(
            path=resolved_path,
            original=original,
            refactored=refactored_code,
            explanation=explanation,
        )

    logger.info(
        "Parsed refactor plan: %d files with changes",
        plan.files_changed,
    )
    return plan


def _resolve_filename(
    raw_filename: str,
    file_map: dict[str, Path],
) -> Path | None:
    """Resolve a filename from the LLM response to a real file path.

    Tries exact match first, then progressively looser matching.

    Args:
        raw_filename: The filename as written by the LLM.
        file_map: Known filename → path mapping.

    Returns:
        The resolved ``Path``, or ``None`` if unresolvable.
    """
    # Exact match.
    if raw_filename in file_map:
        return file_map[raw_filename]

    # Match by basename only.
    raw_basename = Path(raw_filename).name
    for key, path in file_map.items():
        if Path(key).name == raw_basename:
            return path

    # Match by path suffix (LLM might use relative path).
    for key, path in file_map.items():
        if key.endswith(raw_filename) or raw_filename.endswith(key):
            return path

    return None
