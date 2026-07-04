# Cyber-RAG — RAG-based Cybersecurity Assistant

Semantic search + Groq LLM over the `savaniDhruv/Cybersecurity_Attack_Dataset`
(14.1k attack records: SQL Injection, XSS, ransomware, phishing, etc.)

## Setup

```bash
cd Cyber-RAG
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then paste your Groq key into .env
```

Get a free Groq API key: https://console.groq.com/keys

## Phase 1 — Build the vector database

This downloads the dataset from Hugging Face, embeds every row, and
stores it in a local ChromaDB folder (`chroma_db/`). Only needs to be
run once.

```bash
python embeddings/build_database.py
```

You should see progress logs and a final count of ~14,100 documents stored.

## Phase 2 — Quick sanity check (no server needed)

```bash
python backend/rag.py
```

This runs one hardcoded question through the full RAG pipeline and prints
the answer + sources, so you can confirm retrieval + Groq are both wired
up correctly before building the API on top.

## Phase 3 — Run the API

```bash
uvicorn backend.app:app --reload --port 8000
```

Then open http://localhost:8000/docs for interactive Swagger docs. Try:

- `POST /ask` — `{"question": "How does SQL Injection work?"}`
- `GET /search?q=phishing email attack`
- `GET /filters` — dropdown values for the frontend
- `GET /stats` — counts for dashboard charts

## Phase 4 — React frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Make sure `uvicorn backend.app:app --reload --port 8000`
is still running in another terminal — the frontend calls it directly at
`http://localhost:8000`.

**Design direction:** built as a SOC-style query console rather than a generic
chat UI — graphite/mono aesthetic, amber for your query, phosphor green for
confirmed retrieval matches. Left rail shows live index stats and lets you
filter by category/attack type/target type before asking. Each answer shows
a "matched records" strip with per-source similarity meters so you can see
exactly what grounded the response.

## Phase 5 — Personal Vault (pentesting/bug bounty notes)

A second tab in the same app, backed by its own ChromaDB collection
(`personal_kb`), completely separate from the attack dataset. Store your
own:

- **Commands** — tool syntax, flags, one-liners you use often
- **Notes** — engagement scope, findings, progress
- **Payloads** — reusable techniques you've personally tested

Everything is embedded and semantically searchable the same way as the
main dataset, so you can ask "how did I handle rate limiting last time?"
and get back the actual note you wrote, not a generic answer. Filter by
type or phase (recon/enumeration/exploitation/post-exploitation/reporting).

This is 100% local — stored in `chroma_db/` on your machine, nothing
synced anywhere. No setup needed beyond what you already did; the new
`/kb/*` endpoints are part of the same FastAPI server.

## Phase 6 — Assistant Mode + growing memory

A second **mode** (not just a tab) — switch between Cyber Mode and
Assistant Mode from the sidebar. Assistant Mode is a general-purpose
personal assistant with its own long-term memory that grows as you use it.

**Important — how "learning" actually works here:** this does not retrain
the underlying LLM (Llama on Groq). No personal project retrains a
foundation model — that's what Anthropic/OpenAI do in massive offline runs.
What actually happens, and what "ChatGPT/Claude feeling smarter over time"
really is: **memory + retrieval**. Facts get saved, then retrieved and fed
back into context on future questions. That's exactly what's built here:

- **Auto-remembering** — after each exchange in Assistant Mode, Groq checks
  whether anything durable is worth keeping (a preference, a project, a
  deadline) and saves it if so — same idea as how I (Claude) build memory
  of you across conversations.
- **Manual teaching** — type something directly into the Memory tab and
  it's saved immediately.
- **File uploads** — drop in `.txt`, `.md`, `.py`, `.js`, `.json`, `.csv`
  files; they get chunked and embedded so you can ask questions about them
  later.
- **Cyber Mode also got smarter** — `/ask` now pulls from your Vault too,
  so answers can surface your own past notes alongside the dataset.

New endpoints: `/assistant/chat`, `/memory/teach`, `/memory/list`,
`/memory/{id}` (DELETE), `/memory/upload`, `/memory/files`.

No new setup — same `chroma_db/`, same Groq key, just restart uvicorn.

## Phase 7 — Super Assistant (everything combined)

A third mode that searches all four knowledge sources at once — attack
dataset, Vault, memory, and uploaded documents — and blends whatever's
actually relevant, so you don't have to pick a mode first. Ask about an
attack, a tool you uploaded docs for, your own notes, or just talk
normally; it figures out which sources apply per question.

Uses a **relevance floor** (similarity ≥ 0.25) so it doesn't force
irrelevant context into every answer — if nothing stored is relevant, it
just answers from general knowledge and says so.

New endpoint: `/super/chat`. Same auto-memory growth as Assistant Mode.
No new setup needed.

### Adding tool docs (e.g. nmap)

Upload via the Memory tab (works in Assistant Mode or Super Mode — same
`documents` collection either way):

```bash
man nmap > nmap_docs.txt
```

Then upload `nmap_docs.txt` through the Memory tab's "+ upload file"
button. It gets chunked and embedded, and Super Assistant (or Assistant
Mode) will pull the relevant sections when you ask nmap-specific
questions.

## Project structure

```
Cyber-RAG/
├── data/                  (not used directly — dataset streams from HF)
├── embeddings/
│   └── build_database.py  Phase 1: dataset -> embeddings -> ChromaDB
├── backend/
│   ├── rag.py              Phase 2: semantic search + Groq generation
│   └── app.py               Phase 3: FastAPI endpoints
├── chroma_db/               generated by Phase 1, gitignore this
├── frontend/                Phase 4: React app (TBD)
├── requirements.txt
└── .env.example
```
