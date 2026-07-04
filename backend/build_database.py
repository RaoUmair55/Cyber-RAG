"""
Phase 1: Build the vector database.

Loads savaniDhruv/Cybersecurity_Attack_Dataset from Hugging Face,
turns each row into one searchable document, embeds it with
Sentence Transformers, and stores everything in a persistent
ChromaDB collection.

Run this once (or whenever the dataset changes):
    python embeddings/build_database.py
"""

import os
import chromadb
from datasets import load_dataset
from sentence_transformers import SentenceTransformer

# ---- Config ----------------------------------------------------------
DATASET_NAME = "savaniDhruv/Cybersecurity_Attack_Dataset"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
COLLECTION_NAME = "cyber_attacks"
BATCH_SIZE = 64

# Columns in the dataset. Adjust here if the schema changes and
# nothing else in this file needs to be touched.
COLUMNS = [
    "ID", "Title", "Category", "Attack Type", "Scenario Description",
    "Attack Steps", "Tools Used", "Target Type", "Vulnerability",
    "MITRE Technique", "Impact", "Detection Method", "Solution",
    "Tags", "Source",
]


def clean_value(v) -> str:
    """Turn a possibly-missing cell into clean display text."""
    if v is None:
        return "Not specified"
    s = str(v).strip()
    if s == "" or s.lower() == "nan":
        return "Not specified"
    return s


def row_to_document(row: dict) -> str:
    """
    Convert one dataset row into a single text block that reads
    naturally and embeds well. Field labels help the embedding
    model anchor on structure without hurting semantic quality.
    """
    return (
        f"Title: {clean_value(row.get('Title'))}\n"
        f"Category: {clean_value(row.get('Category'))}\n"
        f"Attack Type: {clean_value(row.get('Attack Type'))}\n\n"
        f"Scenario Description:\n{clean_value(row.get('Scenario Description'))}\n\n"
        f"Attack Steps:\n{clean_value(row.get('Attack Steps'))}\n\n"
        f"Tools Used: {clean_value(row.get('Tools Used'))}\n"
        f"Target Type: {clean_value(row.get('Target Type'))}\n"
        f"Vulnerability: {clean_value(row.get('Vulnerability'))}\n"
        f"MITRE Technique: {clean_value(row.get('MITRE Technique'))}\n\n"
        f"Impact:\n{clean_value(row.get('Impact'))}\n\n"
        f"Detection Method:\n{clean_value(row.get('Detection Method'))}\n\n"
        f"Solution:\n{clean_value(row.get('Solution'))}\n\n"
        f"Tags: {clean_value(row.get('Tags'))}"
    )


def build():
    print(f"Loading dataset: {DATASET_NAME} ...")
    ds = load_dataset(DATASET_NAME)
    # Most HF datasets expose a single 'train' split for this kind of data.
    split = "train" if "train" in ds else list(ds.keys())[0]
    rows = ds[split]
    print(f"Loaded {len(rows)} rows from split '{split}'.")

    print(f"Loading embedding model: {EMBED_MODEL_NAME} ...")
    model = SentenceTransformer(EMBED_MODEL_NAME)

    print("Setting up ChromaDB ...")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    # Fresh build each run so re-running this script is always safe.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    documents, metadatas, ids = [], [], []

    for i, row in enumerate(rows):
        doc_id = clean_value(row.get("ID"))
        if doc_id == "Not specified":
            doc_id = f"row-{i}"

        documents.append(row_to_document(row))
        metadatas.append({
            "id": doc_id,
            "title": clean_value(row.get("Title")),
            "category": clean_value(row.get("Category")),
            "attack_type": clean_value(row.get("Attack Type")),
            "target_type": clean_value(row.get("Target Type")),
            "vulnerability": clean_value(row.get("Vulnerability")),
            "mitre_technique": clean_value(row.get("MITRE Technique")),
            "tags": clean_value(row.get("Tags")),
            "source": clean_value(row.get("Source")),
        })
        ids.append(f"doc-{i}-{doc_id}")

    print(f"Embedding {len(documents)} documents in batches of {BATCH_SIZE} ...")
    for start in range(0, len(documents), BATCH_SIZE):
        end = start + BATCH_SIZE
        batch_docs = documents[start:end]
        batch_embeds = model.encode(batch_docs, show_progress_bar=False).tolist()

        collection.add(
            documents=batch_docs,
            embeddings=batch_embeds,
            metadatas=metadatas[start:end],
            ids=ids[start:end],
        )
        print(f"  stored {min(end, len(documents))}/{len(documents)}")

    print(f"\nDone. Collection '{COLLECTION_NAME}' has {collection.count()} documents.")
    print(f"Stored at: {os.path.abspath(CHROMA_PATH)}")


if __name__ == "__main__":
    build()
