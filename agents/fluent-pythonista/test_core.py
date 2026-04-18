"""Smoke tests for core modules — no API key required."""

import pytest
import typer
from pathlib import Path
from typer.testing import CliRunner

from pyagent.__main__ import _resolve_directory_mode, app
from pyagent.context import (
    FileCategory,
    assemble_context,
    build_context,
    classify_file,
    discover_python_files,
    parse_module,
    score_modules,
)
from pyagent.memory import ConversationMemory
from pyagent.plan_model import (
    CodebasePlan,
    FileNote,
    RefactorTheme,
    load_plan,
    parse_codebase_plan,
    save_plan,
)
from pyagent.prompts import build_batch_refactor_prompt
from pyagent.rag import load_knowledge_base
from pyagent.tools.refactor import check_batch_adherence
from pyagent.writer import FileChange, RefactorPlan

# pyagent's docs live under <repo>/docs/python/.  This path is
# test_core.py → agents/fluent-pythonista → agents → <repo>, then the
# python/ subdir.
DOCS_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "python"


class TestKnowledgeBase:
    """Tests for the RAG knowledge base."""

    def test_load_knowledge_base(self) -> None:
        kb = load_knowledge_base(DOCS_PATH)
        assert kb.total_chunks > 0

    def test_retrieve_returns_relevant_chunks(self) -> None:
        kb = load_knowledge_base(DOCS_PATH)
        results = kb.retrieve("type annotations", max_chunks=5)
        assert len(results) > 0
        assert any("type" in chunk.content.lower() for chunk in results)

    def test_retrieve_with_source_filter(self) -> None:
        kb = load_knowledge_base(DOCS_PATH)
        results = kb.retrieve(
            "refactoring",
            sources=["refactoring_playbook"],
            max_chunks=5,
        )
        assert all(chunk.source == "refactoring_playbook" for chunk in results)

    def test_retrieve_formatted_returns_string(self) -> None:
        kb = load_knowledge_base(DOCS_PATH)
        text = kb.retrieve_formatted("error handling", max_chunks=3)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_default_docs_path_finds_chunks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression: ``Settings().docs_path`` must resolve to a real
        directory of pyagent's markdown corpus, and ``load_knowledge_base``
        must find chunks there.

        Previously the default pointed at ``<repo>/docs`` (parent of the
        per-agent subdirs), and ``load_knowledge_base`` does a
        non-recursive ``glob("*.md")``, so the KB silently loaded zero
        chunks on defaults.  If anyone reintroduces that mistake — either
        by broadening the default back to ``<repo>/docs`` or by moving
        the corpus — this test catches it immediately.
        """
        from pyagent.config import Settings

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-regression")
        settings = Settings()

        assert settings.docs_path.is_dir(), (
            f"Default docs_path does not exist: {settings.docs_path}"
        )
        kb = load_knowledge_base(settings.docs_path)
        assert kb.total_chunks > 0, (
            f"Default docs_path={settings.docs_path} yielded 0 chunks — "
            "either the path is wrong or the glob isn't finding the markdown files."
        )


class TestContext:
    """Tests for codebase ingestion and context assembly."""

    def test_discover_python_files(self) -> None:
        src_dir = Path(__file__).resolve().parent / "src" / "pyagent"
        files = discover_python_files(src_dir)
        assert len(files) > 0
        assert all(f.suffix == ".py" for f in files)

    def test_parse_module_extracts_structure(self) -> None:
        module_path = (
            Path(__file__).resolve().parent / "src" / "pyagent" / "config.py"
        )
        info = parse_module(module_path)
        assert info.path == module_path
        assert any(cls.name == "Settings" for cls in info.classes)

    def test_parse_module_handles_syntax_error(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(:\n    pass\n")
        info = parse_module(bad_file)
        assert info.classes == []
        assert info.functions == []
        assert info.source == "def broken(:\n    pass\n"

    def test_classify_file_source(self, tmp_path: Path) -> None:
        assert classify_file(tmp_path / "service.py") == FileCategory.SOURCE

    def test_classify_file_test(self, tmp_path: Path) -> None:
        assert classify_file(tmp_path / "test_service.py") == FileCategory.TEST
        assert classify_file(tmp_path / "service_test.py") == FileCategory.TEST

    def test_classify_file_init(self, tmp_path: Path) -> None:
        assert classify_file(tmp_path / "__init__.py") == FileCategory.INIT

    def test_classify_file_in_tests_dir(self, tmp_path: Path) -> None:
        assert classify_file(tmp_path / "tests" / "helpers.py") == FileCategory.TEST

    def test_module_info_token_estimate(self) -> None:
        module_path = (
            Path(__file__).resolve().parent / "src" / "pyagent" / "config.py"
        )
        info = parse_module(module_path)
        assert info.token_estimate > 0
        assert info.line_count > 0

    def test_score_modules_prioritizes_source(self, tmp_path: Path) -> None:
        # Create a small codebase with source and test files.
        (tmp_path / "app.py").write_text("def main() -> None:\n    pass\n")
        (tmp_path / "test_app.py").write_text("def test_main() -> None:\n    pass\n")
        ctx = build_context(tmp_path)
        scored = score_modules(ctx, include_tests=True)
        source_scores = [s for s in scored if s.module.category == FileCategory.SOURCE]
        test_scores = [s for s in scored if s.module.category == FileCategory.TEST]
        if source_scores and test_scores:
            assert source_scores[0].score > test_scores[0].score

    def test_score_modules_excludes_tests_by_default(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("x = 1\n")
        (tmp_path / "test_app.py").write_text("x = 2\n")
        ctx = build_context(tmp_path)
        scored = score_modules(ctx)
        assert all(s.module.category != FileCategory.TEST for s in scored)

    def test_assemble_context_respects_budget(self, tmp_path: Path) -> None:
        # Create files that together exceed a small budget.
        for i in range(10):
            (tmp_path / f"module_{i}.py").write_text(f"x = {i}\n" * 100)
        ctx = build_context(tmp_path)
        result = assemble_context(ctx, token_budget=2000)
        # Should be within budget (rough check).
        assert len(result) // 4 < 3000  # Some slack for formatting

    def test_assemble_context_includes_summary(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("def hello() -> str:\n    return 'hi'\n")
        ctx = build_context(tmp_path)
        result = assemble_context(ctx)
        assert "Codebase Structure" in result
        assert "app.py" in result


class TestMemory:
    """Tests for conversation memory."""

    def test_add_and_retrieve_messages(self) -> None:
        memory = ConversationMemory()
        memory.add_user_message("Hello")
        memory.add_assistant_message("Hi there")

        messages = memory.to_api_messages()
        assert len(messages) == 2
        assert messages[0] == {"role": "user", "content": "Hello"}
        assert messages[1] == {"role": "assistant", "content": "Hi there"}

    def test_turn_count(self) -> None:
        memory = ConversationMemory()
        memory.add_user_message("First")
        memory.add_assistant_message("Response")
        memory.add_user_message("Second")
        assert memory.turn_count == 2

    def test_trimming(self) -> None:
        memory = ConversationMemory(max_messages=4)
        for i in range(6):
            memory.add_user_message(f"msg {i}")
        assert len(memory.messages) == 4

    def test_clear(self) -> None:
        memory = ConversationMemory()
        memory.add_user_message("Hello")
        memory.clear()
        assert len(memory.messages) == 0


class TestRefactorWorkflow:
    """Tests for the plan → execute handoff in the codebase-wide refactor flow."""

    def _sample_plan(self) -> CodebasePlan:
        return CodebasePlan(
            assessment="Legacy type syntax and deep nesting throughout the app.",
            themes=[
                RefactorTheme(
                    name="Modernize Type Annotations",
                    description="Replace Optional[X] with X | None; List -> list; etc.",
                    target_files=["src/app.py", "src/utils.py"],
                ),
                RefactorTheme(
                    name="Introduce Early Return",
                    description="Flatten nested conditionals.",
                    target_files=["src/app.py"],
                ),
            ],
            order_of_operations=["Modernize types first", "Then flatten conditionals"],
            file_notes=[FileNote(path="src/app.py", note="Entry point; touch last.")],
        )

    def test_batch_system_prompt_has_valid_fence_instruction(self) -> None:
        plan = self._sample_plan()
        system, _user = build_batch_refactor_prompt(
            "### FILE: x.py\n\n```python\npass\n```",
            batch_label="1/1",
            overall_plan=plan,
        )
        # Parser requires ```python fences — prompt must tell the LLM that
        # clearly, both in the instruction and in the example.
        assert "```python" in system
        assert "fenced with ```python and ```" in system

    def test_batch_system_prompt_not_indented(self) -> None:
        plan = self._sample_plan()
        system, _user = build_batch_refactor_prompt(
            "### FILE: x.py\n\n```python\npass\n```",
            overall_plan=plan,
        )
        offending = [
            line
            for line in system.splitlines()
            if line.startswith("        ") and line.strip()
        ]
        assert not offending, (
            f"Batch system prompt has unexpected 8-space indentation on "
            f"{len(offending)} line(s); first: {offending[0]!r}"
        )

    def test_batch_system_prompt_places_plan_before_format_rules(self) -> None:
        plan = self._sample_plan()
        system, _user = build_batch_refactor_prompt(
            "### FILE: x.py\n\n```python\npass\n```",
            overall_plan=plan,
        )
        plan_idx = system.index("Overall Refactoring Plan")
        fmt_idx = system.index("Output Format")
        assert plan_idx < fmt_idx

    def test_batch_system_prompt_embeds_theme_names(self) -> None:
        plan = self._sample_plan()
        system, _user = build_batch_refactor_prompt(
            "### FILE: x.py\n\n```python\npass\n```",
            overall_plan=plan,
        )
        for theme in plan.themes:
            assert theme.name in system

    def test_batch_prompt_handles_missing_plan(self) -> None:
        # Must not raise when no plan is provided.
        system, _user = build_batch_refactor_prompt(
            "### FILE: x.py\n\n```python\npass\n```",
            overall_plan=None,
        )
        assert "Overall Refactoring Plan" in system

    def test_codebase_plan_to_markdown_contains_themes(self) -> None:
        plan = self._sample_plan()
        md = plan.to_markdown()
        for theme in plan.themes:
            assert theme.name in md
        assert "Order of Operations" in md
        assert "File-Specific Notes" in md

    def test_parse_codebase_plan_handles_json_fence(self) -> None:
        response = (
            "Here is the plan.\n\n"
            "## Overall Assessment\n\nLots of legacy typing.\n\n"
            "```json\n"
            '{\n'
            '  "assessment": "Lots of legacy typing.",\n'
            '  "themes": [\n'
            '    {"name": "Modernize Type Annotations", '
            '"description": "X | None", "target_files": ["a.py"]}\n'
            '  ],\n'
            '  "order_of_operations": [],\n'
            '  "file_notes": [],\n'
            '  "recommended_dependencies": []\n'
            '}\n'
            "```\n"
        )
        plan = parse_codebase_plan(response)
        assert plan.theme_names() == ["Modernize Type Annotations"]
        assert plan.themes[0].target_files == ["a.py"]

    def test_parse_codebase_plan_falls_back_on_invalid_json(self) -> None:
        response = "No structured block here — just some prose about the codebase."
        plan = parse_codebase_plan(response)
        assert plan.themes == []
        assert response in plan.assessment

    def test_save_and_load_plan_roundtrip(self, tmp_path: Path) -> None:
        plan = self._sample_plan()
        save_plan(plan, tmp_path)
        loaded = load_plan(tmp_path)
        assert loaded is not None
        assert loaded.theme_names() == plan.theme_names()
        assert loaded.assessment == plan.assessment
        assert (tmp_path / ".pyagent" / "last_plan.md").exists()

    def test_load_plan_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert load_plan(tmp_path) is None

    def test_check_batch_adherence_detects_missing_themes(self) -> None:
        plan = self._sample_plan()
        batch = RefactorPlan(
            summary="Cleaned up variable names and fixed a bug.",
            changes=[
                FileChange(
                    path=Path("src/app.py"),
                    original="x = 1\n",
                    refactored="x = 2\n",
                    explanation="Updated the value.",
                )
            ],
        )
        report = check_batch_adherence(batch, plan, batch_label="1/1")
        assert report.themes_referenced == []
        assert set(report.themes_missing) == {t.name for t in plan.themes}
        assert report.followed_plan is False

    def test_check_batch_adherence_detects_applied_themes(self) -> None:
        plan = self._sample_plan()
        batch = RefactorPlan(
            summary=(
                "Applied Modernize Type Annotations across the batch and "
                "introduced an early return in app.py."
            ),
            changes=[
                FileChange(
                    path=Path("src/app.py"),
                    original="x = 1\n",
                    refactored="x: int = 1\n",
                    explanation="Introduce Early Return and typed the binding.",
                )
            ],
        )
        report = check_batch_adherence(batch, plan, batch_label="1/1")
        assert set(report.themes_referenced) == {t.name for t in plan.themes}
        assert report.themes_missing == []
        assert report.followed_plan is True


class TestCliModeResolution:
    """Tests for the implicit file-vs-directory mode selection in `refactor`."""

    def test_directory_no_instructions_picks_full(self, tmp_path: Path) -> None:
        assert _resolve_directory_mode(tmp_path, "", False, False) == "full"

    def test_directory_with_instructions_picks_partial(
        self, tmp_path: Path
    ) -> None:
        assert (
            _resolve_directory_mode(tmp_path, "modernize types", False, False)
            == "partial"
        )

    def test_partial_flag_forces_partial(self, tmp_path: Path) -> None:
        assert _resolve_directory_mode(tmp_path, "", True, False) == "partial"

    def test_full_flag_forces_full_over_narrow_instructions(
        self, tmp_path: Path
    ) -> None:
        assert (
            _resolve_directory_mode(tmp_path, "fix types", False, True) == "full"
        )

    def test_both_flags_is_error(self, tmp_path: Path) -> None:
        with pytest.raises(typer.BadParameter):
            _resolve_directory_mode(tmp_path, "", True, True)

    def test_mode_flag_on_file_is_error(self, tmp_path: Path) -> None:
        file_path = tmp_path / "x.py"
        file_path.write_text("x = 1\n")
        with pytest.raises(typer.BadParameter):
            _resolve_directory_mode(file_path, "", True, False)
        with pytest.raises(typer.BadParameter):
            _resolve_directory_mode(file_path, "", False, True)

    def test_whitespace_only_instructions_treated_as_empty(
        self, tmp_path: Path
    ) -> None:
        assert _resolve_directory_mode(tmp_path, "   \n\t  ", False, False) == "full"

    def test_refactor_help_no_longer_mentions_all_files(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["refactor", "--help"])
        assert result.exit_code == 0
        assert "--all-files" not in result.output
        assert "--partial" in result.output
        assert "--full" in result.output
