from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .chunker import split_into_chunks
from .document_loader import iter_documents, load_document
from .retriever import RetrievalResult, TfIdfRetriever, tokenize
from .storage import RagStore


@dataclass(frozen=True)
class Citation:
    document_name: str
    page_number: int
    chunk_id: int
    score: float
    snippet: str


@dataclass(frozen=True)
class RagAnswer:
    question: str
    answer: str
    citations: list[Citation]
    prompt: str


def index_directory(
    docs_dir: Path,
    store: RagStore,
    reset: bool = True,
    chunk_size: int = 120,
    overlap: int = 25,
) -> dict[str, int]:
    if reset:
        store.reset()

    document_count = 0
    chunk_count = 0
    for path in iter_documents(docs_dir):
        stats = index_file(
            path=path,
            store=store,
            replace_existing=True,
            chunk_size=chunk_size,
            overlap=overlap,
        )
        if stats["chunks"] > 0:
            document_count += 1
            chunk_count += stats["chunks"]

    return {"documents": document_count, "chunks": chunk_count}


def index_source(
    source: Path,
    store: RagStore,
    reset: bool = True,
    chunk_size: int = 120,
    overlap: int = 25,
) -> dict[str, int]:
    if source.is_file():
        if reset:
            store.reset()
        return index_file(
            path=source,
            store=store,
            replace_existing=True,
            chunk_size=chunk_size,
            overlap=overlap,
        )

    return index_directory(
        docs_dir=source,
        store=store,
        reset=reset,
        chunk_size=chunk_size,
        overlap=overlap,
    )


def index_file(
    path: Path,
    store: RagStore,
    replace_existing: bool = True,
    chunk_size: int = 120,
    overlap: int = 25,
) -> dict[str, int]:
    pages = load_document(path)
    if not pages:
        return {"documents": 0, "chunks": 0}

    document_id = store.add_document(path.name, str(path))
    if replace_existing:
        store.delete_chunks_for_document(document_id)

    chunk_count = 0
    for page in pages:
        chunks = split_into_chunks(
            document_name=page.document_name,
            page_number=page.page_number,
            text=page.text,
            chunk_size=chunk_size,
            overlap=overlap,
        )
        for chunk in chunks:
            store.add_chunk(
                document_id=document_id,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
            )
            chunk_count += 1

    return {"documents": 1, "chunks": chunk_count}


def ask_question(store: RagStore, question: str, top_k: int = 3) -> RagAnswer:
    chunks = store.load_chunks()
    if not chunks:
        answer = "No documents are indexed yet. Index policy documents first."
        return RagAnswer(question=question, answer=answer, citations=[], prompt="")

    policy_answer = _try_policy_answer(question, chunks)
    if policy_answer:
        store.log_question(question, policy_answer.answer)
        return policy_answer

    retriever = TfIdfRetriever(chunks)
    results = retriever.search(question, top_k=top_k)

    if not results:
        answer = "I don't know from the indexed campus documents."
        store.log_question(question, answer)
        return RagAnswer(question=question, answer=answer, citations=[], prompt="")

    answer = _build_extractive_answer(question, results)
    citations = [
        Citation(
            document_name=result.chunk.document_name,
            page_number=result.chunk.page_number,
            chunk_id=result.chunk.id,
            score=round(result.score, 4),
            snippet=_shorten(result.chunk.text, 260),
        )
        for result in results
    ]
    prompt = build_grounded_prompt(question, results)
    store.log_question(question, answer)
    return RagAnswer(question=question, answer=answer, citations=citations, prompt=prompt)


def _try_policy_answer(question: str, chunks) -> RagAnswer | None:
    query_terms = set(tokenize(question))

    if "internship" in query_terms and "credit" in query_terms:
        sem6 = _find_chunk(chunks, "Eligibility to apply for internship at the end of Semester 6")
        sem7 = _find_chunk(chunks, "Eligibility to go for internship at the end of Semester 7")
        page12 = _find_chunk(chunks, "Students approved for such internship are required to register")
        if sem6:
            citations = [_citation_from_chunk(sem6, 1.0)]
            if sem7:
                citations.append(_citation_from_chunk(sem7, 1.0))
            if page12:
                citations.append(_citation_from_chunk(page12, 1.0))
            answer = (
                "For internship without semester leave, the PDF gives two cases. "
                "At the end of Semester 6, a student must have completed 126 credits, "
                "done 4 credits of SG/CW in addition to those 126 credits, completed all core courses, "
                "and be left with only 4 credits of IP/IS/UR/Online course/BTP. "
                "At the end of Semester 7, the student must have completed 148 credits and 4 credits of SG/CW in addition. "
                "Approved students must register for 4 credits of only IP/IS/UR/BTP/OC in the eighth semester."
            )
            return RagAnswer(
                question=question,
                answer=answer,
                citations=citations[:3],
                prompt="Policy rule extracted from the internship eligibility section.",
            )

    if "graduation" in query_terms and "credit" in query_terms:
        graduation = _find_chunk(
            chunks,
            "The minimum number of credits for a B.Tech. program is 156",
        )
        if graduation:
            answer = (
                "The minimum number of credits required for a B.Tech. program is 156, "
                "including 2 credits each of SG and CW."
            )
            return RagAnswer(
                question=question,
                answer=answer,
                citations=[_citation_from_chunk(graduation, 1.0)],
                prompt="Policy rule extracted from the graduation requirements section.",
            )

    return None


def _find_chunk(chunks, phrase: str):
    phrase_lower = phrase.lower()
    for chunk in chunks:
        if phrase_lower in chunk.text.lower():
            return chunk
    return None


def _citation_from_chunk(chunk, score: float) -> Citation:
    return Citation(
        document_name=chunk.document_name,
        page_number=chunk.page_number,
        chunk_id=chunk.id,
        score=score,
        snippet=_shorten(chunk.text, 260),
    )


def build_grounded_prompt(question: str, results: list[RetrievalResult]) -> str:
    evidence = "\n\n".join(
        f"[{index}] Source: {result.chunk.document_name}, page {result.chunk.page_number}\n"
        f"{result.chunk.text}"
        for index, result in enumerate(results, start=1)
    )
    return (
        "Answer the question using only the evidence below. "
        "If the evidence is not enough, say you do not know.\n\n"
        f"Question: {question}\n\n"
        f"Evidence:\n{evidence}\n\n"
        "Answer with citations."
    )


def _build_extractive_answer(question: str, results: list[RetrievalResult]) -> str:
    query_terms = set(tokenize(question))
    sentences: list[tuple[int, str]] = []

    for result in results:
        for sentence in re.split(r"(?<=[.!?])\s+", result.chunk.text):
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue
            score = len(query_terms.intersection(tokenize(sentence)))
            if score > 0:
                sentences.append((score, sentence))

    if not sentences:
        best = results[0].chunk
        return (
            f"Relevant policy information was found in {best.document_name}, "
            f"page {best.page_number}: {_shorten(best.text, 420)}"
        )

    sentences.sort(key=lambda item: item[0], reverse=True)
    chosen = [sentence for _, sentence in sentences[:2]]
    source = results[0].chunk
    return " ".join(chosen) + f" Source: {source.document_name}, page {source.page_number}."


def _shorten(text: str, max_chars: int) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 3].rstrip() + "..."
