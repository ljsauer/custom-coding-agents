from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from prompts import SYSTEM_PROMPT
from rag import build_index, retrieve, build_context_block
from memory import (
    new_session,
    save_session,
    load_session,
    log_decision,
    get_project_decisions,
    build_decision_block,
)
from tools import TOOL_DEFINITIONS, execute_tool

load_dotenv()


class ArchAgent:
    def __init__(self, project: str = "default", resume_id: str | None = None):
        self.client = Anthropic()

        # Load relevant documentation into index
        doc_files = [
            "docs/architecture/design_influences.md",
            "docs/architecture/foundational_patterns.md",
            "docs/architecture/general_rules.md",
        ]
        for f in doc_files:
            if not Path(f).exists():
                raise FileNotFoundError(
                    f"Documentation file not found: {Path(f).resolve()}"
                )

        self.chunks, self.embeddings = build_index(doc_files)

        if resume_id:
            self.session = load_session(resume_id)
            print(
                f"Resumed session {resume_id} ({len(self.session['history']) // 2} prior turns)"
            )
        else:
            self.session = new_session(project)
            print(f"New session — project: {project}")

        self.prior_decisions = get_project_decisions(project)

    def _build_system(self, query: str) -> str:
        relevant = retrieve(query, self.chunks, self.embeddings)
        context = build_context_block(relevant)
        decisions = build_decision_block(self.prior_decisions)
        return SYSTEM_PROMPT + decisions + context

    def _run_turn(self, user_input: str) -> str:
        self.session["history"].append({"role": "user", "content": user_input})

        while True:
            response = self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=self._build_system(user_input),
                tools=TOOL_DEFINITIONS,
                messages=self.session["history"],
            )

            # Serialize before storing — SDK objects are not JSON-safe
            serialized_content = _serialize_content(response.content)

            self.session["history"].append(
                {"role": "assistant", "content": serialized_content}
            )

            if response.stop_reason != "tool_use":
                for block in serialized_content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block["text"]

            tool_results = []
            for block in serialized_content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    result = execute_tool(block["name"], block["input"])
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block["id"],
                            "content": result,
                        }
                    )

            self.session["history"].append({"role": "user", "content": tool_results})

    def chat(self, user_input: str) -> str:
        response = self._run_turn(user_input)
        save_session(self.session)
        return response

    def log_decision(self, decision: str) -> None:
        log_decision(self.session, decision)
        self.prior_decisions.append({"timestamp": "", "decision": decision})
        save_session(self.session)
        print(f"Decision logged: {decision}")


def _serialize_content(content) -> list[dict] | str:
    """Convert SDK response content blocks to JSON-serializable dicts."""
    if isinstance(content, str):
        return content

    result = []
    for block in content:
        if hasattr(block, "type"):
            if block.type == "text":
                result.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                result.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
            elif block.type == "tool_result":
                result.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.tool_use_id,
                        "content": block.content,
                    }
                )
            else:
                # Fallback for any other block types
                result.append({"type": block.type, "raw": str(block)})
        else:
            result.append(block)

    return result
