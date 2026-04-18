"""Smoke tests for the archagent package structure — no API key required."""


def test_package_imports() -> None:
    # Catches: broken imports after the restructure, missing submodules.
    import archagent
    from archagent import agent, logging, memory, prompts, rag, tools

    assert hasattr(archagent, "__version__")
    assert hasattr(agent, "ArchAgent")
    assert hasattr(memory, "list_sessions")
    assert hasattr(prompts, "SYSTEM_PROMPT")
    assert hasattr(rag, "build_index")
    assert hasattr(tools, "TOOL_DEFINITIONS")
    assert callable(logging.get_logger)
    assert callable(logging.configure_logging)


def test_main_entrypoint_is_importable() -> None:
    # This would have failed on the pre-restructure code because of the
    # Python-2 `except KeyboardInterrupt, EOFError:` syntax error in main.py.
    from archagent import __main__

    assert callable(__main__.main)
    assert callable(__main__.pick_session)


def test_logging_helper_returns_namespaced_logger() -> None:
    from archagent.logging import get_logger

    logger = get_logger("test_module")
    assert logger.name == "archagent.test_module"
