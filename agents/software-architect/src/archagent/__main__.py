"""CLI entrypoint for archagent.

Commands:
    chat           Start (or resume) an interactive architecture-review session.
    list-sessions  Show previously saved sessions.
    resume         Shortcut for ``chat --resume SESSION_ID``.
    info           Print resolved configuration and knowledge-base stats.
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from archagent import __version__

app = typer.Typer(
    name="archagent",
    help="Conversational software-architecture advisor grounded in DDD, Clean, Hexagonal, and Onion Architecture.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()
err_console = Console(stderr=True)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"archagent {__version__}")
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
    """archagent — a conversational software-architecture advisor."""


@app.command()
def chat(
    project: str = typer.Option(
        "default",
        "--project",
        "-p",
        help="Project name used to scope persisted decisions and sessions.",
    ),
    resume: str | None = typer.Option(
        None,
        "--resume",
        "-r",
        help="Session ID to resume instead of starting a new one.",
    ),
    model: str = typer.Option(
        "",
        "--model",
        "-m",
        help="Override the default Claude model.",
    ),
) -> None:
    """Start an interactive architecture-review chat session."""
    agent = _create_agent(model_override=model, project=project, resume_id=resume)

    console.print(
        Panel(
            "Special commands:\n"
            "  [bold]:decide <text>[/bold]  — log an architectural decision\n"
            "  [bold]:quit[/bold]           — save and exit",
            title="Ready",
            border_style="green",
        )
    )

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session saved.[/dim]")
            break

        if not user_input:
            continue

        if user_input.lower() == ":quit":
            console.print("[dim]Session saved.[/dim]")
            break

        if user_input.startswith(":decide "):
            decision = user_input[len(":decide ") :].strip()
            agent.log_decision(decision)
            continue

        response = agent.chat(user_input)
        console.print(f"\n[bold]Agent:[/bold] {response}\n")


@app.command("list-sessions")
def list_sessions_cmd(
    project: str | None = typer.Option(
        None,
        "--project",
        "-p",
        help="Only show sessions for this project.",
    ),
) -> None:
    """Show previously saved sessions."""
    from archagent.memory import list_sessions

    sessions = list_sessions(project)
    if not sessions:
        console.print("[dim]No saved sessions.[/dim]")
        return

    table = Table(title="Saved sessions", border_style="blue")
    table.add_column("ID", style="cyan")
    table.add_column("Project")
    table.add_column("Created", style="dim")
    table.add_column("Turns", justify="right")

    for s in sessions:
        table.add_row(s["id"], s["project"], s["created"], str(s["turns"]))

    console.print(table)


@app.command()
def resume(
    session_id: str = typer.Argument(..., help="Session ID to resume."),
    model: str = typer.Option(
        "",
        "--model",
        "-m",
        help="Override the default Claude model.",
    ),
) -> None:
    """Resume a previously saved session (shortcut for `chat --resume <id>`)."""
    chat(project="default", resume=session_id, model=model)


@app.command()
def info() -> None:
    """Show agent configuration and knowledge-base stats."""
    from archagent.config import Settings
    from archagent.rag import load_architecture_knowledge_base

    try:
        settings = Settings()
    except Exception as exc:
        err_console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(1) from exc

    try:
        kb = load_architecture_knowledge_base(settings.docs_path)
        kb_chunks = str(kb.total_chunks)
    except Exception as exc:
        kb_chunks = f"[red]error loading: {exc}[/red]"

    workspace_line = (
        str(settings.workspace)
        if settings.workspace is not None
        else "[dim]unset (write tools disabled)[/dim]"
    )

    console.print(
        Panel(
            f"[bold]Model:[/bold]      {settings.model}\n"
            f"[bold]Docs path:[/bold]  {settings.docs_path}\n"
            f"[bold]Log level:[/bold]  {settings.log_level}\n"
            f"[bold]Max tokens:[/bold] {settings.max_tokens}\n"
            f"[bold]Workspace:[/bold]  {workspace_line}\n"
            f"[bold]KB chunks:[/bold]  {kb_chunks}",
            title="archagent configuration",
            border_style="blue",
        )
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _create_agent(
    *,
    model_override: str = "",
    project: str = "default",
    resume_id: str | None = None,
) -> "ArchAgent":
    """Construct an ``ArchAgent`` with CLI overrides applied."""
    from archagent.agent import ArchAgent
    from archagent.config import Settings

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

    return ArchAgent(settings, project=project, resume_id=resume_id)


if __name__ == "__main__":
    app()
