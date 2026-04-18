"""Structured model for the codebase-wide refactoring plan.

The plan is produced by the first ("planning") phase of a codebase-wide
refactor and consumed by the second ("execution") phase.  Keeping it as a
validated Pydantic model — rather than free-form text — gives every batch
a canonical, deterministic view of what themes to apply, which in turn lets
us detect and surface plan drift during execution.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from pyagent.logging import get_logger

logger = get_logger(__name__)

_ARTIFACTS_DIR = ".pyagent"
_PLAN_JSON = "last_plan.json"
_PLAN_MD = "last_plan.md"

# Match a fenced ```json ... ``` block anywhere in the response.
_JSON_BLOCK_RE = re.compile(r"```json\s*\n(?P<body>.*?)\n```", re.DOTALL)


class RefactorTheme(BaseModel):
    """A single named refactoring theme to apply across the codebase."""

    name: str
    description: str
    target_files: list[str] = Field(default_factory=list)


class FileNote(BaseModel):
    """A per-file callout attached to the plan."""

    path: str
    note: str


class CodebasePlan(BaseModel):
    """Structured refactoring plan for a whole codebase."""

    assessment: str
    themes: list[RefactorTheme] = Field(default_factory=list)
    order_of_operations: list[str] = Field(default_factory=list)
    file_notes: list[FileNote] = Field(default_factory=list)
    recommended_dependencies: list[str] = Field(default_factory=list)

    def theme_names(self) -> list[str]:
        """Return the names of every theme in declaration order."""
        return [theme.name for theme in self.themes]

    def to_markdown(self) -> str:
        """Render the plan as markdown for injection into prompts or display."""
        assessment = self.assessment.strip() or "_(none)_"
        parts: list[str] = ["### Overall Assessment", assessment]

        if self.themes:
            parts.append("\n### Refactoring Themes")
            for idx, theme in enumerate(self.themes, start=1):
                files = (
                    f"  \n  Target files: {', '.join(theme.target_files)}"
                    if theme.target_files
                    else ""
                )
                parts.append(
                    f"{idx}. **{theme.name}** — {theme.description}{files}"
                )

        if self.order_of_operations:
            parts.append("\n### Order of Operations")
            for idx, step in enumerate(self.order_of_operations, start=1):
                parts.append(f"{idx}. {step}")

        if self.file_notes:
            parts.append("\n### File-Specific Notes")
            for note in self.file_notes:
                parts.append(f"- `{note.path}`: {note.note}")

        if self.recommended_dependencies:
            parts.append("\n### Recommended Dependencies")
            for dep in self.recommended_dependencies:
                parts.append(f"- {dep}")

        return "\n".join(parts)


def parse_codebase_plan(llm_response: str) -> CodebasePlan:
    """Parse a planner LLM response into a :class:`CodebasePlan`.

    The planner is instructed to include a fenced ``json`` block that
    matches the ``CodebasePlan`` schema.  This function extracts that block
    and validates it.  If the block is missing or invalid, falls back to a
    minimal plan that carries the raw prose in ``assessment`` so the
    execution phase still has *something* to anchor on.
    """
    match = _JSON_BLOCK_RE.search(llm_response)
    if not match:
        logger.warning(
            "No ```json block found in planner response — falling back to raw prose"
        )
        return CodebasePlan(assessment=llm_response.strip(), themes=[])

    body = match.group("body").strip()
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        logger.warning("Planner JSON block failed to decode: %s", exc)
        return CodebasePlan(assessment=llm_response.strip(), themes=[])

    try:
        return CodebasePlan.model_validate(data)
    except Exception as exc:  # pydantic.ValidationError
        logger.warning("Planner JSON did not match CodebasePlan schema: %s", exc)
        return CodebasePlan(assessment=llm_response.strip(), themes=[])


def save_plan(plan: CodebasePlan, root: Path) -> Path:
    """Persist the plan to ``<root>/.pyagent/last_plan.{json,md}``.

    Returns the JSON path.  Creates the artifacts directory if needed.
    """
    artifacts = root / _ARTIFACTS_DIR
    artifacts.mkdir(exist_ok=True)

    json_path = artifacts / _PLAN_JSON
    md_path = artifacts / _PLAN_MD

    json_path.write_text(
        plan.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(plan.to_markdown() + "\n", encoding="utf-8")

    logger.info("Saved codebase plan to %s", json_path)
    return json_path


def load_plan(root: Path) -> CodebasePlan | None:
    """Load a previously saved plan from ``<root>/.pyagent/last_plan.json``.

    Returns ``None`` if no plan has been saved yet.  Raises if the file
    exists but is malformed — callers that need a resilient load should
    wrap this.
    """
    json_path = root / _ARTIFACTS_DIR / _PLAN_JSON
    if not json_path.exists():
        return None
    return CodebasePlan.model_validate_json(json_path.read_text(encoding="utf-8"))
