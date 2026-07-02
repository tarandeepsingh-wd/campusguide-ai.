from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PageText:
    document_name: str
    page_number: int
    text: str
    source_path: str


SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf"}


def load_document(path: Path) -> list[PageText]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        text = path.read_text(encoding="utf-8")
        return [
            PageText(
                document_name=path.name,
                page_number=1,
                text=text,
                source_path=str(path),
            )
        ]

    if suffix == ".pdf":
        try:
            import pdfplumber
        except ImportError as exc:
            raise RuntimeError(
                "PDF support requires pdfplumber. Install requirements.txt or use txt/md files."
            ) from exc

        pages: list[PageText] = []
        with pdfplumber.open(str(path)) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                extracted = page.extract_text() or ""
                pages.append(
                    PageText(
                        document_name=path.name,
                        page_number=index,
                        text=extracted,
                        source_path=str(path),
                    )
                )
        return pages

    raise ValueError(f"Unsupported file type: {path.suffix}")


def iter_documents(docs_dir: Path) -> list[Path]:
    if not docs_dir.exists():
        raise FileNotFoundError(f"Docs directory not found: {docs_dir}")

    return sorted(
        path
        for path in docs_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )
