# Legal AI Platform

A secure, multi-tenant full-stack application for legal document parsing, hybrid clause classification, automated risk-spotting, and semantic similarity clause search.

The platform combines a **FastAPI backend** (powered by local sentence embeddings, vector search, and LLaMA-based generative AI) with a **React/Vite frontend** featuring responsive risk-review dashboards and high-fidelity PDF report exports.

---

## Key Core Features

### 1. Multi-Tier Document Parsing & OCR
* **Native and Layout-complex PDFs:** Uses PyMuPDF for high-speed parsing, with automatic fallback to `pdfplumber` to extract irregular vertical/horizontal structures.
* **Scanned Image Support:** Automatically falls back to high-resolution page rendering and **Tesseract OCR** when no digital text layer is detected.
* **Regex Cleaner:** Fixes broken sentence breaks, split headings, and removes header/footer page artifacts.

### 2. Hybrid Clause Classification
* **Rule-based & Semantic Classifier:** Splits agreements into separate clauses and tags them with one of 15 preset legal categories.
* **Cosine Similarity:** Pairs deterministic keyword rules with a local **Sentence-Transformers** model (`all-MiniLM-L6-v2`) to verify clauses semantically when wording is unique or ambiguous.

### 3. Automated Risk Assessment Engine
* **Rule-Based Prioritizer:** Evaluates clauses against a comprehensive set of legal checks (e.g., unlimited liability caps, open-ended survival terms, unilateral discretion, non-home jurisdiction forums).
* **Weighted Scoring:** Automatically assigns risk ratings:
  * **LOW (0-1):** Standard contract terminology.
  * **MEDIUM (2-4):** Advisable points of review (notice periods, foreign governing laws).
  * **HIGH (5+):** Severe exposure (e.g., uncapped liability).
* **Positive Signals:** Detects protective language (like opportunity-to-cure or home jurisdiction selections) to balance severity scores.

### 4. Secure Multi-Tenant Semantic Search (Vector Database)
* **ChromaDB Integration:** Indexes vectorized clauses for semantic retrieval against past agreements.
* **Strict Multi-Tenancy:** Prevents cross-user data leakage by enforcing metadata query boundaries (`where={"user_id": user_id}`) on all vector searches.
* **SHA-256 Deduplication:** Creates compound hash keys to prevent duplicate clause indexing.
* **Diversity Reranking:** Limits results to unique source files, excluding the document currently under review.

### 5. Generative AI Explanations & Redrafts
* **Context-Grounded LLM prompts:** Integrates the **Groq API** (`llama-3.1-8b-instant`) to generate plain-English explanations and draft safer alternative clauses by feeding original text, risk ratings, and recommendations directly to the model as prompt context.

### 6. Relational Models & JWT Security
* **SQLAlchemy ORM:** Keeps track of users and uploaded documents within SQLite.
* **JWT Access Keys:** Enforces security isolation at the API router level, using bcrypt-salted hashing and JWT signatures.

---

## Tech Stack
* **Frontend:** React, Vite, Axios, Lucide React, Print CSS Stylesheet (for dynamic PDF export layout compiling).
* **Backend:** FastAPI, Uvicorn, SQLAlchemy, SQLite, ChromaDB, Sentence-Transformers (`all-MiniLM-L6-v2`), Groq SDK (LLaMA 3.1), PyMuPDF (fitz), pdfplumber, PyTesseract, bcrypt, and python-jose.

---

## Running Locally

### Backend Setup:
Configure your environment by copying `.env.example` to `.env` in the root folder, and set your API keys (like `GROQ_API_KEY`).

Run the backend server:
```powershell
backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

### Frontend Setup:
Navigate to the frontend folder, install dependencies, and run the Vite dev server:
```powershell
cd frontend
npm install
npm run dev
```

---

## Validation & Testing

Run unit tests for backend APIs:
```powershell
backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

Validate the frontend build & styles:
```powershell
cd frontend
npm run lint
npm run build
```

---

## Administrative Commands

### Rebuilding the Vector Database
To rebuild the clause-level collection from the original page-level Chroma collection:
```powershell
backend\.venv\Scripts\python.exe -m backend.scripts.rebuild_clause_library
```
*Note: By default, the system runs in an offline-safe configuration (`EMBEDDING_LOCAL_FILES_ONLY=true`).*
