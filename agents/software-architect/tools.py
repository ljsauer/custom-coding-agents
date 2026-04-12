from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()


def _check_write_allowed(path: str) -> str | None:
    """Returns an error string if the write should be blocked, None if safe."""
    load_dotenv(override=True)
    allowed_write_root = os.environ.get("AGENT_WORKSPACE", None)
    if allowed_write_root is None:
        return "Write tools are disabled. Set AGENT_WORKSPACE in .env to enable."
    resolved = Path(path).resolve()
    workspace = Path(allowed_write_root).resolve()
    if not str(resolved).startswith(str(workspace)):
        return f"Write blocked: {resolved} is outside workspace {workspace}."
    return None


TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Read the contents of a source file for architectural review.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file."}
            },
            "required": ["path"],
        },
    },
    {
        "name": "describe_project_structure",
        "description": (
            "List the directory tree of a project to understand its layer "
            "structure before reading individual files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "root": {"type": "string"},
                "max_depth": {"type": "integer", "default": 4},
            },
            "required": ["root"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write content to a file. Only available within the configured workspace. "
            "Use for creating new files or replacing file contents entirely."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": (
            "Replace a specific string in a file with new content. "
            "old_str must match exactly and appear exactly once."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_str": {"type": "string"},
                "new_str": {"type": "string"},
            },
            "required": ["path", "old_str", "new_str"],
        },
    },
]


def execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "read_file":
        try:
            return Path(tool_input["path"]).read_text()
        except FileNotFoundError:
            return f"Error: file not found at {tool_input['path']}"

    if tool_name == "describe_project_structure":
        return _describe_structure(tool_input["root"], tool_input.get("max_depth", 4))

    if tool_name in ("write_file", "edit_file"):
        error = _check_write_allowed(tool_input["path"])
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
