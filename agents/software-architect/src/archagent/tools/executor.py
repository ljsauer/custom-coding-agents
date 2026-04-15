"""Dispatcher for Anthropic tool-use calls emitted by archagent."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _resolve_workspace(workspace: Path | None) -> Path | None:
    """Resolve the write-allowed workspace.

    Prefers the explicit argument (typically passed from ``Settings``),
    falling back to the ``AGENT_WORKSPACE`` env var so callers that don't
    have a Settings instance still work.
    """
    if workspace is not None:
        return workspace
    env_value = os.environ.get("AGENT_WORKSPACE")
    return Path(env_value) if env_value else None


def _check_write_allowed(path: str, workspace: Path | None) -> str | None:
    """Returns an error string if the write should be blocked, None if safe."""
    resolved_workspace = _resolve_workspace(workspace)
    if resolved_workspace is None:
        return "Write tools are disabled. Set AGENT_WORKSPACE in .env to enable."
    resolved = Path(path).resolve()
    ws = resolved_workspace.resolve()
    if not str(resolved).startswith(str(ws)):
        return f"Write blocked: {resolved} is outside workspace {ws}."
    return None


def execute_tool(
    tool_name: str,
    tool_input: dict,
    *,
    workspace: Path | None = None,
) -> str:
    """Dispatch a single Anthropic tool-use call.

    Args:
        tool_name: Name of the tool the model invoked.
        tool_input: Parsed JSON input for the tool call.
        workspace: Optional write-allowed workspace.  When ``None``,
            falls back to the ``AGENT_WORKSPACE`` env var.

    Returns:
        The tool's result text, suitable for returning to the model as a
        ``tool_result`` content block.
    """
    if tool_name == "read_file":
        try:
            return Path(tool_input["path"]).read_text()
        except FileNotFoundError:
            return f"Error: file not found at {tool_input['path']}"

    if tool_name == "describe_project_structure":
        return _describe_structure(tool_input["root"], tool_input.get("max_depth", 4))

    if tool_name in ("write_file", "edit_file"):
        error = _check_write_allowed(tool_input["path"], workspace)
        if error:
            return error
        print(f"\n[AGENT WANTS TO WRITE] {tool_input['path']}")
        print("---")
        print(tool_input.get("content") or tool_input.get("new_str"))
        print("---")
        confirm = input("Apply this change? [y/N]: ").strip().lower()
        if confirm != "y":
            return "Write cancelled by user."

        target = Path(tool_input["path"])

        if tool_name == "write_file":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(tool_input["content"])
            return f"Written: {target}"

        if tool_name == "edit_file":
            if not target.exists():
                return f"Error: file not found at {target}"
            original = target.read_text()
            old_str = tool_input["old_str"]
            new_str = tool_input["new_str"]
            if original.count(old_str) == 0:
                return f"Error: old_str not found in {target}"
            if original.count(old_str) > 1:
                return f"Error: old_str appears more than once in {target}"
            target.write_text(original.replace(old_str, new_str, 1))
            return f"Edited: {target}"

    return f"Unknown tool: {tool_name}"


def _describe_structure(root: str, max_depth: int) -> str:
    lines = []
    root_path = Path(root)

    def walk(path: Path, depth: int, prefix: str = "") -> None:
        if depth > max_depth:
            return
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
        for i, entry in enumerate(entries):
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            if entry.is_dir() and not entry.name.startswith("."):
                ext = "    " if i == len(entries) - 1 else "│   "
                walk(entry, depth + 1, prefix + ext)

    lines.append(str(root_path))
    walk(root_path, 1)
    return "\n".join(lines)
