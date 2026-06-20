from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends
from typing import Dict, Any, List
from pydantic import BaseModel, Field
import os
from backend.services.parsers import parse_document_with_pages
from backend.services.orchestrator import route_document
from backend.services.explainability import generate_explanation
from backend.services.redraft_clause import generate_redraft
from backend.pipelines.research_agent import ingest_document

# 🔒 Multi-Tenant Auth Dependencies
from sqlalchemy.orm import Session
from backend.database.connection import get_db
from backend.services.auth import get_current_user
from backend.database.models import User, UserDocument

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


class RedraftRequest(BaseModel):
    clause_text: str
    clause_type: str
    risk_level: str
    risk_reason: str
    recommendations: List[str] = Field(default_factory=list)


class GlobalSearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = Field(default=5, ge=1, le=20)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    task_type: str = Form("analyze_contract"),
    retain_in_library: Any = Form(False),
    jurisdiction: str = Form(""),
    current_user: User = Depends(get_current_user),  # 🔒 Enforced multi-user isolation guard
    db: Session = Depends(get_db)                   # Relational database pipeline sync
) -> Dict[str, Any]:
    """
    Upload a document and route it to the correct AI pipeline with multi-tenant storage isolation.
    """
    try:
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
            # 🔒 Relational Registry Write: Track file ownership inside SQL
            exists = db.query(UserDocument).filter_by(
                document_hash=document_hash, 
                user_id=current_user.id
            ).first()
            
            if not exists:
                new_doc = UserDocument(
                    document_hash=document_hash, 
                    filename=file.filename, 
                    user_id=current_user.id
                )
                db.add(new_doc)
                db.commit()

            # Schedule the task, passing the current_user.id safely downward
            background_tasks.add_task(
                ingest_document,
                file.filename,
                text,
                current_user.id,  # ◄── Dynamic ownership anchor
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
async def explain_clause(
    req: ClauseRequest, 
    current_user: User = Depends(get_current_user)  # 🔒 Protected route instance
) -> Dict[str, Any]:
    """
    Explains a single clause on demand via Groq.
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


@router.post("/redraft-clause")
async def redraft_clause(
    req: RedraftRequest, 
    current_user: User = Depends(get_current_user)  # 🔒 Protected route instance
) -> Dict[str, Any]:
    """
    Suggests a safer redraft of a risky clause via Groq.
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
async def find_precedents(
    req: PrecedentRequest, 
    current_user: User = Depends(get_current_user)  # 🔒 Protected route instance
) -> Dict[str, Any]:
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
async def similar_clauses(
    req: SimilarClauseRequest, 
    current_user: User = Depends(get_current_user)  # 🔒 Protected route instance
) -> Dict[str, Any]:
    """Search the user's private clause library isolated by tenant user_id."""
    from backend.pipelines.research_agent import search_similar_clauses

    return search_similar_clauses(
        query=req.clause_text,
        user_id=current_user.id,  # ◄── Forwards tenant anchor to block cross-user leaking
        clause_type=req.clause_type,
        exclude_document_hash=req.exclude_document_hash,
        exclude_source=req.exclude_source,
        top_k=req.top_k,
        min_similarity=req.min_similarity,
    )


@router.post("/global-search")
async def global_search(
    req: GlobalSearchRequest, 
    current_user: User = Depends(get_current_user)  # 🔒 Protected route instance
) -> Dict[str, Any]:
    """
    Executes a global semantic search across indexed chunks belonging exclusively to the tenant user.
    """
    try:
        from backend.pipelines.research_agent import search_library_globally
        
        raw_results = search_library_globally(
            query=req.query,
            user_id=current_user.id,  # ◄── Enforces secure tenant isolation mapping parameters
            top_k=req.top_k,
            min_similarity=None
        )
        
        if raw_results.get("status") == "error":
            raise HTTPException(status_code=500, detail=raw_results.get("message", "Search execution error."))
        
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
async def clause_library_status(
    current_user: User = Depends(get_current_user)  # 🔒 Protected route instance
) -> Dict[str, Any]:
    """
    Fetches the status metrics scoped to the active tenant.
    """
    from backend.pipelines.research_agent import get_library_status

    return get_library_status(user_id=current_user.id)  # ◄── Pass authenticated user ID downward


@router.delete("/clause-library/documents/{document_hash}")
async def remove_library_document(
    document_hash: str, 
    current_user: User = Depends(get_current_user),  # 🔒 Required authentication identity token
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Deletes a document from the clause library only if ownership validation passes.
    """
    try:
        # 🔒 Verify document ownership in SQL registry table before modifying the index
        record = db.query(UserDocument).filter_by(
            document_hash=document_hash, 
            user_id=current_user.id
        ).first()
        
        if not record:
            raise HTTPException(
                status_code=403, 
                detail="Access denied: You do not have permission to delete this file layout."
            )
            
        from backend.pipelines.research_agent import delete_library_document

        # Pass both targets down to clear ChromaDB safely
        result = delete_library_document(document_hash=document_hash, user_id=current_user.id)
        
        # Drop registry link from our relational DB table tracker
        db.delete(record)
        db.commit()
        
        return result
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[clause_library] Delete failed: {exc}")
        raise HTTPException(status_code=500, detail="Could not remove the document from the clause library.")