"""Local document loading for M2 RAG tests and API status."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LoadedDocument:
    content: str
    source: str
    metadata: dict[str, str | int]


def list_knowledge_files(
    data_path: Path,
    allowed_extensions: tuple[str, ...] = ("txt",),
) -> list[Path]:
    if not data_path.exists() or not data_path.is_dir():
        return []
    normalized = {ext.lower().lstrip(".") for ext in allowed_extensions}
    return sorted(
        path
        for path in data_path.iterdir()
        if path.is_file() and path.suffix.lower().lstrip(".") in normalized
    )


def load_text_documents(
    data_path: Path,
    allowed_extensions: tuple[str, ...] = ("txt",),
) -> list[LoadedDocument]:
    documents: list[LoadedDocument] = []
    for path in list_knowledge_files(data_path, allowed_extensions):
        if path.suffix.lower() != ".txt":
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        if not content.strip():
            continue
        documents.append(
            LoadedDocument(
                content=content,
                source=str(path),
                metadata={
                    "filename": path.name,
                    "extension": path.suffix.lower(),
                    "size_bytes": path.stat().st_size,
                },
            )
        )
    return documents

