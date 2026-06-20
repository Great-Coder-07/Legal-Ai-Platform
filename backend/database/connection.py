import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import chromadb

# PostgreSQL config (Fallback to SQLite for local ease if not provided)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./legal_ai.db")

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 🟢 Unified Base: Shared across models.py and app instantiation scripts
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ChromaDB optional/lazy thread management mapping layout
_chroma_client = None
_vector_collections = {}


def get_vector_collection(collection_name: str | None = None):
    global _chroma_client
    name = collection_name or os.getenv("CHROMA_COLLECTION_NAME", "legal_clauses_v2")
    
    if name not in _vector_collections:
        # Pinned relative to backend app root tree layout workspace cleanly
        default_path = Path(__file__).resolve().parent.parent.parent / "chroma_db"
        chroma_path = os.getenv("CHROMA_DB_PATH", str(default_path))
        
        if _chroma_client is None:
            _chroma_client = chromadb.PersistentClient(path=chroma_path)
            
        metadata = {"hnsw:space": "cosine"} if name == "legal_clauses_v2" else None
        _vector_collections[name] = _chroma_client.get_or_create_collection(
            name=name,
            metadata=metadata,
        )
    return _vector_collections[name]