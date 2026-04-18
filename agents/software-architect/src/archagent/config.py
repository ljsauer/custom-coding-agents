"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """ArchAgent configuration.

    All values can be set via environment variables prefixed with
    ``ARCHAGENT_`` or via a ``.env`` file in the working directory.  The
    only hard requirement is ``ANTHROPIC_API_KEY`` (no prefix so it can
    be shared across Anthropic-based tooling); ``AGENT_WORKSPACE`` keeps
    its historical name so existing ``.env`` files continue to work.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ARCHAGENT_",
        case_sensitive=False,
    )

    # Anthropic API key is read WITHOUT the ARCHAGENT_ prefix so the same
    # env var works for other Anthropic tooling.
    anthropic_api_key: str = Field(
        alias="ANTHROPIC_API_KEY",
        min_length=1,
        description="Anthropic API key for Claude access.",
    )

    model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096
    log_level: str = "INFO"

    # Path to the architecture docs consumed by the RAG index.  Defaults
    # to ``<repo>/docs/architecture`` discovered by walking up from this
    # file's location.
    docs_path: Path = (
        Path(__file__).resolve().parent.parent.parent.parent.parent
        / "docs"
        / "architecture"
    )

    # Opt-in workspace path that gates the write_file / edit_file tools.
    # Kept as AGENT_WORKSPACE (no prefix) so pre-existing .env files work.
    workspace: Path | None = Field(
        default=None,
        alias="AGENT_WORKSPACE",
        description=(
            "Directory the agent is allowed to write into.  Required for "
            "write_file / edit_file tools; they refuse otherwise."
        ),
    )
