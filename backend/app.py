"""
Phase 3: FastAPI backend.

Run with:
    uvicorn backend.app:app --reload --port 8000
"""

from collections import Counter
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.rag import answer_question, semantic_search, get_collection
from backend import kb

app = FastAPI(title="Cyber-RAG API", version="1.0.0")

# Allow the React dev server to call this API. Tighten this before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    top_k: int = 5
    category: Optional[str] = None
    attack_type: Optional[str] = None
    target_type: Optional[str] = None


@app.get("/")
def root():
    return {"status": "ok", "message": "Cyber-RAG API is running."}


@app.post("/ask")
def ask(req: AskRequest):
    """Main RAG endpoint: ask a natural-language question, get a grounded answer."""
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    where = None
    filters = {}
    if req.category:
        filters["category"] = req.category
    if req.attack_type:
        filters["attack_type"] = req.attack_type
    if req.target_type:
        filters["target_type"] = req.target_type
    if len(filters) == 1:
        where = filters
    elif len(filters) > 1:
        where = {"$and": [{k: v} for k, v in filters.items()]}

    try:
        result = answer_question(req.question, top_k=req.top_k, where=where)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


@app.get("/search")
def search(q: str = Query(..., min_length=1), top_k: int = 5):
    """Raw semantic search without LLM generation — useful for quick lookups."""
    hits = semantic_search(q, top_k=top_k)
    return {"query": q, "results": hits}


@app.get("/filters")
def filters():
    """Unique values for building dropdown filters in the frontend."""
    collection = get_collection()
    all_meta = collection.get(include=["metadatas"])["metadatas"]

    def unique_sorted(key: str):
        return sorted({m[key] for m in all_meta if m.get(key) and m[key] != "Not specified"})

    return {
        "categories": unique_sorted("category"),
        "attack_types": unique_sorted("attack_type"),
        "target_types": unique_sorted("target_type"),
    }


@app.get("/stats")
def stats():
    """Aggregate counts for the dashboard charts."""
    collection = get_collection()
    all_meta = collection.get(include=["metadatas"])["metadatas"]

    def top_counts(key: str, n: int = 10):
        counts = Counter(m[key] for m in all_meta if m.get(key) and m[key] != "Not specified")
        return [{"label": k, "count": v} for k, v in counts.most_common(n)]

    return {
        "total_records": len(all_meta),
        "top_categories": top_counts("category"),
        "top_attack_types": top_counts("attack_type"),
        "top_target_types": top_counts("target_type"),
    }


@app.get("/attack/{doc_id}")
def get_attack(doc_id: str):
    """Fetch one full record by its dataset ID."""
    collection = get_collection()
    results = collection.get(where={"id": doc_id}, include=["documents", "metadatas"])
    if not results["ids"]:
        raise HTTPException(status_code=404, detail=f"No record with ID {doc_id}")
    return {
        "id": doc_id,
        "document": results["documents"][0],
        "metadata": results["metadatas"][0],
    }


# ---------------------------------------------------------------------
# Personal Vault — your own commands, engagement notes, payload library.
# Separate ChromaDB collection, local-only, never mixed with the
# public attack dataset above.
# ---------------------------------------------------------------------

class KBEntryRequest(BaseModel):
    type: str          # command | note | payload
    title: str
    content: str
    tags: str = ""
    phase: str = "general"   # recon | enumeration | exploitation | post-exploitation | reporting | general
    target: str = ""


class KBUpdateRequest(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[str] = None
    phase: Optional[str] = None
    target: Optional[str] = None


@app.post("/kb/add")
def kb_add(req: KBEntryRequest):
    try:
        return kb.add_entry(
            entry_type=req.type, title=req.title, content=req.content,
            tags=req.tags, phase=req.phase, target=req.target,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/kb/{entry_id}")
def kb_update(entry_id: str, req: KBUpdateRequest):
    try:
        return kb.update_entry(entry_id, **req.model_dump())
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/kb/{entry_id}")
def kb_delete(entry_id: str):
    kb.delete_entry(entry_id)
    return {"deleted": entry_id}


@app.get("/kb/search")
def kb_search(q: str = Query(..., min_length=1), top_k: int = 8,
              type: Optional[str] = None, phase: Optional[str] = None):
    return {"query": q, "results": kb.search_entries(q, top_k=top_k, entry_type=type, phase=phase)}


@app.get("/kb/list")
def kb_list(type: Optional[str] = None, phase: Optional[str] = None, limit: int = 50):
    return {"results": kb.list_entries(entry_type=type, phase=phase, limit=limit)}
