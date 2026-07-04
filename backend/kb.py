"""
Personal Vault — your own commands, engagement notes, and reusable
payloads/techniques, stored and searched the same way as the attack
dataset (embed -> ChromaDB -> semantic search), but in a separate
collection so it never mixes with the public dataset.

This is local-only storage on your machine (chroma_db/). Nothing here
is sent anywhere except to Groq at question-answering time, and only
the records your search actually retrieves.
"""

import os
import uuid
from datetime import datetime, timezone

import chromadb
from sentence_transformers import SentenceTransformer

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
KB_COLLECTION_NAME = "personal_kb"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

VALID_TYPES = {"command", "note", "payload"}
VALID_PHASES = {"recon", "enumeration", "exploitation", "post-exploitation", "reporting", "general"}

_embed_model = None
_kb_collection = None


def get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


def get_kb_collection():
    global _kb_collection
    if _kb_collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        _kb_collection = client.get_or_create_collection(
            name=KB_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _kb_collection


def _embed_text(entry_type: str, title: str, content: str, tags: str) -> str:
    """What actually gets embedded — title and tags weigh in alongside content
    so a search for 'subdomain enum' matches a command tagged that way even
    if the word 'subdomain' isn't in the command itself."""
    return f"{entry_type} | {title}\nTags: {tags}\n\n{content}"


def add_entry(
    entry_type: str,
    title: str,
    content: str,
    tags: str = "",
    phase: str = "general",
    target: str = "",
) -> dict:
    if entry_type not in VALID_TYPES:
        raise ValueError(f"type must be one of {VALID_TYPES}")
    if phase not in VALID_PHASES:
        phase = "general"
    if not title.strip() or not content.strip():
        raise ValueError("title and content are required")

    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    collection = get_kb_collection()
    model = get_embed_model()
    embedding = model.encode([_embed_text(entry_type, title, content, tags)]).tolist()

    metadata = {
        "type": entry_type,
        "title": title.strip(),
        "tags": tags.strip(),
        "phase": phase,
        "target": target.strip(),
        "created_at": now,
    }

    collection.add(
        documents=[content],
        embeddings=embedding,
        metadatas=[metadata],
        ids=[entry_id],
    )
    return {"id": entry_id, **metadata, "content": content}


def update_entry(entry_id: str, **fields) -> dict:
    collection = get_kb_collection()
    existing = collection.get(ids=[entry_id], include=["documents", "metadatas"])
    if not existing["ids"]:
        raise LookupError(f"No vault entry with id {entry_id}")

    meta = existing["metadatas"][0]
    content = existing["documents"][0]

    for key in ("type", "title", "tags", "phase", "target"):
        if key in fields and fields[key] is not None:
            meta[key] = fields[key]
    if "content" in fields and fields["content"] is not None:
        content = fields["content"]

    model = get_embed_model()
    embedding = model.encode([_embed_text(meta["type"], meta["title"], content, meta["tags"])]).tolist()

    collection.update(
        ids=[entry_id],
        documents=[content],
        embeddings=embedding,
        metadatas=[meta],
    )
    return {"id": entry_id, **meta, "content": content}


def delete_entry(entry_id: str) -> None:
    get_kb_collection().delete(ids=[entry_id])


def search_entries(query: str, top_k: int = 8, entry_type: str = None, phase: str = None) -> list[dict]:
    collection = get_kb_collection()
    if collection.count() == 0:
        return []

    where = None
    conds = []
    if entry_type:
        conds.append({"type": entry_type})
    if phase:
        conds.append({"phase": phase})
    if len(conds) == 1:
        where = conds[0]
    elif len(conds) > 1:
        where = {"$and": conds}

    model = get_embed_model()
    query_embedding = model.encode([query]).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count()),
        where=where,
    )

    hits = []
    for doc, meta, doc_id, dist in zip(
        results["documents"][0], results["metadatas"][0], results["ids"][0], results["distances"][0]
    ):
        hits.append({"id": doc_id, "content": doc, "similarity": round(1 - dist, 4), **meta})
    return hits


def list_entries(entry_type: str = None, phase: str = None, limit: int = 50) -> list[dict]:
    collection = get_kb_collection()
    where = None
    conds = []
    if entry_type:
        conds.append({"type": entry_type})
    if phase:
        conds.append({"phase": phase})
    if len(conds) == 1:
        where = conds[0]
    elif len(conds) > 1:
        where = {"$and": conds}

    results = collection.get(where=where, include=["documents", "metadatas"])
    items = [
        {"id": doc_id, "content": doc, **meta}
        for doc_id, doc, meta in zip(results["ids"], results["documents"], results["metadatas"])
    ]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items[:limit]
