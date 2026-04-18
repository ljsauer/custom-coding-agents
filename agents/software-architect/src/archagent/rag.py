"""Embedding-based retrieval over the architecture documentation.

Wraps the sentence-transformers index in an :class:`ArchitectureKnowledgeBase`
with the same API shape as pyagent's :class:`~pyagent.rag.KnowledgeBase` so
the two agents are ergonomically interchangeable.  The embedding model
(``all-MiniLM-L6-v2``) is loaded lazily on first use.
"""

import logging as stdlib_logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from archagent.logging import get_logger

logger = get_logger(__name__)

# Silence noisy third-party loggers once at import time.
stdlib_logging.getLogger("sentence_transformers").setLevel(stdlib_logging.ERROR)
stdlib_logging.getLogger("huggingface_hub").setLevel(stdlib_logging.ERROR)

_model: SentenceTransformer | None = None

_HEADING_RE = re.compile(r"(?=^#{1,4} .+$)", re.MULTILINE)


def _get_model() -> SentenceTransformer:
    """Lazily construct the embedding model (shared across calls)."""
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


@dataclass
class ArchitectureKnowledgeBase:
    """Indexed architecture documentation with embedding-based retrieval.

    Attributes:
        chunks: Per-section chunks; each has ``heading``, ``text``, ``source``.
        embeddings: ``(num_chunks, embed_dim)`` matrix aligned with ``chunks``.
    """

    chunks: list[dict] = field(default_factory=list)
    embeddings: np.ndarray | None = None

    @property
    def total_chunks(self) -> int:
        """Return the number of indexed chunks."""
        return len(self.chunks)

    def retrieve(self, query: str, *, top_k: int = 3) -> list[dict]:
        """Return the ``top_k`` chunks most similar to ``query``.

        Args:
            query: Natural-language search query.
            top_k: Maximum number of chunks to return.

        Raises:
            ValueError: If the query is empty or the index is empty.
        """
        if not query.strip():
            raise ValueError("Query is empty.")
        if not self.chunks or self.embeddings is None:
            raise ValueError(
                "Knowledge base is empty — was load_architecture_knowledge_base called?"
            )

        model = _get_model()
        query_vec = model.encode([query], convert_to_numpy=True)

        if query_vec.shape[-1] != self.embeddings.shape[-1]:
            raise ValueError(
                f"Embedding dimension mismatch: query={query_vec.shape}, "
                f"index={self.embeddings.shape}. Rebuild the index."
            )

        scores = (self.embeddings @ query_vec.T).squeeze()
        k = min(top_k, len(self.chunks))
        top_indices = np.argsort(scores)[::-1][:k]
        return [self.chunks[i] for i in top_indices]

    def retrieve_formatted(self, query: str, *, top_k: int = 3) -> str:
        """Retrieve chunks and format them as a single context string."""
        retrieved = self.retrieve(query, top_k=top_k)
        if not retrieved:
            return ""
        sections = "\n\n---\n".join(
            f"[{c['source']} > {c['heading']}]\n{c['text']}" for c in retrieved
        )
        return f"\n\n## Reference Material\n{sections}"


def load_architecture_knowledge_base(docs_path: Path) -> ArchitectureKnowledgeBase:
    """Index every ``.md`` file under ``docs_path`` into an embedding-based KB.

    Args:
        docs_path: Directory containing the architecture markdown files.

    Returns:
        A populated :class:`ArchitectureKnowledgeBase`.

    Raises:
        FileNotFoundError: If ``docs_path`` does not exist.
        ValueError: If no chunks could be produced from the docs.
    """
    if not docs_path.exists():
        raise FileNotFoundError(f"Docs directory not found: {docs_path}")

    all_chunks: list[dict] = []
    for md_file in sorted(docs_path.glob("*.md")):
        file_chunks = _chunk_by_section(md_file)
        for chunk in file_chunks:
            chunk["source"] = md_file.stem
        all_chunks.extend(file_chunks)
        logger.debug("Indexed %d chunks from %s", len(file_chunks), md_file.name)

    if not all_chunks:
        raise ValueError(
            f"No chunks produced from {docs_path}. Check file paths and content."
        )

    model = _get_model()
    texts = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts, convert_to_numpy=True)

    logger.info(
        "Knowledge base loaded: %d chunks from %s (embedding shape %s)",
        len(all_chunks),
        docs_path,
        embeddings.shape,
    )
    return ArchitectureKnowledgeBase(chunks=all_chunks, embeddings=embeddings)


def _chunk_by_section(filepath: Path) -> list[dict]:
    """Split a markdown file at ``#``-``####`` heading boundaries."""
    text = filepath.read_text()
    raw_chunks = _HEADING_RE.split(text)

    chunks: list[dict] = []
    for chunk in raw_chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        first_line = chunk.splitlines()[0] if chunk.splitlines() else ""
        heading = first_line.lstrip("#").strip()
        chunks.append({"heading": heading, "text": chunk})
    return chunks
