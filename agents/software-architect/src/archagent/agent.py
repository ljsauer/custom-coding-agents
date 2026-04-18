"""Core archagent orchestration.

Wires together the Anthropic client, the architecture knowledge base,
the session memory, and the tool dispatcher into a conversational agent.
"""

from anthropic import Anthropic

from archagent.config import Settings
from archagent.logging import get_logger
from archagent.memory import (
    build_decision_block,
    get_project_decisions,
    load_session,
    log_decision,
    new_session,
    save_session,
)
from archagent.prompts import SYSTEM_PROMPT
from archagent.rag import (
    ArchitectureKnowledgeBase,
    load_architecture_knowledge_base,
)
from archagent.tools import TOOL_DEFINITIONS, execute_tool

logger = get_logger(__name__)


class ArchAgent:
    """The archagent orchestrator."""

    def __init__(
        self,
        settings: Settings,
        *,
        project: str = "default",
        resume_id: str | None = None,
    ) -> None:
        self._settings = settings
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self._kb: ArchitectureKnowledgeBase = load_architecture_knowledge_base(
            settings.docs_path
        )

        if resume_id:
            self.session = load_session(resume_id)
            print(
                f"Resumed session {resume_id} "
                f"({len(self.session['history']) // 2} prior turns)"
            )
        else:
            self.session = new_session(project)
            print(f"New session — project: {project}")

        self.prior_decisions = get_project_decisions(project)

    @property
    def knowledge_base(self) -> ArchitectureKnowledgeBase:
        """The loaded architecture knowledge base."""
        return self._kb

    def _build_system(self, query: str) -> str:
        context = self._kb.retrieve_formatted(query)
        decisions = build_decision_block(self.prior_decisions)
        return SYSTEM_PROMPT + decisions + context

    def _run_turn(self, user_input: str) -> str:
        self.session["history"].append({"role": "user", "content": user_input})

        while True:
            response = self.client.messages.create(
                model=self._settings.model,
                max_tokens=self._settings.max_tokens,
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
                    result = execute_tool(
                        block["name"],
                        block["input"],
                        workspace=self._settings.workspace,
                    )
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
