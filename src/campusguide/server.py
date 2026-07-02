from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .document_loader import SUPPORTED_EXTENSIONS
from .rag_pipeline import ask_question, index_file, index_source
from .storage import RagStore


class CampusGuideHandler(BaseHTTPRequestHandler):
    store: RagStore
    docs_source: Path
    upload_dir: Path

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send_html(_HTML)
            return
        if path == "/health":
            self._send_json({"status": "ok"})
            return
        if path == "/documents":
            self._send_json({"documents": self.store.list_documents()})
            return
        self._send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/upload":
            self._handle_upload()
            return

        body = self._read_json()
        if path == "/ask":
            question = str(body.get("question", "")).strip()
            top_k = int(body.get("top_k", 3))
            if not question:
                self._send_json({"error": "question is required"}, status=400)
                return
            result = ask_question(self.store, question, top_k=top_k)
            self._send_json(
                {
                    "question": result.question,
                    "answer": result.answer,
                    "citations": [citation.__dict__ for citation in result.citations],
                    "prompt": result.prompt,
                }
            )
            return

        if path == "/index":
            reset = bool(body.get("reset", True))
            stats = index_source(self.docs_source, self.store, reset=reset)
            self._send_json(
                {
                    "message": "index complete",
                    "active_source": str(self.docs_source),
                    "documents": stats["documents"],
                    "chunks": stats["chunks"],
                }
            )
            return

        self._send_json({"error": "Not found"}, status=404)

    def _handle_upload(self) -> None:
        try:
            filename, content = self._read_multipart_file()
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return

        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            self._send_json(
                {
                    "error": (
                        "Unsupported file type. Upload one of: "
                        + ", ".join(sorted(SUPPORTED_EXTENSIONS))
                    )
                },
                status=400,
            )
            return

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        safe_name = _safe_filename(filename)
        target_path = _unique_path(self.upload_dir / safe_name)
        target_path.write_bytes(content)

        try:
            self.store.reset()
            stats = index_file(target_path, self.store, replace_existing=True)
        except Exception as exc:
            self._send_json({"error": f"Upload saved, but indexing failed: {exc}"}, status=500)
            return

        self._send_json(
            {
                "message": "upload indexed",
                "filename": target_path.name,
                "path": str(target_path),
                **stats,
            }
        )

    def _read_json(self) -> dict:
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw)

    def _read_multipart_file(self) -> tuple[str, bytes]:
        content_type = self.headers.get("content-type", "")
        match = re.search(r"boundary=(.+)", content_type)
        if not content_type.startswith("multipart/form-data") or not match:
            raise ValueError("Expected multipart/form-data upload")

        boundary = match.group(1).strip('"')
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            raise ValueError("Empty upload request")

        body = self.rfile.read(length)
        boundary_bytes = ("--" + boundary).encode("utf-8")
        for part in body.split(boundary_bytes):
            if b"Content-Disposition:" not in part:
                continue
            header_blob, _, content = part.partition(b"\r\n\r\n")
            headers = header_blob.decode("utf-8", errors="ignore")
            if 'name="file"' not in headers:
                continue
            filename_match = re.search(r'filename="([^"]+)"', headers)
            if not filename_match:
                raise ValueError("Uploaded file is missing a filename")
            filename = Path(filename_match.group(1)).name
            content = content.rstrip(b"\r\n-")
            if not content:
                raise ValueError("Uploaded file is empty")
            return filename, content

        raise ValueError("No file field named 'file' found")

    def _send_json(self, payload: dict, status: int = 200) -> None:
        encoded = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_html(self, html: str, status: int = 200) -> None:
        encoded = html.encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def run_server(
    host: str,
    port: int,
    db_path: Path,
    docs_source: Path,
    upload_dir: Path | None = None,
) -> None:
    CampusGuideHandler.store = RagStore(db_path)
    CampusGuideHandler.docs_source = docs_source
    CampusGuideHandler.upload_dir = upload_dir or Path("data/uploads")
    server = ThreadingHTTPServer((host, port), CampusGuideHandler)
    print(f"CampusGuide AI running at http://{host}:{port}")
    print("POST /index once, then ask questions from the browser.")
    server.serve_forever()


def _safe_filename(filename: str) -> str:
    stem = Path(filename).stem
    suffix = Path(filename).suffix.lower()
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", stem).strip(".-")
    return (cleaned or "upload") + suffix


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("Could not create a unique upload filename")


_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CampusGuide AI</title>
  <style>
    body { margin: 0; font-family: Arial, sans-serif; background: #f6f7f9; color: #17202a; }
    main { max-width: 880px; margin: 0 auto; padding: 32px 18px; }
    header { margin-bottom: 22px; }
    h1 { margin: 0 0 8px; font-size: 32px; }
    p { line-height: 1.5; }
    .panel { background: white; border: 1px solid #d9dee7; border-radius: 8px; padding: 18px; margin: 16px 0; }
    textarea { width: 100%; min-height: 84px; padding: 12px; border-radius: 6px; border: 1px solid #b8c1cc; font: inherit; box-sizing: border-box; }
    button { border: 0; border-radius: 6px; padding: 10px 14px; margin-top: 10px; cursor: pointer; background: #1463ff; color: white; font-weight: 700; }
    button.secondary { background: #3d4a5c; margin-left: 8px; }
    pre { white-space: pre-wrap; background: #101827; color: #edf2ff; padding: 14px; border-radius: 6px; overflow: auto; }
    .citation { border-left: 4px solid #1463ff; padding-left: 12px; margin: 12px 0; }
  </style>
</head>
<body>
<main>
  <header>
    <h1>CampusGuide AI</h1>
    <p>Ask questions from one active IIITD policy PDF. Uploading a file replaces the active source.</p>
  </header>

  <section class="panel">
    <button onclick="indexDocs()">Index Default IIITD B.Tech Regulations PDF</button>
    <button class="secondary" onclick="loadDocs()">Show Indexed Docs</button>
    <pre id="status">Ready.</pre>
  </section>

  <section class="panel">
    <h3>Upload One Policy PDF/Text File</h3>
    <p>The uploaded file becomes the only active source for answers.</p>
    <input id="file" type="file" accept=".pdf,.txt,.md">
    <button onclick="uploadFile()">Upload and Index</button>
  </section>

  <section class="panel">
    <textarea id="question" placeholder="Ask: how many credits are required for internship?"></textarea>
    <button onclick="ask()">Ask</button>
    <h3>Answer</h3>
    <p id="answer"></p>
    <h3>Citations</h3>
    <div id="citations"></div>
  </section>
</main>

<script>
async function indexDocs() {
  const response = await fetch('/index', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({reset: true})
  });
  document.getElementById('status').textContent = JSON.stringify(await response.json(), null, 2);
}

async function loadDocs() {
  const response = await fetch('/documents');
  document.getElementById('status').textContent = JSON.stringify(await response.json(), null, 2);
}

async function uploadFile() {
  const fileInput = document.getElementById('file');
  if (!fileInput.files.length) {
    document.getElementById('status').textContent = 'Choose a PDF, TXT, or MD file first.';
    return;
  }
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  const response = await fetch('/upload', { method: 'POST', body: formData });
  document.getElementById('status').textContent = JSON.stringify(await response.json(), null, 2);
  await loadDocs();
}

async function ask() {
  const question = document.getElementById('question').value;
  const response = await fetch('/ask', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({question, top_k: 3})
  });
  const data = await response.json();
  document.getElementById('answer').textContent = data.answer || data.error;
  const citations = document.getElementById('citations');
  citations.innerHTML = '';
  for (const citation of data.citations || []) {
    const item = document.createElement('div');
    item.className = 'citation';
    item.innerHTML = `<strong>${citation.document_name}, page ${citation.page_number}</strong><br>${citation.snippet}<br>score: ${citation.score}`;
    citations.appendChild(item);
  }
}
</script>
</body>
</html>
"""
