"""
Long-term memory for Assistant Mode.

Three ways knowledge gets in here:
  1. Auto-extraction — after a general-assistant exchange, ask the LLM
     whether anything durable is worth remembering (name, preference,
     ongoing project, decision, deadline, etc.) and store it if so.
  2. Manual teaching — you tell it something directly.
  3. File ingestion — upload a note/doc/code file, it gets chunked and
     stored so it can be retrieved later.

Everything lives in two ChromaDB collections, separate from the cyber
attack dataset and the pentest Vault:
  - "memory"    short factual/preference snippets
  - "documents" chunks of uploaded files

Nothing here trains or modifies the underlying LLM. This is retrieval,
not fine-tuning — the same pattern as the rest of the project, just
pointed at your own knowledge instead of a public dataset.
"""

import os
import re
import uuid
import json
from datetime import datetime, timezone

import chromadb
from sentence_transformers import SentenceTransformer
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

_embed_model = None
_memory_collection = None
_documents_collection = None
_groq_client = None


def get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


def get_memory_collection():
    global _memory_collection
    if _memory_collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        _memory_collection = client.get_or_create_collection(
            name="memory", metadata={"hnsw:space": "cosine"}
        )
    return _memory_collection


def get_documents_collection():
    global _documents_collection
    if _documents_collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        _documents_collection = client.get_or_create_collection(
            name="documents", metadata={"hnsw:space": "cosine"}
        )
    return _documents_collection


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set.")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


# ------------------------------------------------------------------ #
# Manual + auto memory (short facts/preferences)
# ------------------------------------------------------------------ #

def add_memory(text: str, source: str = "manual") -> dict:
    """source: 'manual' | 'auto' | 'file'"""
    if not text.strip():
        raise ValueError("memory text cannot be empty")

    collection = get_memory_collection()
    model = get_embed_model()
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    collection.add(
        documents=[text.strip()],
        embeddings=model.encode([text.strip()]).tolist(),
        metadatas=[{"source": source, "created_at": now}],
        ids=[entry_id],
    )
    return {"id": entry_id, "text": text.strip(), "source": source, "created_at": now}


def delete_memory(entry_id: str) -> None:
    get_memory_collection().delete(ids=[entry_id])


def list_memory(limit: int = 100) -> list[dict]:
    collection = get_memory_collection()
    results = collection.get(include=["documents", "metadatas"])
    items = [
        {"id": i, "text": d, **m}
        for i, d, m in zip(results["ids"], results["documents"], results["metadatas"])
    ]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items[:limit]


def search_memory(query: str, top_k: int = 5) -> list[dict]:
    collection = get_memory_collection()
    if collection.count() == 0:
        return []
    model = get_embed_model()
    results = collection.query(
        query_embeddings=model.encode([query]).tolist(),
        n_results=min(top_k, collection.count()),
    )
    hits = []
    for doc, meta, doc_id, dist in zip(
        results["documents"][0], results["metadatas"][0], results["ids"][0], results["distances"][0]
    ):
        hits.append({"id": doc_id, "text": doc, "similarity": round(1 - dist, 4), **meta})
    return hits


EXTRACTION_PROMPT = """You extract durable facts worth remembering long-term from a single \
conversation exchange, the same way a personal assistant would build up memory of a person \
over time.

Only extract things that are:
- Stable facts about the person (name, role, ongoing projects, tools/stack they use, preferences)
- Concrete commitments (deadlines, decisions made, plans)

Do NOT extract:
- One-off questions or requests with no lasting relevance
- Anything already generic/obvious
- Speculative or uncertain information

Respond with ONLY a JSON array of short strings, each one fact, third person, e.g.:
["User is building a FYP called IntegrityFlow using Electron.js", "User prefers concise answers"]

If there is nothing worth remembering, respond with exactly: []

Conversation exchange:
User: {user_msg}
Assistant: {assistant_msg}
"""


def extract_facts(user_msg: str, assistant_msg: str) -> list[str]:
    """Ask the LLM if anything in this exchange is worth remembering.
    Returns a list of fact strings (possibly empty). Never raises on
    malformed output — worst case it just remembers nothing this turn."""
    client = get_groq_client()
    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{
                "role": "user",
                "content": EXTRACTION_PROMPT.format(user_msg=user_msg, assistant_msg=assistant_msg),
            }],
            temperature=0,
            max_tokens=300,
        )
        raw = completion.choices[0].message.content.strip()
        raw = re.sub(r"^```json|```$", "", raw, flags=re.MULTILINE).strip()
        facts = json.loads(raw)
        if isinstance(facts, list):
            return [f for f in facts if isinstance(f, str) and f.strip()]
    except Exception:
        pass
    return []


def remember_exchange(user_msg: str, assistant_msg: str) -> list[dict]:
    """Extract + store in one call. Returns what got saved (may be empty)."""
    facts = extract_facts(user_msg, assistant_msg)
    return [add_memory(f, source="auto") for f in facts]


# ------------------------------------------------------------------ #
# File ingestion (notes, docs, code -> chunked, embedded, searchable)
# ------------------------------------------------------------------ #

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Simple sliding-window chunker on characters. Good enough for
    notes/code/docs without pulling in a heavier splitter dependency."""
    text = text.strip()
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def ingest_file(filename: str, content: str) -> dict:
    if not content.strip():
        raise ValueError("file content is empty")

    chunks = chunk_text(content)
    if not chunks:
        raise ValueError("nothing to ingest after chunking")

    collection = get_documents_collection()
    model = get_embed_model()
    now = datetime.now(timezone.utc).isoformat()

    ids = [str(uuid.uuid4()) for _ in chunks]
    embeddings = model.encode(chunks).tolist()
    metadatas = [
        {"filename": filename, "chunk_index": i, "created_at": now}
        for i in range(len(chunks))
    ]

    collection.add(documents=chunks, embeddings=embeddings, metadatas=metadatas, ids=ids)
    return {"filename": filename, "chunks_stored": len(chunks)}


def search_documents(query: str, top_k: int = 5) -> list[dict]:
    collection = get_documents_collection()
    if collection.count() == 0:
        return []
    model = get_embed_model()
    results = collection.query(
        query_embeddings=model.encode([query]).tolist(),
        n_results=min(top_k, collection.count()),
    )
    hits = []
    for doc, meta, doc_id, dist in zip(
        results["documents"][0], results["metadatas"][0], results["ids"][0], results["distances"][0]
    ):
        hits.append({"id": doc_id, "text": doc, "similarity": round(1 - dist, 4), **meta})
    return hits


def list_files() -> list[dict]:
    """Distinct filenames with chunk counts, for a file-list UI."""
    collection = get_documents_collection()
    results = collection.get(include=["metadatas"])
    counts = {}
    for m in results["metadatas"]:
        counts[m["filename"]] = counts.get(m["filename"], 0) + 1
    return [{"filename": f, "chunks": c} for f, c in counts.items()]


def delete_file(filename: str) -> int:
    collection = get_documents_collection()
    results = collection.get(where={"filename": filename})
    if results["ids"]:
        collection.delete(ids=results["ids"])
    return len(results["ids"])


# ------------------------------------------------------------------ #
# General assistant chat: retrieve memory + docs, then generate
# ------------------------------------------------------------------ #

ASSISTANT_SYSTEM_PROMPT = """You are the user's personal AI assistant. You have long-term \
memory of facts about them (below, if any) and access to documents they've uploaded. Use \
this context naturally, the way someone who knows the person well would — don't announce \
that you're "retrieving memory," just use it. If the context doesn't cover the question, \
answer from general knowledge and say so. Be concise and direct. Format responses in \
markdown when it aids clarity — headers for sections, bullet/numbered lists for steps, \
fenced code blocks for any code or commands, tables for comparisons."""


def chat(message: str, history: list[dict] = None) -> dict:
    history = history or []
    mem_hits = search_memory(message, top_k=5)
    doc_hits = search_documents(message, top_k=3)

    context_parts = []
    if mem_hits:
        context_parts.append("Known facts about the user:\n" + "\n".join(f"- {h['text']}" for h in mem_hits))
    if doc_hits:
        context_parts.append(
            "Relevant excerpts from uploaded files:\n" +
            "\n\n".join(f"[{h['filename']}]\n{h['text']}" for h in doc_hits)
        )
    context = "\n\n".join(context_parts) if context_parts else "(no stored context yet)"

    client = get_groq_client()
    messages = [{"role": "system", "content": f"{ASSISTANT_SYSTEM_PROMPT}\n\n{context}"}]
    messages.extend(history[-10:])
    messages.append({"role": "user", "content": message})

    completion = client.chat.completions.create(
        model=GROQ_MODEL, messages=messages, temperature=0.4, max_tokens=800,
    )
    answer = completion.choices[0].message.content

    saved = remember_exchange(message, answer)

    return {
        "answer": answer,
        "memory_used": [{"text": h["text"], "similarity": h["similarity"]} for h in mem_hits],
        "docs_used": [{"filename": h["filename"], "similarity": h["similarity"]} for h in doc_hits],
        "newly_remembered": [s["text"] for s in saved],
    }
