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
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show proposed changes without writing files.",
    ),
    no_confirm: bool = typer.Option(
        False,
        "--no-confirm",
        "-y",
        help="Apply changes without confirmation prompt.",
    ),
    no_backup: bool = typer.Option(
        False,
        "--no-backup",
        help="Skip creating backup files before writing.",
    ),
    all_files: bool = typer.Option(
        False,
        "--all-files",
        help=(
            "Refactor every file in the codebase using a two-phase "
            "strategy: first generate an overall plan, then refactor "
            "all files in token-budget batches.  Requires a directory path."
        ),
    ),
) -> None:
    """Refactor Python code and write changes to files."""
    _run_refactor(
        path,
        instructions=instructions,
        model_override=model,
        dry_run=dry_run,
        no_confirm=no_confirm,
        no_backup=no_backup,
        all_files=all_files,
    )


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


def _run_refactor(
    path: Path,
    *,
    instructions: str = "",
    model_override: str = "",
    dry_run: bool = False,
    no_confirm: bool = False,
    no_backup: bool = False,
    all_files: bool = False,
) -> None:
    """Execute the refactoring workflow with diff review and file writing.

    Flow:
    1. Read target file(s) and build context.
    2. Send to LLM for refactoring.
    3. Parse structured response into a RefactorPlan.
    4. Display diffs for user review.
    5. On confirmation, write changes to disk.

    Args:
        path: Path to the target file or directory.
        instructions: Refactoring instructions.
        model_override: Optional model override.
        dry_run: If True, show changes but don't write.
        no_confirm: If True, skip confirmation prompt.
        no_backup: If True, skip creating backup files.
        all_files: If True and path is a directory, use multi-pass
            codebase-wide refactoring instead of single-pass context packing.
    """
    from rich.syntax import Syntax

    from pyagent.writer import has_uncommitted_changes, is_git_repo, write_changes

    agent = _create_agent(model_override=model_override)

    if all_files:
        if not path.is_dir():
            err_console.print(
                "[red]--all-files requires a directory path.[/red]"
            )
            raise typer.Exit(1)

        plan = _run_codebase_refactor(agent, path, instructions=instructions)

    else:
        # ── Single-file or best-effort directory refactoring ─────────────────
        file_map: dict[str, Path] = {}
        originals: dict[str, str] = {}

        if path.is_dir():
            from pyagent.context import assemble_context

            with console.status("[bold]Indexing codebase..."):
                ctx = agent.load_codebase(str(path))

            console.print(
                f"[dim]Indexed {ctx.file_count} files "
                f"(~{ctx.total_tokens:,} tokens)[/dim]"
            )

            with console.status("[bold]Selecting relevant files..."):
                code = assemble_context(ctx, query=instructions)

            # Build file map from all source modules in context.
            for mod_path, module in ctx.source_modules.items():
                rel = str(
                    mod_path.relative_to(ctx.root)
                    if mod_path.is_relative_to(ctx.root)
                    else mod_path
                )
                file_map[rel] = mod_path
                file_map[mod_path.name] = mod_path
                originals[rel] = module.source
                originals[mod_path.name] = module.source

            filename = str(path)

        elif path.is_file():
            code = path.read_text(encoding="utf-8")
            filename = path.name
            resolved = path.resolve()
            file_map[path.name] = resolved
            file_map[str(path)] = resolved
            originals[path.name] = code
            originals[str(path)] = code

            # Load surrounding context.
            package_root = _find_package_root(path)
            if package_root and package_root != path:
                with console.status("[bold]Loading package context..."):
                    agent.load_codebase(str(package_root))
        else:
            err_console.print(f"[red]Invalid path: {path}[/red]")
            raise typer.Exit(1)

        with console.status("[bold]Refactoring..."):
            plan = asyncio.run(
                agent.refactor_with_plan(
                    file_map=file_map,
                    originals=originals,
                    code=code,
                    filename=filename,
                    instructions=instructions,
                )
            )

    # Display results.
    if plan.summary:
        console.print()
        console.print(
            Panel(Markdown(plan.summary), title="Summary", border_style="blue")
        )

    if plan.files_changed == 0:
        console.print("\n[yellow]No changes proposed.[/yellow]")
        return

    # Show diffs for each changed file.
    console.print(
        f"\n[bold]{plan.files_changed} file(s) with proposed changes:[/bold]\n"
    )

    for change in plan.changes:
        if not change.has_changes:
            continue

        rel_path = change.path.name
        console.print(
            Panel(
                f"[bold]{rel_path}[/bold]  {change.stat_summary}",
                border_style="cyan",
                expand=False,
            )
        )

        if change.explanation:
            console.print(f"  [dim]{change.explanation}[/dim]\n")

        diff_text = change.diff
        if diff_text:
            console.print(
                Syntax(diff_text, "diff", theme="monokai", line_numbers=False)
            )
        console.print()

    # Dry run — stop here.
    if dry_run:
        console.print("[yellow]Dry run — no files were modified.[/yellow]")
        return

    # Safety checks before writing.
    has_git = is_git_repo(path)
    dirty_files: list[str] = []

    if has_git:
        for change in plan.changes:
            if change.has_changes and has_uncommitted_changes(change.path):
                dirty_files.append(change.path.name)

    if dirty_files:
        console.print(
            Panel(
                "[yellow]Warning:[/yellow] The following files have "
                "uncommitted git changes:\n"
                + "\n".join(f"  • {f}" for f in dirty_files)
                + "\n\nBackups will be created regardless of --no-backup.",
                border_style="yellow",
            )
        )
        # Force backups for dirty files.
        no_backup = False

    if not has_git and not no_backup:
        console.print(
            "[dim]Not a git repository — backups will be created in "
            ".pyagent_backup/[/dim]\n"
        )

    # Confirmation.
    if not no_confirm:
        choice = Prompt.ask(
            "[bold]Apply these changes?[/bold]",
            choices=["yes", "no", "y", "n"],
            default="no",
        )
        if choice.lower() not in {"yes", "y"}:
            console.print("[dim]Aborted — no files were modified.[/dim]")
            return

    # Write changes.
    written = write_changes(plan, backup=not no_backup)

    if written:
        console.print(
            Panel(
                "\n".join(f"  ✓ {p.name}" for p in written),
                title=f"[green]{len(written)} file(s) updated[/green]",
                border_style="green",
            )
        )
    else:
        console.print("[yellow]No files were written.[/yellow]")


def _run_codebase_refactor(
    agent: "Agent",
    path: Path,
    *,
    instructions: str = "",
) -> "RefactorPlan":
    """Run the two-phase codebase-wide refactoring and return the merged plan.

    Phase 1: Generate an overall strategy from the structural summary.
    Phase 2: Refactor all files in token-budget batches using that strategy.

    Progress is printed to the console between phases and batches.

    Args:
        agent: A configured ``Agent`` instance.
        path: Path to the codebase root directory.
        instructions: Optional refactoring focus.

    Returns:
        A ``RefactorPlan`` with changes from every batch merged together.
    """
    from pyagent.writer import RefactorPlan

    with console.status("[bold]Indexing codebase..."):
        ctx = agent.load_codebase(str(path))

    console.print(
        f"[dim]Indexed {ctx.file_count} files "
        f"(~{ctx.total_tokens:,} tokens)[/dim]"
    )

    # Use a mutable container so the callback (a closure) can update the
    # status text while asyncio.run() drives the coroutine.
    _status_ref: list[object] = []

    def _update(msg: str) -> None:
        if _status_ref:
            _status_ref[0].update(f"[bold]{msg}")  # type: ignore[attr-defined]
        else:
            console.print(f"[dim]{msg}[/dim]")

    with console.status("[bold]Planning codebase refactoring...") as status:
        _status_ref.append(status)
        plan: RefactorPlan = asyncio.run(
            agent.refactor_codebase(
                instructions=instructions,
                on_progress=_update,
            )
        )
        _status_ref.clear()

    return plan


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
