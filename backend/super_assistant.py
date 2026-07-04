"""
Super Assistant — combines every knowledge source in the project into
one chat:

  - cyber_attacks   the public attack dataset (rag.py)
  - personal_kb     your Vault: commands, notes, payloads (kb.py)
  - memory          auto-remembered + manually taught facts (memory.py)
  - documents       uploaded files, e.g. nmap docs (memory.py)

For each question, it searches all four, keeps whatever's actually
relevant (a similarity floor, not a fixed count from every source),
and lets Groq answer from whatever mix comes back. If you ask about
nmap, it'll pull from documents. If you ask about your FYP, memory.
If you ask about SQL Injection, the attack dataset and maybe your
Vault. One assistant, no need to pick a mode first.
"""

import os
from groq import Groq
from dotenv import load_dotenv

from backend.rag import semantic_search as search_attacks
from backend import kb
from backend import memory

load_dotenv()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

_groq_client = None

# Below this similarity, a hit is probably not actually relevant —
# skip it rather than force irrelevant context into the prompt.
RELEVANCE_FLOOR = 0.25


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not set.")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


def gather_context(question: str, top_k: int = 4) -> dict:
    """Search all four sources, filter by relevance, return grouped hits."""
    attack_hits = [h for h in search_attacks(question, top_k=top_k) if h["similarity"] >= RELEVANCE_FLOOR]
    vault_hits = [h for h in kb.search_entries(question, top_k=top_k) if h["similarity"] >= RELEVANCE_FLOOR]
    memory_hits = [h for h in memory.search_memory(question, top_k=top_k) if h["similarity"] >= RELEVANCE_FLOOR]
    doc_hits = [h for h in memory.search_documents(question, top_k=top_k) if h["similarity"] >= RELEVANCE_FLOOR]
    return {"attacks": attack_hits, "vault": vault_hits, "memory": memory_hits, "documents": doc_hits}


def build_context_block(hits: dict) -> str:
    parts = []

    if hits["attacks"]:
        block = "\n\n".join(f"[Attack: {h['metadata']['title']}]\n{h['document']}" for h in hits["attacks"])
        parts.append(f"=== Cybersecurity attack dataset ===\n{block}")

    if hits["vault"]:
        block = "\n\n".join(f"[Your {h['type']}: {h['title']}]\n{h['content']}" for h in hits["vault"])
        parts.append(f"=== Your personal Vault ===\n{block}")

    if hits["memory"]:
        block = "\n".join(f"- {h['text']}" for h in hits["memory"])
        parts.append(f"=== What you know about the user ===\n{block}")

    if hits["documents"]:
        block = "\n\n".join(f"[{h['filename']}]\n{h['text']}" for h in hits["documents"])
        parts.append(f"=== Uploaded reference documents ===\n{block}")

    return "\n\n".join(parts) if parts else "(no matching stored context — answer from general knowledge)"


SYSTEM_PROMPT = """You are the user's unified personal assistant, combining cybersecurity/pentesting \
knowledge with general assistance. You have access to a public attack dataset, the user's own \
pentesting Vault (commands/notes/payloads), long-term memory of facts about them, and any reference \
documents they've uploaded (e.g. tool documentation).

Use whichever of these sources is actually relevant to the question — don't force irrelevant \
context in. If nothing stored is relevant, just answer from general knowledge and say so. When you \
do use stored context, make clear what it's based on (e.g. "based on the nmap docs you uploaded..." \
or "from your notes on this..."). Be direct and concise. Format responses in markdown when it aids \
clarity — headers for sections, lists for steps, fenced code blocks for commands/payloads, tables \
for comparisons."""


def chat(message: str, history: list[dict] = None) -> dict:
    history = history or []
    hits = gather_context(message)
    context = build_context_block(hits)

    client = get_groq_client()
    messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{context}"}]
    messages.extend(history[-10:])
    messages.append({"role": "user", "content": message})

    completion = client.chat.completions.create(
        model=GROQ_MODEL, messages=messages, temperature=0.3, max_tokens=900,
    )
    answer = completion.choices[0].message.content

    # Same auto-memory growth as Assistant Mode.
    saved = memory.remember_exchange(message, answer)

    return {
        "answer": answer,
        "sources": {
            "attacks": [{"title": h["metadata"]["title"], "similarity": h["similarity"]} for h in hits["attacks"]],
            "vault": [{"title": h["title"], "type": h["type"], "similarity": h["similarity"]} for h in hits["vault"]],
            "memory": [{"text": h["text"], "similarity": h["similarity"]} for h in hits["memory"]],
            "documents": [{"filename": h["filename"], "similarity": h["similarity"]} for h in hits["documents"]],
        },
        "newly_remembered": [s["text"] for s in saved],
    }
