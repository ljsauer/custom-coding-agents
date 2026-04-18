"""CLI entrypoint for PyAgent.

Provides commands for reviewing, refactoring, and explaining Python code,
plus an interactive chat mode for free-form conversation about a codebase.
"""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from pyagent import __version__

app = typer.Typer(
    name="pyagent",
    help="An opinionated Python code review, refactoring, and explanation agent.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()
err_console = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"pyagent {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """PyAgent — opinionated Python code intelligence."""


@app.command()
def review(
    path: Path = typer.Argument(
        ...,
        help="Path to a Python file or directory to review.",
        exists=True,
        readable=True,
    ),
    instructions: str = typer.Option(
        "",
        "--instructions",
        "-i",
        help="Additional review instructions.",
    ),
    model: str = typer.Option(
        "",
        "--model",
        "-m",
        help="Override the default model.",
    ),
) -> None:
    """Review Python code for correctness, style, and best practices."""
    _run_tool("review", path, instructions=instructions, model_override=model)


@app.command()
def refactor(
    path: Path = typer.Argument(
        ...,
        help="Path to a Python file or directory to refactor.",
        exists=True,
        readable=True,
    ),
    instructions: str = typer.Option(
        "",
        "--instructions",
        "-i",
        help="Specific refactoring focus or instructions.",
    ),
    model: str = typer.Option(
        "",
        "--model",
        "-m",
        help="Override the default model.",
    ),
) -> None:
    """Refactor Python code using named patterns from the playbook."""
    _run_tool("refactor", path, instructions=instructions, model_override=model)


@app.command()
def explain(
    path: Path = typer.Argument(
        ...,
        help="Path to a Python file to explain.",
        exists=True,
        readable=True,
    ),
    question: str = typer.Option(
        "",
        "--question",
        "-q",
        help="Specific question about the code.",
    ),
    model: str = typer.Option(
        "",
        "--model",
        "-m",
        help="Override the default model.",
    ),
) -> None:
    """Explain code structure, patterns, and design decisions."""
    _run_tool("explain", path, instructions=question, model_override=model)


@app.command()
def chat(
    path: Path = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to a codebase to load for context.",
        exists=True,
        readable=True,
    ),
    model: str = typer.Option(
        "",
        "--model",
        "-m",
        help="Override the default model.",
    ),
) -> None:
    """Start an interactive chat session about Python code."""
    agent = _create_agent(model_override=model)

    if path:
        with console.status("[bold]Loading codebase..."):
            ctx = agent.load_codebase(str(path))
        console.print(
            Panel(
                f"Loaded [bold]{ctx.file_count}[/bold] files from [cyan]{path}[/cyan]",
                title="Codebase Loaded",
                border_style="green",
            )
        )

    console.print(
        Panel(
            "Type your message and press Enter. Type [bold]quit[/bold] or "
            "[bold]exit[/bold] to end the session.",
            title="PyAgent Chat",
            border_style="blue",
        )
    )

    while True:
        try:
            user_input = Prompt.ask("\n[bold blue]You[/bold blue]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session ended.[/dim]")
            break

        if user_input.strip().lower() in {"quit", "exit", "q"}:
            console.print("[dim]Session ended.[/dim]")
            break

        if not user_input.strip():
            continue

        with console.status("[bold]Thinking..."):
            response = asyncio.run(agent.chat(user_input))

        console.print()
        console.print(Markdown(response))


@app.command()
def info() -> None:
    """Show agent configuration and loaded knowledge base stats."""
    from pyagent.config import Settings
    from pyagent.rag import load_knowledge_base

    try:
        settings = Settings()
    except Exception as exc:
        err_console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(1) from exc

    kb = load_knowledge_base(settings.docs_path)

    console.print(
        Panel(
            f"[bold]Model:[/bold]       {settings.model}\n"
            f"[bold]Docs path:[/bold]   {settings.docs_path}\n"
            f"[bold]Log level:[/bold]   {settings.log_level}\n"
            f"[bold]Max tokens:[/bold]  {settings.max_tokens}\n"
            f"[bold]KB chunks:[/bold]   {kb.total_chunks}",
            title="PyAgent Configuration",
            border_style="blue",
        )
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _create_agent(*, model_override: str = "") -> "Agent":
    """Create an agent instance, applying CLI overrides.

    Args:
        model_override: If non-empty, overrides the configured model.

    Returns:
        A configured ``Agent`` instance.
    """
    from pyagent.agent import Agent
    from pyagent.config import Settings

    try:
        settings = Settings()
    except Exception as exc:
        err_console.print(f"[red]Configuration error:[/red] {exc}")
        err_console.print(
            "[dim]Ensure ANTHROPIC_API_KEY is set in your environment or .env file.[/dim]"
        )
        raise typer.Exit(1) from exc

    if model_override:
        settings.model = model_override

    return Agent(settings)


def _run_tool(
    tool_name: str,
    path: Path,
    *,
    instructions: str = "",
    model_override: str = "",
) -> None:
    """Execute a tool command (review, refactor, or explain).

    Handles file reading, agent creation, async execution, and output
    rendering.

    Args:
        tool_name: One of "review", "refactor", "explain".
        path: Path to the target file or directory.
        instructions: Additional instructions or questions.
        model_override: Optional model override.
    """
    agent = _create_agent(model_override=model_override)

    if path.is_dir():
        # Directory-level operation: use smart context assembly.
        from pyagent.context import assemble_context

        with console.status("[bold]Indexing codebase..."):
            ctx = agent.load_codebase(str(path))

        file_count = ctx.file_count
        total_tokens = ctx.total_tokens
        console.print(
            f"[dim]Indexed {file_count} files (~{total_tokens:,} tokens total). "
            f"Assembling context...[/dim]"
        )

        with console.status("[bold]Selecting relevant files..."):
            code = assemble_context(
                ctx,
                query=instructions,
                include_tests=(tool_name == "review"),
            )
        filename = str(path)

    elif path.is_file():
        # Single file: load codebase for surrounding context if in a package.
        code = path.read_text(encoding="utf-8")
        filename = path.name

        # Try to load the parent package for related-module context.
        package_root = _find_package_root(path)
        if package_root and package_root != path:
            with console.status("[bold]Loading package context..."):
                agent.load_codebase(str(package_root))
    else:
        err_console.print(f"[red]Invalid path: {path}[/red]")
        raise typer.Exit(1)

    tool_method = getattr(agent, tool_name)
    kwargs = {"filename": filename}
    if tool_name == "explain":
        kwargs["question"] = instructions
    else:
        kwargs["instructions"] = instructions

    with console.status(f"[bold]Running {tool_name}..."):
        result = asyncio.run(tool_method(code, **kwargs))

    console.print()
    console.print(Markdown(result))


def _find_package_root(file_path: Path) -> Path | None:
    """Walk up from a file to find the nearest package root.

    Looks for ``pyproject.toml``, ``setup.py``, or a ``src/`` layout.
    Falls back to the nearest directory containing an ``__init__.py``.

    Args:
        file_path: Path to a Python file.

    Returns:
        The package root path, or ``None`` if not found.
    """
    markers = {"pyproject.toml", "setup.py", "setup.cfg"}
    current = file_path.parent

    for _ in range(10):  # Don't walk up forever.
        if any((current / marker).exists() for marker in markers):
            return current
        if (current / "src").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


if __name__ == "__main__":
    app()
