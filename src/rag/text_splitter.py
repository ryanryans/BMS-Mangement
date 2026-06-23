"""Deterministic text chunking for the M2 local retriever."""

from __future__ import annotations

from dataclasses import dataclass

from src.rag.document_loader import LoadedDocument


@dataclass(frozen=True)
class TextChunk:
    text: str
    source: str
    chunk_id: str
    metadata: dict[str, str | int]


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        return []
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    overlap = max(0, min(chunk_overlap, chunk_size - 1))
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + chunk_size)
        chunks.append(clean[start:end])
        if end == len(clean):
            break
        start = end - overlap
    return chunks


def split_documents(
    documents: list[LoadedDocument],
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for document_index, document in enumerate(documents):
        for chunk_index, chunk_text in enumerate(
            split_text(document.content, chunk_size, chunk_overlap)
        ):
            metadata = dict(document.metadata)
            metadata["chunk_index"] = chunk_index
            metadata["document_index"] = document_index
            chunks.append(
                TextChunk(
                    text=chunk_text,
                    source=document.source,
                    chunk_id=f"doc{document_index}-chunk{chunk_index}",
                    metadata=metadata,
                )
            )
    return chunks

