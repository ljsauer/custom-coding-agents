"""JSON schemas for the Anthropic tool-use API.

These are passed to ``client.messages.create(tools=TOOL_DEFINITIONS, ...)``.
The actual implementations live in :mod:`archagent.tools.executor`.
"""

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
            "Write content to a file. Only available within the configured "
            "workspace.  Use for creating new files or replacing file "
            "contents entirely."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
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
