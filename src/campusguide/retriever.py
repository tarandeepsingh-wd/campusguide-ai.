from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .storage import StoredChunk


TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "for",
    "from",
    "has",
    "have",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "with",
}


@dataclass(frozen=True)
class RetrievalResult:
    chunk: StoredChunk
    score: float


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw_token in TOKEN_PATTERN.findall(text):
        token = _normalize_token(raw_token)
        if token not in STOPWORDS and len(token) > 1:
            tokens.append(token)
    return tokens


def _normalize_token(token: str) -> str:
    token = token.lower()
    if token.startswith("intern"):
        return "internship"
    if token in {"credit", "credits"}:
        return "credit"
    if token in {"require", "required", "requires", "requirement", "requirements"}:
        return "require"
    if token in {"eligible", "eligibility"}:
        return "eligible"
    if token.startswith("graduat"):
        return "graduation"
    if token in {"student", "students"}:
        return "student"
    if token.endswith("s") and len(token) > 4:
        return token[:-1]
    return token


class TfIdfRetriever:
    """Small transparent vector retriever for the MVP.

    This intentionally avoids a hosted embedding service so the project works
    offline. The README explains how to replace this with pgvector/Chroma later.
    """

    def __init__(self, chunks: list[StoredChunk]):
        self.chunks = chunks
        self.idf: dict[str, float] = {}
        self.chunk_vectors: list[dict[str, float]] = []
        self._fit()

    def _fit(self) -> None:
        document_frequency: dict[str, int] = {}
        tokenized_chunks: list[list[str]] = []

        for chunk in self.chunks:
            tokens = tokenize(chunk.text)
            tokenized_chunks.append(tokens)
            for token in set(tokens):
                document_frequency[token] = document_frequency.get(token, 0) + 1

        total_chunks = max(len(self.chunks), 1)
        self.idf = {
            token: math.log((1 + total_chunks) / (1 + frequency)) + 1
            for token, frequency in document_frequency.items()
        }

        self.chunk_vectors = [
            self._normalize(self._tfidf(tokens)) for tokens in tokenized_chunks
        ]

    def _tfidf(self, tokens: list[str]) -> dict[str, float]:
        if not tokens:
            return {}
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1

        token_count = len(tokens)
        return {
            token: (count / token_count) * self.idf.get(token, 0.0)
            for token, count in counts.items()
        }

    @staticmethod
    def _normalize(vector: dict[str, float]) -> dict[str, float]:
        norm = math.sqrt(sum(value * value for value in vector.values()))
        if norm == 0:
            return vector
        return {token: value / norm for token, value in vector.items()}

    @staticmethod
    def _dot(left: dict[str, float], right: dict[str, float]) -> float:
        if len(left) > len(right):
            left, right = right, left
        return sum(value * right.get(token, 0.0) for token, value in left.items())

    def search(self, query: str, top_k: int = 3) -> list[RetrievalResult]:
        query_vector = self._normalize(self._tfidf(tokenize(query)))
        scored = [
            RetrievalResult(chunk=chunk, score=self._dot(query_vector, vector))
            for chunk, vector in zip(self.chunks, self.chunk_vectors)
        ]
        scored.sort(key=lambda result: result.score, reverse=True)
        return [result for result in scored[:top_k] if result.score > 0]
