# AI Knowledge Inbox

A minimal Django + React knowledge inbox with note and URL ingestion plus a lightweight RAG pipeline.

## Features

- Save plain-text notes
- Save URLs and fetch page content server-side
- Chunk saved content into retrieval units
- Generate embeddings with Sentence Transformers
- Search semantically across saved content
- Answer questions with a simple RAG flow using saved chunks
- Display answer and source snippets in the UI
- Support provider-based external model routing for OpenAI and Gemini

## Stack

- Backend: Django, Django REST Framework
- Frontend: React + Vite
- Embeddings: sentence-transformers/all-MiniLM-L6-v2
- Storage: SQLite
- AI generation: OpenAI or Gemini when configured; otherwise a grounded fallback answer is generated from top matching chunks

## Run locally

1. Create and activate the environment:

   python3 -m venv .venv
   . .venv/bin/activate

2. Install Python dependencies:

   pip install Django djangorestframework django-cors-headers python-dotenv requests beautifulsoup4 openai sentence-transformers scikit-learn

3. Optional external model config in a `.env` file:

   OPENAI_API_KEY=...
   GEMINI_API_KEY=...
   LLM_PROVIDER=openai   # or gemini

4. Apply migrations:

   python manage.py migrate

5. Start the Django API:

   python manage.py runserver 0.0.0.0:8000

6. In another terminal, install frontend dependencies and run Vite:

   cd frontend
   npm install
   npm run dev -- --host 0.0.0.0

7. Open http://localhost:5173

## API

- POST /api/ingest/
- GET /api/items/
- POST /api/query/

## Architecture notes

- Chunking strategy: content is split into overlapping text windows to preserve local context while staying retrieval-friendly.
- Vector store: SQLite stores embedding vectors next to content and related metadata, which keeps the prototype simple but still realistic.
- Scale limits: a single SQLite database and local embedding model are suitable for small single-user workloads but will not handle large concurrent traffic or massive corpora without moving to a dedicated vector database and async worker queue.
- Production changes: add background jobs, indexing, observability, model versioning, and proper secret management for production deployments.

## Debugging and reliability

- Structured logging is intentionally lightweight and can be extended via Django logging config.
- HTTP status codes are explicit for validation and ingestion errors.
- RAG fallbacks keep the app usable even without an external LLM key.

## External model providers

The app supports a provider abstraction for external LLMs:

- OpenAI: uses `OPENAI_API_KEY` when available
- Gemini: uses `GEMINI_API_KEY` and `LLM_PROVIDER=gemini` when configured
- Fallback: if no external model is configured, the app still answers from the top matching chunks

### Gemini example

```bash
export GEMINI_API_KEY="your_key_here"
export LLM_PROVIDER="gemini"
```

This is the same flow used by the app-level provider selection; the backend chooses the configured provider automatically.
