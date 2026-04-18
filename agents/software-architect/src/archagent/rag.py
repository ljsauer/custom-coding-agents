"""RAG index + retrieval over architecture documentation."""

import logging
import re
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

# Keep third-party libraries quiet.
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def chunk_by_section(filepath: str) -> list[dict]:
    text = Path(filepath).read_text()
    pattern = re.compile(r"(?=^#{1,4} .+$)", re.MULTILINE)
    raw_chunks = pattern.split(text)

    chunks = []
    for chunk in raw_chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        first_line = chunk.splitlines()[0] if chunk.splitlines() else ""
        heading = first_line.lstrip("#").strip()
        chunks.append({"heading": heading, "text": chunk})

    return chunks


def build_index(filepaths: list[str]) -> tuple[list[dict], np.ndarray]:
    model = get_model()
    all_chunks = []

    for filepath in filepaths:
        print(f"Building index for {filepath}")
        chunks = chunk_by_section(filepath)
        for chunk in chunks:
            chunk["source"] = Path(filepath).stem
        all_chunks.extend(chunks)

    if not all_chunks:
        raise ValueError(
            f"No chunks produced from {filepaths}. Check file paths and content."
        )

    texts = [c["text"] for c in all_chunks]
    embeddings = model.encode(texts, convert_to_numpy=True)

    print(f"Index built: {len(all_chunks)} chunks, embedding shape {embeddings.shape}")
    return all_chunks, embeddings


def retrieve(
    query: str, chunks: list[dict], embeddings: np.ndarray, top_k: int = 3
) -> list[dict]:
    if not query.strip():
        raise ValueError("Query is empty.")
    if len(chunks) == 0:
        raise ValueError("Chunk index is empty — was build_index called?")

    model = get_model()
    query_vec = model.encode([query], convert_to_numpy=True)

    # Shape guard — catches the mismatch before numpy does
    if query_vec.shape[-1] != embeddings.shape[-1]:
        raise ValueError(
            f"Embedding dimension mismatch: query={query_vec.shape}, "
            f"index={embeddings.shape}. Rebuild the index."
        )

    scores = (embeddings @ query_vec.T).squeeze()
    top_k = min(top_k, len(chunks))
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [chunks[i] for i in top_indices]


def build_context_block(retrieved_chunks: list[dict]) -> str:
    sections = "\n\n---\n".join(
        f"[{c['source']} → {c['heading']}]\n{c['text']}" for c in retrieved_chunks
    )
    return f"\n\n## Reference Material\n{sections}"
