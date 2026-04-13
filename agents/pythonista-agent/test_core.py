"""Smoke tests for core modules — no API key required."""

from pathlib import Path

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
from pyagent.rag import load_knowledge_base

DOCS_PATH = Path(__file__).resolve().parent.parent / "docs"


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


class TestContext:
    """Tests for codebase ingestion and context assembly."""

    def test_discover_python_files(self) -> None:
        src_dir = Path(__file__).resolve().parent.parent / "src" / "pyagent"
        files = discover_python_files(src_dir)
        assert len(files) > 0
        assert all(f.suffix == ".py" for f in files)

    def test_parse_module_extracts_structure(self) -> None:
        module_path = (
            Path(__file__).resolve().parent.parent / "src" / "pyagent" / "config.py"
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
            Path(__file__).resolve().parent.parent / "src" / "pyagent" / "config.py"
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
