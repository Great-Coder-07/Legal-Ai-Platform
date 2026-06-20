# Legal AI Platform

React/Vite frontend and FastAPI backend for document parsing, contract issue-spotting, summarization, clause explanation, and private-library clause matching.

## Run locally

Backend:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Copy `.env.example` to `.env` and configure the values required by your environment.

## Validation

```powershell
backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
cd frontend
npm run lint
npm run build
```

## Review methodology

The risk engine is a conservative issue-spotting aid. Scores indicate review priority:

- LOW: 0-1
- MEDIUM: 2-4
- HIGH: 5+

They are not conclusions about legality or enforceability. Results depend on the complete agreement, governing law, parties, transaction, and bargaining position. `LEGAL_HOME_JURISDICTION` controls which governing law is treated as the user's home jurisdiction; the default is `india`.

## Private clause library

The “Search private library” action compares a clause against clauses that the user explicitly chose to retain. It does not search case law and must not be presented as verified legal precedent.

- Documents are segmented and indexed clause-by-clause.
- Deterministic hashes prevent duplicate records when the same content is uploaded again.
- Results are thresholded, reranked by clause type, limited to one match per source document, and exclude the document currently being reviewed.
- Results include similarity, source, clause number, page number when available, jurisdiction, and clause type.
- Users can inspect and delete retained documents from the upload screen.

By default, ChromaDB is stored in `%LOCALAPPDATA%\LegalAIPlatform\chroma_db`. Avoid OneDrive, Dropbox, or other synchronized folders because their file locking can corrupt or block SQLite/HNSW writes.

To rebuild the new clause-level collection from the original page-level Chroma collection:

```powershell
backend\.venv\Scripts\python.exe -m backend.scripts.rebuild_clause_library
```

The default is offline-safe (`EMBEDDING_LOCAL_FILES_ONLY=true`). Pre-cache `CLAUSE_EMBEDDING_MODEL`, or temporarily set this option to `false` on a machine allowed to download the model.

Do not retain confidential documents without an appropriate privacy notice, access controls, retention period, and deletion policy.
