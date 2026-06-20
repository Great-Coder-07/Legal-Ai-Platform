import datetime
import hashlib
import os
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

try:
    from sentence_transformers import SentenceTransformer
    _ST_IMPORT_ERROR = None
except Exception as exc:
    SentenceTransformer = None
    _ST_IMPORT_ERROR = exc

from backend.database.connection import get_vector_collection


CLAUSE_COLLECTION = "legal_clauses_v2"
LEGACY_COLLECTION = "legal_cases"
SCHEMA_VERSION = 2
DEFAULT_MODEL = "all-MiniLM-L6-v2"

embedder = None
embedder_error = None


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _hash_text(value: str) -> str:
    return hashlib.sha256(_normalize_text(value).encode("utf-8")).hexdigest()


def document_fingerprint(text: str) -> str:
    return _hash_text(text)


def get_embedder():
    global embedder, embedder_error
    if embedder is not None:
        return embedder
    if embedder_error is not None:
        return None
    if SentenceTransformer is None:
        embedder_error = str(_ST_IMPORT_ERROR or "sentence-transformers is unavailable")
        return None

    model_name = os.getenv("CLAUSE_EMBEDDING_MODEL", DEFAULT_MODEL)
    local_only = os.getenv("EMBEDDING_LOCAL_FILES_ONLY", "true").lower() == "true"
    try:
        embedder = SentenceTransformer(model_name, local_files_only=local_only)
    except Exception as exc:
        embedder_error = str(exc)
        print(f"[clause_library] Embedding model unavailable: {exc}")
        return None
    return embedder


def reset_embedder_state():
    """Allow an operator or test to retry model loading after the environment changes."""
    global embedder, embedder_error
    embedder = None
    embedder_error = None


def _encode(model, texts: list[str]) -> list[list[float]]:
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vectors.tolist() if hasattr(vectors, "tolist") else list(vectors)


def build_clause_records(
    filename: str,
    text: str,
    user_id: int,  # 🔒 Senior Dev Fix: Explicitly bind to the owner's record index
    jurisdiction: str = "",
    page_texts: list[str] | None = None,
) -> tuple[str, list[dict]]:
    from backend.pipelines.contract_analyzer import classify_clause_by_rules, segment_clauses

    document_hash = _hash_text(text)
    clause_sources = []
    if page_texts:
        for page_number, page_text in enumerate(page_texts, start=1):
            page_clauses = segment_clauses(page_text)
            if not page_clauses and len(_normalize_text(page_text)) >= 40:
                page_clauses = [_normalize_text(page_text)]
            clause_sources.extend((clause, page_number) for clause in page_clauses)
    else:
        clauses = segment_clauses(text)
        if not clauses and len(_normalize_text(text)) >= 40:
            clauses = [_normalize_text(text)]
        clause_sources = [(clause, 0) for clause in clauses]

    records = []
    seen_clause_hashes = set()
    for index, (raw_clause, page_number) in enumerate(clause_sources, start=1):
        clause_text = _normalize_text(raw_clause)
        if len(clause_text) < 40:
            continue
        clause_hash = _hash_text(clause_text)
        if clause_hash in seen_clause_hashes:
            continue
        seen_clause_hashes.add(clause_hash)
        clause_type, confidence = classify_clause_by_rules(clause_text)
        
        # Unique record identity mapping hash
        record_id = hashlib.sha256(
            f"{user_id}:{document_hash}:{clause_hash}".encode("utf-8")
        ).hexdigest()
        
        records.append(
            {
                "id": record_id,
                "text": clause_text,
                "metadata": {
                    "user_id": int(user_id),  # 🔒 Core Tenant Anchor
                    "source": filename,
                    "source_filename": filename,
                    "document_type": filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown",
                    "document_hash": document_hash,
                    "clause_hash": clause_hash,
                    "clause_index": index,
                    "page_number": page_number,
                    "clause_type": clause_type,
                    "classification_confidence": float(round(confidence, 3)),
                    "jurisdiction": jurisdiction or "unspecified",
                    "character_count": len(clause_text),
                    "schema_version": SCHEMA_VERSION,
                    "ingested_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                },
            }
        )
    return document_hash, records


def ingest_document(
    filename: str,
    text: str,
    user_id: int,  # 🔒 Anchor param forwarded from upload.py routes layer
    jurisdiction: str = "",
    page_texts: list[str] | None = None,
) -> dict:
    """
    Index a document as individual, metadata-rich clauses pinned to a tenant user_id.
    """
    document_hash, records = build_clause_records(filename, text, user_id, jurisdiction, page_texts)
    if not records:
        return {
            "status": "skipped",
            "document_hash": document_hash,
            "indexed_clauses": 0,
            "reason": "No clause-sized text was detected.",
        }

    model = get_embedder()
    if model is None:
        return {
            "status": "unavailable",
            "document_hash": document_hash,
            "indexed_clauses": 0,
            "reason": "Embedding model is unavailable.",
        }

    try:
        collection = get_vector_collection(CLAUSE_COLLECTION)
        documents = [record["text"] for record in records]
        collection.upsert(
            ids=[record["id"] for record in records],
            documents=documents,
            metadatas=[record["metadata"] for record in records],
            embeddings=_encode(model, documents),
        )
        return {
            "status": "indexed",
            "document_hash": document_hash,
            "indexed_clauses": len(records),
            "source": filename,
        }
    except Exception as exc:
        print(f"[clause_library] Ingestion failed: {exc}")
        return {
            "status": "error",
            "document_hash": document_hash,
            "indexed_clauses": 0,
            "reason": "Clause library storage is unavailable.",
        }


def _distance_to_similarity(distance: float | None) -> float:
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - float(distance)))


def search_similar_clauses(
    query: str,
    user_id: int,  # 🔒 Senior Dev Fix: Multi-tenant protection anchor
    clause_type: str = "",
    exclude_document_hash: str = "",
    exclude_source: str = "",
    top_k: int = 3,
    min_similarity: float | None = None,
) -> dict:
    model = get_embedder()
    if model is None:
        return {
            "status": "unavailable",
            "matches": [],
            "message": "The local embedding model is unavailable.",
        }

    try:
        collection = get_vector_collection(CLAUSE_COLLECTION)
        library_size = collection.count()
        if library_size == 0:
            return {
                "status": "empty",
                "matches": [],
                "message": "Your private clause library is empty.",
            }

        candidate_count = min(library_size, max(top_k * 10, 30))
        
        # 🔒 Senior Dev Fix: Restrict lookups strictly to this tenant's user_id
        result = collection.query(
            query_embeddings=_encode(model, [_normalize_text(query)]),
            n_results=candidate_count,
            include=["documents", "metadatas", "distances"],
            where={"user_id": int(user_id)}  # Prevents cross-user clause matching
        )
    except Exception as exc:
        print(f"[clause_library] Search failed: {exc}")
        return {
            "status": "error",
            "matches": [],
            "message": "The private clause library is unavailable.",
        }

    threshold = (
        min_similarity
        if min_similarity is not None
        else float(os.getenv("CLAUSE_SIMILARITY_THRESHOLD", "0.45"))
    )
    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    candidates = []
    seen_clause_hashes = set()
    for item_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
        metadata = metadata or {}
        if exclude_document_hash and metadata.get("document_hash") == exclude_document_hash:
            continue
        if exclude_source and metadata.get("source") == exclude_source:
            continue

        similarity = _distance_to_similarity(distance)
        if similarity < threshold:
            continue
        clause_hash = metadata.get("clause_hash") or _hash_text(document)
        if clause_hash in seen_clause_hashes:
            continue
        seen_clause_hashes.add(clause_hash)

        same_type = bool(clause_type and metadata.get("clause_type") == clause_type)
        rerank_score = similarity + (0.06 if same_type else 0.0)
        candidates.append(
            {
                "id": item_id,
                "text": document,
                "metadata": metadata,
                "similarity": round(similarity, 4),
                "similarity_percent": round(similarity * 100),
                "same_clause_type": same_type,
                "_rank": rerank_score,
            }
        )

    candidates.sort(key=lambda item: item["_rank"], reverse=True)

    # Prefer one result per source document. Returning fewer strong, diverse
    # matches is better than repeating several chunks from the same contract.
    selected = []
    used_documents = set()
    for candidate in candidates:
        document_key = candidate["metadata"].get("document_hash") or candidate["metadata"].get("source")
        if document_key in used_documents:
            continue
        used_documents.add(document_key)
        selected.append(candidate)
        if len(selected) == top_k:
            break
            
    for item in selected:
        item.pop("_rank", None)

    return {
        "status": "ok",
        "matches": selected,
        "threshold": threshold,
        "library_clause_count": library_size,
        "message": (
            "Matches are from your private document library, not court precedents or verified legal authorities."
        ),
    }


def get_library_status(user_id: int) -> dict:
    """
    Fetch the clause library structural layout statistics scoped strictly 
    to an authenticated user_id tenant.
    """
    try:
        collection = get_vector_collection(CLAUSE_COLLECTION)
        
        # 🔒 Senior Dev Fix: Only fetch metadata blocks belonging to this user
        data = collection.get(where={"user_id": int(user_id)}, include=["metadatas"])
        metadatas = data.get("metadatas") or []
        
        documents = {}
        for metadata in metadatas:
            if not metadata:
                continue
            key = metadata.get("document_hash") or metadata.get("source")
            documents[key] = metadata.get("source", "Unknown document")
            
        return {
            "status": "ok",
            "clause_count": len(data.get("ids") or []),
            "document_count": len(documents),
            "documents": [
                {"document_hash": key, "source": source}
                for key, source in sorted(documents.items(), key=lambda item: item[1].lower())
            ],
            "embedding_model_loaded": embedder is not None,
            "embedding_error": embedder_error or "",
        }
    except Exception as exc:
        return {
            "status": "error",
            "clause_count": 0,
            "document_count": 0,
            "documents": [],
            "embedding_model_loaded": embedder is not None,
            "embedding_error": embedder_error or "",
            "message": str(exc),
        }


def delete_library_document(document_hash: str, user_id: int) -> dict:
    """
    Purges document clause vectors only if they belong to the requesting tenant user_id.
    """
    collection = get_vector_collection(CLAUSE_COLLECTION)
    
    # 🔒 Senior Dev Fix: Scoping lookup with a logical AND pairing
    tenant_query = {
        "$and": [
            {"document_hash": document_hash},
            {"user_id": int(user_id)}
        ]
    }
    
    existing = collection.get(where=tenant_query, include=["metadatas"])
    count = len(existing.get("ids") or [])
    
    if count:
        collection.delete(where=tenant_query)
        
    return {"status": "deleted", "deleted_clauses": count, "document_hash": document_hash}


def migrate_legacy_collection(user_id: int) -> dict:
    """
    Rebuild the v2 clause collection from documents stored by the original
    page/paragraph-based index, pinning them securely to a migration owner user_id.
    """
    grouped = defaultdict(list)
    legacy_path = Path(os.getenv("LEGACY_CHROMA_DB_PATH", "./chroma_db")) / "chroma.sqlite3"
    if not legacy_path.exists():
        return {
            "status": "skipped",
            "reason": f"Legacy database not found at {legacy_path}.",
            "documents": 0,
            "clauses": 0,
        }

    try:
        uri = f"file:{legacy_path.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as connection:
            rows = connection.execute(
                """
                SELECT
                    MAX(CASE WHEN metadata.key = 'source' THEN metadata.string_value END) AS source,
                    MAX(CASE WHEN metadata.key = 'chunk_index' THEN metadata.int_value END) AS chunk_index,
                    MAX(CASE WHEN metadata.key = 'chroma:document' THEN metadata.string_value END) AS document
                FROM embeddings
                JOIN embedding_metadata AS metadata ON metadata.id = embeddings.id
                GROUP BY embeddings.id
                ORDER BY source, chunk_index
                """
            ).fetchall()
        for source, chunk_index, document in rows:
            if document:
                grouped[source or "legacy-document"].append((int(chunk_index or 0), document))
    except Exception as exc:
        return {"status": "error", "reason": str(exc), "documents": 0, "clauses": 0}

    migrated_documents = 0
    migrated_clauses = 0
    failures = []
    for source, chunks in grouped.items():
        text = "\n\n".join(chunk for _, chunk in sorted(chunks))
        
        # 🔒 Senior Dev Fix: Forwarding the user_id token into the updated ingestion engine
        outcome = ingest_document(filename=source, text=text, user_id=int(user_id))
        if outcome["status"] == "indexed":
            migrated_documents += 1
            migrated_clauses += outcome["indexed_clauses"]
        else:
            failures.append({"source": source, "reason": outcome.get("reason", outcome["status"])})

    return {
        "status": "completed" if not failures else "partial",
        "documents": migrated_documents,
        "clauses": migrated_clauses,
        "failures": failures,
    }


# Backward-compatible alias for older callers.
def search_precedents(query: str, top_k: int = 3) -> list:
    # Note: If search_similar_clauses is upgraded for multi-tenancy, 
    # make sure to pass the user_id through here too.
    return search_similar_clauses(query=query, top_k=top_k)["matches"]

def search_library_globally(
    query: str,
    user_id: int,  # 🔒 Senior Dev Fix: Multi-tenant protection anchor
    top_k: int = 5,
    min_similarity: float | None = None,
) -> dict:
    """
    Executes an unconstrained semantic search across the entire vector library index
    isolated to a specific authenticated user_id.
    """
    model = get_embedder()
    if model is None:
        return {
            "status": "unavailable",
            "matches": [],
            "message": "The local embedding model is unavailable.",
        }

    try:
        collection = get_vector_collection(CLAUSE_COLLECTION)
        library_size = collection.count()
        if library_size == 0:
            return {
                "status": "empty",
                "matches": [],
                "message": "Your private clause library is empty.",
            }

        # Query a generous window from ChromaDB so we can safely filter by threshold
        candidate_count = min(library_size, max(top_k * 4, 20))
        
        # 🔒 Senior Dev Fix: Inject metadata filtering to restrict results by tenant ownership
        result = collection.query(
            query_embeddings=_encode(model, [_normalize_text(query)]),
            n_results=candidate_count,
            include=["documents", "metadatas", "distances"],
            where={"user_id": int(user_id)}  # Ensures zero data leakage across user sessions
        )
    except Exception as exc:
        print(f"[clause_library] Global search block error: {exc}")
        return {
            "status": "error",
            "matches": [],
            "message": "The private clause library database is unavailable.",
        }

    threshold = (
        min_similarity
        if min_similarity is not None
        else float(os.getenv("GLOBAL_SEARCH_THRESHOLD", "0.25"))
    )
    
    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    matches = []
    for item_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
        metadata = metadata or {}
        similarity = _distance_to_similarity(distance)
        
        if similarity < threshold:
            continue

        matches.append(
            {
                "id": item_id,
                "text": document,
                "metadata": metadata,
                "score": round(similarity, 4),
                "similarity_percent": round(similarity * 100),
            }
        )

    # Sort strictly by distance match ranking performance
    matches.sort(key=lambda item: item["score"], reverse=True)

    return {
        "status": "ok",
        "matches": matches[:top_k],
        "library_clause_count": library_size,
    }
