# CampusGuide AI

A basic single-document RAG assistant that answers questions from one active IIITD policy PDF and returns source citations.

This project is intentionally simple enough to understand in an interview, but still shows backend, database, retrieval, and RAG fundamentals.

## 30-Second Explanation

CampusGuide AI indexes one official IIITD policy PDF by default: the B.Tech Regulations PDF. A user can also upload any one PDF/TXT/MD file, which replaces the active source. A student can ask a question, and the backend retrieves the most relevant chunks, builds a grounded answer, and returns citations with document name and page number.

## Features

- Seed the knowledge base with one official IIITD B.Tech Regulations PDF
- Upload one user-provided `.txt`, `.md`, or `.pdf` document and make it the active source
- Split documents into overlapping chunks
- Store document metadata and chunks in SQLite
- Retrieve relevant chunks using TF-IDF vector similarity
- Return citation-backed answers
- Log asked questions
- Provide a CLI and local HTTP API
- Include a simple browser UI
- Include unit tests for indexing and retrieval

## Default IIITD Document

The project uses this official IIITD document by default:

- `iiitd-btech-regulations-2025-october.pdf`

The downloaded file list and source URLs are stored in:

```text
data/iiitd_policies/manifest.json
```

## Tech Stack

- Python
- SQLite
- Pure-Python TF-IDF retrieval
- pdfplumber for PDF text extraction
- Standard-library HTTP server
- unittest

## Project Structure

```text
campusguide-ai/
  data/
    iiitd_policies/       downloaded official IIITD policy documents
    sample_docs/          fallback sample campus policy documents
    uploads/              user-uploaded PDFs/text files
    indexed/              generated SQLite database
  scripts/
    download_iiitd_policies.py
  src/campusguide/
    chunker.py            splits documents into chunks
    document_loader.py    loads txt, md, and pdf files
    retriever.py          TF-IDF vector retrieval
    rag_pipeline.py       indexing and question-answering pipeline
    server.py             local HTTP API and browser UI
    storage.py            SQLite tables and queries
  tests/
    test_pipeline.py
  run.py
```

## Quick Start

Run from the project root:

```bash
python scripts/download_iiitd_policies.py
python run.py index
python run.py ask "how many credits are required for intern"
python run.py serve --port 8766
```

Then open:

```text
http://127.0.0.1:8766
```

The official PDFs/text pages are downloaded from IIITD at setup time and are not committed to the repository. To refresh them:

```bash
python scripts/download_iiitd_policies.py
python run.py index
```

## API

Index documents:

```http
POST /index
Content-Type: application/json

{"reset": true}
```

Ask a question:

```http
POST /ask
Content-Type: application/json

{"question": "Can I sit for placement after accepting an offer?", "top_k": 3}
```

List indexed documents:

```http
GET /documents
```

Upload and index one policy PDF/text file:

```http
POST /upload
Content-Type: multipart/form-data

file=<policy.pdf>
```

## Database Design

```text
documents(id, name, source_path, created_at)
chunks(id, document_id, page_number, chunk_index, text)
question_logs(id, question, answer, created_at)
```

## How RAG Works Here

1. One official IIITD PDF is loaded from `data/iiitd_policies`.
2. Text is split into overlapping chunks.
3. Chunks are stored in SQLite.
4. Query and chunks are converted into TF-IDF vectors.
5. The backend retrieves the highest scoring chunks.
6. The answer is generated only from retrieved chunks.
7. Citations are returned with document name, page number, and chunk id.

## Upgrade Path

This MVP uses TF-IDF so it works offline and is easy to explain. To make it stronger later:

- Replace TF-IDF with embeddings
- Store vectors in ChromaDB or PostgreSQL + pgvector
- Add hybrid search: keyword + vector search
- Add a real LLM call using OpenAI, Gemini, or a local model
- Add authentication for admin document uploads
- Add evaluation questions and retrieval accuracy metrics

## Resume Bullet

```text
Built CampusGuide AI, a single-document RAG assistant for IIITD B.Tech Regulations using Python, SQLite, PDF ingestion, document chunking, retrieval ranking, file upload, and citation-backed answers.
```

## Interview Talking Points

- Why chunking is needed
- Difference between keyword search and semantic embeddings
- Why citations reduce hallucination risk
- How SQLite stores document chunks and question logs
- How retrieval quality can be measured using test questions
- How the project can be upgraded to embeddings and pgvector
