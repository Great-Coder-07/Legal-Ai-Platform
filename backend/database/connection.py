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

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ChromaDB is optional and initialized lazily. A vector-store disk problem
# should not prevent the API or non-retrieval features from starting.
_chroma_client = None
_vector_collections = {}


def get_vector_collection(collection_name: str | None = None):
    global _chroma_client
    name = collection_name or os.getenv("CHROMA_COLLECTION_NAME", "legal_clauses_v2")
    if name not in _vector_collections:
        default_path = (
            Path(os.getenv("LOCALAPPDATA", Path.home()))
            / "LegalAIPlatform"
            / "chroma_db"
        )
        chroma_path = os.getenv("CHROMA_DB_PATH", str(default_path))
        if _chroma_client is None:
            _chroma_client = chromadb.PersistentClient(path=chroma_path)
        metadata = {"hnsw:space": "cosine"} if name == "legal_clauses_v2" else None
        _vector_collections[name] = _chroma_client.get_or_create_collection(
            name=name,
            metadata=metadata,
        )
    return _vector_collections[name]
