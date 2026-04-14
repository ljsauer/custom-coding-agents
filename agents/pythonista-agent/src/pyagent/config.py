"""Application configuration loaded from environment variables."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """PyAgent configuration.

    All values can be set via environment variables prefixed with ``PYAGENT_``
    or via a ``.env`` file in the working directory.  The only hard requirement
    is ``ANTHROPIC_API_KEY``, which has no prefix so it can be shared across
    Anthropic-based tools.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PYAGENT_",
        case_sensitive=False,
    )

    # Anthropic API key is read WITHOUT the PYAGENT_ prefix so the same
    # env var works for other Anthropic tooling.
    anthropic_api_key: str = Field(
        alias="ANTHROPIC_API_KEY",
        min_length=1,
        description="Anthropic API key for Claude access.",
    )

    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    batch_max_tokens: int = 16384
    context_token_budget: int = 30_000
    log_level: str = "INFO"

    # Path to the docs/ directory used for RAG retrieval.
    docs_path: Path = (
        Path(__file__).resolve().parent.parent.parent.parent.parent / "docs"
    )
