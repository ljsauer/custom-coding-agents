from pathlib import Path


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
]


def execute_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "read_file":
        try:
            return Path(tool_input["path"]).read_text()
        except FileNotFoundError:
            return f"Error: file not found at {tool_input['path']}"

    if tool_name == "describe_project_structure":
        return _describe_structure(tool_input["root"], tool_input.get("max_depth", 4))

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
