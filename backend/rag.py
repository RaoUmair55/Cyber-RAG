"""
Phase 2: Retrieval-Augmented Generation.

Searches the ChromaDB collection built by embeddings/build_database.py,
assembles the retrieved records into context, and asks Groq's LLM to
answer using ONLY that context.
"""

import os
import chromadb
from sentence_transformers import SentenceTransformer
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
COLLECTION_NAME = "cyber_attacks"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ---- Lazy-loaded singletons (avoid reloading the model per request) --
_embed_model = None
_chroma_collection = None
_groq_client = None


def get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    return _embed_model


def get_collection():
    global _chroma_collection
    if _chroma_collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        _chroma_collection = client.get_collection(COLLECTION_NAME)
    return _chroma_collection


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Copy .env.example to .env and add your key."
            )
        _groq_client = Groq(api_key=api_key)
    return _groq_client


def semantic_search(query: str, top_k: int = 5, where: dict | None = None) -> list[dict]:
    """
    Embed the query and return the top_k most similar records.
    `where` can filter by metadata, e.g. {"category": "Web Application"}.
    """
    model = get_embed_model()
    collection = get_collection()

    query_embedding = model.encode([query]).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        where=where,
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        hits.append({
            "document": doc,
            "metadata": meta,
            "similarity": round(1 - dist, 4),  # cosine distance -> similarity
        })
    return hits


def build_context(hits: list[dict]) -> str:
    """Join retrieved documents into one context block for the LLM."""
    blocks = []
    for i, hit in enumerate(hits, start=1):
        blocks.append(f"[Record {i}]\n{hit['document']}")
    return "\n\n---\n\n".join(blocks)


SYSTEM_PROMPT = (
    "You are a cybersecurity assistant. Answer the user's question using "
    "ONLY the information in the provided context records. Do not use "
    "outside knowledge. If the context does not contain enough information "
    "to answer, say so clearly instead of guessing. Be concise, use bullet "
    "points where useful, and reference which attack(s) your answer is "
    "based on."
)


def ask_groq(question: str, context: str) -> str:
    client = get_groq_client()
    completion = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}",
            },
        ],
        temperature=0.2,
        max_tokens=800,
    )
    return completion.choices[0].message.content


def answer_question(question: str, top_k: int = 5, where: dict | None = None, include_vault: bool = True) -> dict:
    """
    Full RAG pipeline: retrieve -> build context -> generate grounded answer.
    If include_vault is True, also pulls relevant entries from your personal
    Vault (backend/kb.py) so past notes/commands surface alongside the
    public dataset — e.g. "here's how SQLi works, and here's the payload
    you used last time."
    Returns the answer plus the source records used, for citation in the UI.
    """
    hits = semantic_search(question, top_k=top_k, where=where)

    vault_hits = []
    if include_vault:
        try:
            from backend import kb
            vault_hits = kb.search_entries(question, top_k=3)
        except Exception:
            vault_hits = []

    if not hits and not vault_hits:
        return {
            "answer": "I couldn't find any relevant attacks in the dataset for this question.",
            "sources": [],
            "vault_sources": [],
        }

    context = build_context(hits)
    if vault_hits:
        vault_block = "\n\n---\n\n".join(
            f"[Your Vault: {v['type']}] {v['title']}\n{v['content']}" for v in vault_hits
        )
        context = f"{context}\n\n=== Your personal notes on related topics ===\n\n{vault_block}" if context else vault_block

    answer = ask_groq(question, context)

    sources = [
        {
            "title": h["metadata"]["title"],
            "attack_type": h["metadata"]["attack_type"],
            "category": h["metadata"]["category"],
            "similarity": h["similarity"],
        }
        for h in hits
    ]
    vault_sources = [
        {"title": v["title"], "type": v["type"], "similarity": v["similarity"]}
        for v in vault_hits
    ]

    return {"answer": answer, "sources": sources, "vault_sources": vault_sources}


if __name__ == "__main__":
    # Quick manual test: python backend/rag.py
    q = "How does SQL Injection work and how can it be detected?"
    result = answer_question(q)
    print("ANSWER:\n", result["answer"])
    print("\nSOURCES:")
    for s in result["sources"]:
        print(f"  - {s['title']} ({s['attack_type']}) sim={s['similarity']}")
