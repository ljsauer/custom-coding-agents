"""Retrieval-augmented generation over the standards documentation.

This module provides a simple, dependency-light RAG implementation that splits
the markdown docs into sections and retrieves relevant chunks based on keyword
matching.  It is intentionally minimal — no vector database, no embeddings.
For a local CLI agent operating over a small, known corpus of six documents,
keyword retrieval with section-level granularity is sufficient and keeps the
dependency footprint near zero.

If retrieval quality becomes a bottleneck, this module is the single place to
swap in a vector store or embedding-based approach.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from pyagent.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class DocChunk:
    """A retrievable section of a standards document."""

    source: str
    heading: str
    content: str
    level: int

    @property
    def token_estimate(self) -> int:
        """Rough token count (~4 chars per token)."""
        return len(self.content) // 4


@dataclass
class KnowledgeBase:
    """Indexed collection of documentation chunks."""

    chunks: list[DocChunk]

    @property
    def total_chunks(self) -> int:
        """Return the number of indexed chunks."""
        return len(self.chunks)

    def retrieve(
        self,
        query: str,
        *,
        max_chunks: int = 10,
        max_tokens: int = 3000,
        sources: list[str] | None = None,
    ) -> list[DocChunk]:
        """Retrieve the most relevant chunks for a query.

        Uses simple keyword scoring: each query term that appears in the
        chunk's heading or content contributes to the score, with heading
        matches weighted higher.

        Args:
            query: The search query (natural language or keywords).
            max_chunks: Maximum number of chunks to return.
            max_tokens: Approximate token budget for retrieved context.
            sources: Optional list of source filenames to restrict search to.

        Returns:
            A list of ``DocChunk`` objects ranked by relevance.
        """
        terms = _tokenize_query(query)
        if not terms:
            return []

        scored: list[tuple[float, DocChunk]] = []
        for chunk in self.chunks:
            if sources and chunk.source not in sources:
                continue
            score = _score_chunk(chunk, terms)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda pair: pair[0], reverse=True)

        results: list[DocChunk] = []
        token_budget = max_tokens
        for _score, chunk in scored[:max_chunks]:
            if chunk.token_estimate > token_budget:
                continue
            results.append(chunk)
            token_budget -= chunk.token_estimate

        logger.debug(
            "Retrieved %d chunks for query '%s' (%d tokens used)",
            len(results),
            query[:50],
            max_tokens - token_budget,
        )
        return results

    def retrieve_formatted(
        self,
        query: str,
        *,
        max_chunks: int = 10,
        max_tokens: int = 3000,
        sources: list[str] | None = None,
    ) -> str:
        """Retrieve and format chunks as a single context string.

        Args:
            query: The search query.
            max_chunks: Maximum number of chunks to return.
            max_tokens: Approximate token budget.
            sources: Optional source filename filter.

        Returns:
            A formatted string suitable for inclusion in an LLM prompt.
        """
        chunks = self.retrieve(
            query,
            max_chunks=max_chunks,
            max_tokens=max_tokens,
            sources=sources,
        )
        if not chunks:
            return ""

        sections: list[str] = []
        for chunk in chunks:
            sections.append(f"[{chunk.source} > {chunk.heading}]\n{chunk.content}")
        return "\n\n---\n\n".join(sections)


def load_knowledge_base(docs_path: Path) -> KnowledgeBase:
    """Load and index all Markdown files in the docs directory.

    Args:
        docs_path: Path to the directory containing ``.md`` files.

    Returns:
        A ``KnowledgeBase`` ready for retrieval.

    Raises:
        FileNotFoundError: If ``docs_path`` does not exist.
    """
    if not docs_path.exists():
        raise FileNotFoundError(f"Docs directory not found: {docs_path}")

    chunks: list[DocChunk] = []
    for md_file in sorted(docs_path.glob("*.md")):
        file_chunks = _split_markdown(md_file)
        chunks.extend(file_chunks)
        logger.debug("Indexed %d chunks from %s", len(file_chunks), md_file.name)

    kb = KnowledgeBase(chunks=chunks)
    logger.info("Knowledge base loaded: %d chunks from %s", kb.total_chunks, docs_path)
    return kb


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
_WORD_RE = re.compile(r"[a-z_][a-z0-9_]*", re.IGNORECASE)


def _split_markdown(path: Path) -> list[DocChunk]:
    """Split a markdown file into chunks at heading boundaries."""
    content = path.read_text(encoding="utf-8")
    source = path.stem

    matches = list(_HEADING_RE.finditer(content))
    if not matches:
        return [
            DocChunk(
                source=source,
                heading=source,
                content=content.strip(),
                level=0,
            )
        ]

    chunks: list[DocChunk] = []

    # Content before the first heading (if any).
    preamble = content[: matches[0].start()].strip()
    if preamble:
        chunks.append(
            DocChunk(source=source, heading="Introduction", content=preamble, level=0)
        )

    for i, match in enumerate(matches):
        level = len(match.group(1))
        heading = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[start:end].strip()

        if body:
            chunks.append(
                DocChunk(source=source, heading=heading, content=body, level=level)
            )

    return chunks


def _tokenize_query(query: str) -> list[str]:
    """Extract lowercase keyword tokens from a query string."""
    stopwords = {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "shall",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "i",
        "you",
        "he",
        "she",
        "we",
        "they",
        "my",
        "your",
        "his",
        "her",
        "our",
        "their",
        "what",
        "which",
        "who",
        "whom",
        "how",
        "when",
        "where",
        "why",
        "and",
        "or",
        "but",
        "not",
        "no",
        "if",
        "then",
        "than",
        "so",
        "for",
        "with",
        "from",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "about",
        "into",
        "through",
        "during",
        "before",
        "after",
    }
    words = _WORD_RE.findall(query.lower())
    return [w for w in words if w not in stopwords]


def _score_chunk(chunk: DocChunk, terms: list[str]) -> float:
    """Score a chunk against query terms.

    Heading matches are weighted 3x over body matches.
    """
    heading_lower = chunk.heading.lower()
    content_lower = chunk.content.lower()

    score = 0.0
    for term in terms:
        if term in heading_lower:
            score += 3.0
        if term in content_lower:
            score += 1.0

    return score
