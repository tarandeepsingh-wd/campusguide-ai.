from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .rag_pipeline import ask_question, index_source
from .server import run_server
from .storage import RagStore


DEFAULT_DB = Path("data/indexed/campusguide.db")
DEFAULT_DOCS = Path("data/iiitd_policies/iiitd-btech-regulations-2025-october.pdf")
DEFAULT_UPLOADS = Path("data/uploads")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="CampusGuide AI basic RAG backend")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Index one PDF/text source into SQLite")
    index_parser.add_argument("--docs", type=Path, default=DEFAULT_DOCS)
    index_parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    index_parser.add_argument("--no-reset", action="store_true")

    ask_parser = subparsers.add_parser("ask", help="Ask a question")
    ask_parser.add_argument("question")
    ask_parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    ask_parser.add_argument("--top-k", type=int, default=3)

    serve_parser = subparsers.add_parser("serve", help="Run local HTTP server")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    serve_parser.add_argument("--docs", type=Path, default=DEFAULT_DOCS)
    serve_parser.add_argument("--uploads", type=Path, default=DEFAULT_UPLOADS)

    args = parser.parse_args()

    if args.command == "index":
        store = RagStore(args.db)
        stats = index_source(args.docs, store, reset=not args.no_reset)
        print(f"Indexed {stats['documents']} documents and {stats['chunks']} chunks.")
        return

    if args.command == "ask":
        store = RagStore(args.db)
        result = ask_question(store, args.question, top_k=args.top_k)
        print(result.answer)
        if result.citations:
            print("\nCitations:")
            for citation in result.citations:
                print(
                    f"- {citation.document_name}, page {citation.page_number}, "
                    f"chunk {citation.chunk_id}, score {citation.score}"
                )
        return

    if args.command == "serve":
        run_server(args.host, args.port, args.db, args.docs, args.uploads)


if __name__ == "__main__":
    main()
