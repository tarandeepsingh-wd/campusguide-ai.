from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredChunk:
    id: int
    document_name: str
    source_path: str
    page_number: int
    chunk_index: int
    text: str


class RagStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    source_path TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id INTEGER NOT NULL,
                    page_number INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(id)
                );

                CREATE TABLE IF NOT EXISTS question_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_chunks_document_id
                    ON chunks(document_id);
                CREATE INDEX IF NOT EXISTS idx_chunks_page
                    ON chunks(page_number);
                """
            )
            connection.commit()

    def reset(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                DELETE FROM question_logs;
                DELETE FROM chunks;
                DELETE FROM documents;
                """
            )
            connection.commit()

    def add_document(self, name: str, source_path: str) -> int:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO documents(name, source_path)
                VALUES(?, ?)
                """,
                (name, source_path),
            )
            row = connection.execute(
                "SELECT id FROM documents WHERE source_path = ?",
                (source_path,),
            ).fetchone()
            connection.commit()
            return int(row["id"])

    def delete_chunks_for_document(self, document_id: int) -> None:
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            connection.commit()

    def add_chunk(
        self,
        document_id: int,
        page_number: int,
        chunk_index: int,
        text: str,
    ) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO chunks(document_id, page_number, chunk_index, text)
                VALUES(?, ?, ?, ?)
                """,
                (document_id, page_number, chunk_index, text),
            )
            connection.commit()

    def load_chunks(self) -> list[StoredChunk]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    chunks.id,
                    documents.name AS document_name,
                    documents.source_path,
                    chunks.page_number,
                    chunks.chunk_index,
                    chunks.text
                FROM chunks
                JOIN documents ON documents.id = chunks.document_id
                ORDER BY documents.name, chunks.page_number, chunks.chunk_index
                """
            ).fetchall()

        return [
            StoredChunk(
                id=int(row["id"]),
                document_name=str(row["document_name"]),
                source_path=str(row["source_path"]),
                page_number=int(row["page_number"]),
                chunk_index=int(row["chunk_index"]),
                text=str(row["text"]),
            )
            for row in rows
        ]

    def list_documents(self) -> list[dict[str, str | int]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    documents.id,
                    documents.name,
                    documents.source_path,
                    COUNT(chunks.id) AS chunk_count
                FROM documents
                LEFT JOIN chunks ON chunks.document_id = documents.id
                GROUP BY documents.id
                ORDER BY documents.name
                """
            ).fetchall()

        return [
            {
                "id": int(row["id"]),
                "name": str(row["name"]),
                "source_path": str(row["source_path"]),
                "chunk_count": int(row["chunk_count"]),
            }
            for row in rows
        ]

    def log_question(self, question: str, answer: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO question_logs(question, answer) VALUES(?, ?)",
                (question, answer),
            )
            connection.commit()
