"""Prepare public curriculum vectors locally instead of embedding them in the cloud."""
from pathlib import Path
import json
import sqlite3
import sys
import faiss
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "ingestion")]
from ul_ingest.curriculum_index import snapshot_documents, embedding_inputs
from app.rag.embeddings import get_embedder
from app.rag.embedding_cache import embedding_key


def main():
    embedder = get_embedder()
    output = sqlite3.connect(ROOT / "data/embedding_seed.sqlite3")
    known = {r[0] for r in output.execute("SELECT key FROM embedding_cache WHERE model=? AND dim=?", (embedder.name, embedder.dim))}
    pending = {}
    for doc in snapshot_documents():
        for text in embedding_inputs(doc):
            key = embedding_key(embedder.name, text)
            if key not in known: pending[key] = text
    items = list(pending.items())
    print(json.dumps({"new_public_vectors": len(items), "device": embedder.device}), flush=True)
    for start in range(0, len(items), 128):
        batch = items[start:start + 128]; vectors = embedder.encode([t for _, t in batch])
        output.executemany("INSERT OR IGNORE INTO embedding_cache VALUES (?,?,?,?)", [(k, embedder.name, embedder.dim, np.asarray(v, dtype='<f4').tobytes()) for (k, _), v in zip(batch, vectors)])
        output.commit(); print(json.dumps({"prepared": min(start + 128, len(items)), "total": len(items)}), flush=True)
    output.close()


if __name__ == "__main__": main()
