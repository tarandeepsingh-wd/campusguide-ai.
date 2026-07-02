from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    document_name: str
    page_number: int
    chunk_index: int
    text: str


def split_into_chunks(
    document_name: str,
    page_number: int,
    text: str,
    chunk_size: int = 120,
    overlap: int = 25,
) -> list[TextChunk]:
    """Split page text into overlapping word chunks."""
    words = text.split()
    if not words:
        return []

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[TextChunk] = []
    step = chunk_size - overlap
    for chunk_index, start in enumerate(range(0, len(words), step)):
        chunk_words = words[start : start + chunk_size]
        chunk_text = " ".join(chunk_words).strip()
        if chunk_text:
            chunks.append(
                TextChunk(
                    document_name=document_name,
                    page_number=page_number,
                    chunk_index=chunk_index,
                    text=chunk_text,
                )
            )
        if start + chunk_size >= len(words):
            break
    return chunks
