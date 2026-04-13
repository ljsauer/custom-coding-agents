"""Conversation and session state management.

Tracks the message history for a single agent session so multi-turn
interactions maintain context.  Provides helpers to manage the conversation
window and serialize state for the LLM.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from pyagent.logging import get_logger

logger = get_logger(__name__)


class Role(StrEnum):
    """Message roles in the conversation."""

    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class Message:
    """A single message in the conversation history."""

    role: Role
    content: str

    def to_api_dict(self) -> dict[str, str]:
        """Convert to the dict format expected by the Anthropic API."""
        return {"role": self.role.value, "content": self.content}


@dataclass
class ConversationMemory:
    """Manages the message history for an agent session.

    Keeps a rolling window of messages and provides serialization for
    API calls.  The system prompt is stored separately and always
    included at the top of every request.
    """

    system_prompt: str = ""
    messages: list[Message] = field(default_factory=list)
    max_messages: int = 50

    def add_user_message(self, content: str) -> None:
        """Record a user message.

        Args:
            content: The user's input text.
        """
        self._add(Message(role=Role.USER, content=content))

    def add_assistant_message(self, content: str) -> None:
        """Record an assistant response.

        Args:
            content: The assistant's response text.
        """
        self._add(Message(role=Role.ASSISTANT, content=content))

    def to_api_messages(self) -> list[dict[str, str]]:
        """Return the message history in Anthropic API format.

        Returns:
            A list of ``{"role": ..., "content": ...}`` dicts.
        """
        return [m.to_api_dict() for m in self.messages]

    def clear(self) -> None:
        """Reset the conversation history."""
        self.messages.clear()
        logger.debug("Conversation memory cleared")

    @property
    def turn_count(self) -> int:
        """Return the number of turns (user messages) in history."""
        return sum(1 for m in self.messages if m.role == Role.USER)

    def _add(self, message: Message) -> None:
        """Append a message and trim if over the window limit."""
        self.messages.append(message)
        if len(self.messages) > self.max_messages:
            trimmed = len(self.messages) - self.max_messages
            self.messages = self.messages[trimmed:]
            logger.debug("Trimmed %d messages from conversation history", trimmed)
