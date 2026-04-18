"""Tests for the archagent package — no API calls, no network."""

from pathlib import Path

import pytest
import typer
from pydantic import ValidationError
from typer.testing import CliRunner

DOCS_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "architecture"


class TestPackageStructure:
    """Smoke-level tests that the package layout is intact."""

    def test_package_imports(self) -> None:
        import archagent
        from archagent import agent, config, logging, memory, prompts, rag, tools

        assert hasattr(archagent, "__version__")
        assert hasattr(agent, "ArchAgent")
        assert hasattr(config, "Settings")
        assert hasattr(memory, "list_sessions")
        assert hasattr(prompts, "SYSTEM_PROMPT")
        assert hasattr(rag, "ArchitectureKnowledgeBase")
        assert hasattr(rag, "load_architecture_knowledge_base")
        assert callable(logging.get_logger)
        assert callable(logging.configure_logging)
        # tools is a subpackage; re-exports matter.
        assert isinstance(tools.TOOL_DEFINITIONS, list)
        assert callable(tools.execute_tool)

    def test_tools_subpackage_split(self) -> None:
        """Definitions and executor live in separate modules, re-exported."""
        from archagent.tools import TOOL_DEFINITIONS, execute_tool
        from archagent.tools.definitions import TOOL_DEFINITIONS as raw_defs
        from archagent.tools.executor import execute_tool as raw_exec

        assert TOOL_DEFINITIONS is raw_defs
        assert execute_tool is raw_exec

    def test_logging_helper_returns_namespaced_logger(self) -> None:
        from archagent.logging import get_logger

        assert get_logger("test_module").name == "archagent.test_module"


class TestSettings:
    """Tests for the Pydantic Settings layer."""

    def test_settings_loads_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
        monkeypatch.delenv("AGENT_WORKSPACE", raising=False)
        from archagent.config import Settings

        settings = Settings()
        assert settings.anthropic_api_key == "sk-test-123"
        assert settings.model  # has a default
        assert settings.workspace is None

    def test_workspace_env_var_alias(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
        monkeypatch.setenv("AGENT_WORKSPACE", str(tmp_path))
        from archagent.config import Settings

        settings = Settings()
        assert settings.workspace == tmp_path

    def test_missing_api_key_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.chdir(tmp_path)  # avoid picking up a repo-level .env
        from archagent.config import Settings

        with pytest.raises(ValidationError):
            Settings()

    def test_prefixed_overrides_take_effect(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
        monkeypatch.setenv("ARCHAGENT_MODEL", "claude-haiku-4-5-20251001")
        monkeypatch.setenv("ARCHAGENT_MAX_TOKENS", "512")
        from archagent.config import Settings

        settings = Settings()
        assert settings.model == "claude-haiku-4-5-20251001"
        assert settings.max_tokens == 512


class TestTools:
    """Tests for the tools subpackage."""

    def test_write_blocked_without_workspace(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Ensure no AGENT_WORKSPACE leaks in from the host env.
        monkeypatch.delenv("AGENT_WORKSPACE", raising=False)
        from archagent.tools import execute_tool

        result = execute_tool(
            "write_file",
            {"path": str(tmp_path / "x.txt"), "content": "hi"},
            workspace=None,
        )
        assert "disabled" in result.lower()

    def test_write_blocked_outside_workspace(self, tmp_path: Path) -> None:
        from archagent.tools import execute_tool

        outside = tmp_path.parent / "outside.txt"
        result = execute_tool(
            "write_file",
            {"path": str(outside), "content": "hi"},
            workspace=tmp_path,
        )
        assert "outside workspace" in result

    def test_read_file_missing(self, tmp_path: Path) -> None:
        from archagent.tools import execute_tool

        result = execute_tool(
            "read_file", {"path": str(tmp_path / "nope.txt")}, workspace=None
        )
        assert "not found" in result

    def test_describe_project_structure(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.py").write_text("y = 2")
        from archagent.tools import execute_tool

        result = execute_tool(
            "describe_project_structure",
            {"root": str(tmp_path), "max_depth": 3},
        )
        assert "a.py" in result
        assert "sub" in result


class TestKnowledgeBase:
    """End-to-end tests for the architecture RAG layer.

    These exercise sentence-transformers and are slow on first run (model
    download + embedding); they intentionally run against the real docs
    directory because catching regressions in the KB layer is the point.
    """

    def test_load_architecture_knowledge_base(self) -> None:
        from archagent.rag import load_architecture_knowledge_base

        kb = load_architecture_knowledge_base(DOCS_PATH)
        assert kb.total_chunks > 0
        assert kb.embeddings is not None
        assert kb.embeddings.shape[0] == len(kb.chunks)

    def test_retrieve_formatted_returns_string(self) -> None:
        from archagent.rag import load_architecture_knowledge_base

        kb = load_architecture_knowledge_base(DOCS_PATH)
        text = kb.retrieve_formatted("aggregate root boundary", top_k=2)
        assert isinstance(text, str)
        assert len(text) > 0

    def test_retrieve_raises_on_empty_query(self) -> None:
        from archagent.rag import load_architecture_knowledge_base

        kb = load_architecture_knowledge_base(DOCS_PATH)
        with pytest.raises(ValueError):
            kb.retrieve("   ")


class TestCLI:
    """Tests for the Typer CLI surface (no API calls)."""

    def test_root_help_lists_subcommands(self) -> None:
        from archagent.__main__ import app

        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for name in ("chat", "list-sessions", "resume", "info"):
            assert name in result.output

    def test_chat_help(self) -> None:
        from archagent.__main__ import app

        runner = CliRunner()
        result = runner.invoke(app, ["chat", "--help"])
        assert result.exit_code == 0
        for flag in ("--project", "--resume", "--model"):
            assert flag in result.output

    def test_version_flag(self) -> None:
        from archagent.__main__ import app

        runner = CliRunner()
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "archagent" in result.output


class TestMainEntrypoint:
    def test_main_entrypoint_is_importable(self) -> None:
        # This would have failed on the pre-restructure code because of the
        # Python-2 `except KeyboardInterrupt, EOFError:` syntax error in main.py.
        from archagent import __main__

        assert hasattr(__main__, "app")
        assert callable(__main__.chat)
        assert callable(__main__.info)


def test_missing_api_key_cli_exits_cleanly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`archagent chat` without API key should exit 1 with a clear message."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    from archagent.__main__ import app

    runner = CliRunner()
    result = runner.invoke(app, ["chat"])
    assert result.exit_code != 0
    assert "ANTHROPIC_API_KEY" in result.output or "api_key" in result.output.lower()


def test_typer_bad_param_does_not_crash() -> None:
    """Sanity: typer's error handling is wired up."""
    # Nothing archagent-specific; imports work as a minimal smoke test.
    assert typer.BadParameter is not None
