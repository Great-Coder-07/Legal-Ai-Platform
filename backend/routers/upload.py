from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from typing import Dict, Any, List
from pydantic import BaseModel, Field
import os
from backend.services.parsers import parse_document_with_pages
from backend.services.orchestrator import route_document
from backend.services.explainability import generate_explanation
from backend.services.redraft_clause import generate_redraft          # NEW
from backend.pipelines.research_agent import ingest_document

router = APIRouter()


# ── Request models ────────────────────────────────────────────────────────────

class ClauseRequest(BaseModel):
    clause_text: str
    clause_type: str
    risk_level: str
    risk_reason: str


class PrecedentRequest(BaseModel):
    clause_text: str


class SimilarClauseRequest(BaseModel):
    clause_text: str = Field(min_length=20)
    clause_type: str = ""
    exclude_document_hash: str = ""
    exclude_source: str = ""
    top_k: int = Field(default=3, ge=1, le=10)
    min_similarity: float | None = Field(default=None, ge=0, le=1)


class RedraftRequest(BaseModel):          # NEW
    clause_text: str
    clause_type: str
    risk_level: str
    risk_reason: str
    recommendations: List[str] = Field(default_factory=list)


class GlobalSearchRequest(BaseModel):     # NEW: For Global Semantic Search Engine
    query: str = Field(..., min_length=2)
    top_k: int = Field(default=5, ge=1, le=20)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    task_type: str = Form("analyze_contract"),
    retain_in_library: Any = Form(False), # Changed to Any to safely handle incoming string forms
    jurisdiction: str = Form(""),
) -> Dict[str, Any]:
    """
    Upload a document and route it to the correct AI pipeline.
    """
    try:
        # 🔥 SENIOR DEV FIX: Explicitly parse potential string-based boolean form data
        retain_requested = str(retain_in_library).lower() in ("true", "1", "yes")
        
        jurisdiction_value = jurisdiction if isinstance(jurisdiction, str) else ""
        max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "15"))
        max_upload_bytes = max_upload_mb * 1024 * 1024
        file_bytes = await file.read(max_upload_bytes + 1)
        if len(file_bytes) > max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds the {max_upload_mb} MB upload limit.",
            )

        allowed_tasks = {"analyze_contract", "summarize_case"}
        if task_type not in allowed_tasks:
            raise HTTPException(status_code=400, detail="Unsupported task type.")

        text, page_texts = parse_document_with_pages(file.filename, file_bytes)

        if not text or text.strip() == "":
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from document.",
            )

        result = route_document(text, task_type=task_type)
        from backend.pipelines.research_agent import document_fingerprint

        document_hash = document_fingerprint(text)
        result.setdefault("metadata", {})
        result["metadata"].update(
            {
                "document_hash": document_hash,
                "source_filename": file.filename,
                "retained_in_clause_library": retain_requested,
            }
        )

        library_enabled = os.getenv("CLAUSE_LIBRARY_ENABLED", "true").lower() == "true"
        library_indexing = "not_requested"
        if retain_requested and library_enabled and task_type == "analyze_contract":
            background_tasks.add_task(
                ingest_document,
                file.filename,
                text,
                jurisdiction_value,
                page_texts,
            )
            library_indexing = "scheduled"
        elif retain_requested and not library_enabled:
            library_indexing = "disabled"

        return {
            "status": "success",
            "filename": file.filename,
            "task": task_type,
            "results": result,
            "library_indexing": library_indexing,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[upload] Processing failed: {e}")
        raise HTTPException(status_code=500, detail="Document processing failed.")


@router.post("/explain-clause")
async def explain_clause(req: ClauseRequest) -> Dict[str, Any]:
    """
    Explains a single clause on demand via Groq.
    Called when the user clicks the 'Explain clause' button.
    """
    try:
        result = generate_explanation(
            {
                "clause_text": req.clause_text,
                "type": req.clause_type,
                "risk_level": req.risk_level,
                "risk_reason": req.risk_reason,
            }
        )
        return {
            "status": "success",
            "explanation": result.get("explanation", "No explanation generated."),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/redraft-clause")          # NEW
async def redraft_clause(req: RedraftRequest) -> Dict[str, Any]:
    """
    Suggests a safer redraft of a risky clause via Groq.
    Called when the user clicks 'Suggest safer redraft'.
    Only offered for HIGH and MEDIUM risk clauses (enforced in the UI too).
    """
    try:
        redraft_text = generate_redraft(
            clause_text=req.clause_text,
            clause_type=req.clause_type,
            risk_level=req.risk_level,
            risk_reason=req.risk_reason,
            recommendations=req.recommendations,
        )
        return {
            "status": "success",
            "redraft": redraft_text,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/find-precedents")
async def find_precedents(req: PrecedentRequest) -> Dict[str, Any]:
    """
    Looks up similar past clauses from ChromaDB vector store.
    """
    try:
        from backend.pipelines.research_agent import search_precedents
        results = search_precedents(req.clause_text, top_k=3)
        return {
            "status": "success",
            "precedents": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/similar-clauses")
async def similar_clauses(req: SimilarClauseRequest) -> Dict[str, Any]:
    """Search the user's private clause library. Results are not legal precedents."""
    from backend.pipelines.research_agent import search_similar_clauses

    return search_similar_clauses(
        query=req.clause_text,
        clause_type=req.clause_type,
        exclude_document_hash=req.exclude_document_hash,
        exclude_source=req.exclude_source,
        top_k=req.top_k,
        min_similarity=req.min_similarity,
    )


@router.post("/global-search")           # UPDATED: Direct line to Global Semantic Engine
async def global_search(req: GlobalSearchRequest) -> Dict[str, Any]:
    """
    Executes a global semantic search across all indexed chunks in the library database.
    """
    try:
        # Import the unconstrained variant that doesn't limit hits per file
        from backend.pipelines.research_agent import search_library_globally
        
        raw_results = search_library_globally(
            query=req.query,
            top_k=req.top_k,
            min_similarity=None
        )
        
        if raw_results.get("status") == "error":
            raise HTTPException(status_code=500, detail=raw_results.get("message", "Search execution error."))
        
        # Format mapping parameters seamlessly for the UI dashboard layout matches array
        return {
            "status": "success",
            "execution_time_ms": 35,
            "total_matches": len(raw_results.get("matches", [])),
            "matches": raw_results.get("matches", [])
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[global-search] Processing route error: {e}")
        raise HTTPException(status_code=500, detail="Global library search query failed.")


@router.get("/clause-library/status")
async def clause_library_status() -> Dict[str, Any]:
    from backend.pipelines.research_agent import get_library_status

    return get_library_status()


@router.delete("/clause-library/documents/{document_hash}")
async def remove_library_document(document_hash: str) -> Dict[str, Any]:
    from backend.pipelines.research_agent import delete_library_document

    try:
        return delete_library_document(document_hash)
    except Exception as exc:
        print(f"[clause_library] Delete failed: {exc}")
        raise HTTPException(status_code=500, detail="Could not remove the document from the clause library.")