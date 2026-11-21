"""Content-addressed embedding persistence; the SQLite replica is the source of truth.

Keys bind model name and exact model input. They remain correct when chunk IDs change.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

import numpy as np
from sqlalchemy import delete, select

from ..db import EmbeddingCache, session_scope


def embedding_key(model: str, text: str) -> str:
    return hashlib.sha256((model + '\0' + text).encode('utf-8')).hexdigest()


def decode_vector(blob: bytes, dim: int):
    if len(blob) != dim * 4:
        return None
    value = np.frombuffer(blob, dtype='<f4')
    return value if np.isfinite(value).all() else None


def cached_vectors(db, keys, model, dim):
    rows = db.scalars(select(EmbeddingCache).where(EmbeddingCache.key.in_(keys)))
    out = {}
    for row in rows:
        value = decode_vector(row.vector, dim) if row.dim == dim and row.model == model else None
        if value is not None:
            out[row.key] = value
    return out


def save_vectors(db, vectors, model, dim):
    if not vectors:
        return
    db.execute(delete(EmbeddingCache).where(EmbeddingCache.key.in_(vectors)))
    db.add_all([EmbeddingCache(key=key, model=model, dim=dim,
                              vector=np.asarray(vec, dtype='<f4').tobytes())
                for key, vec in vectors.items()])
    db.flush()


def import_seed_embeddings(model, dim, path=None):
    """Seed only derived public-source vectors; never replace the restored database."""
    path = Path(path or os.environ.get('EMBEDDING_SEED_DB', '/app/seed/embedding_seed.sqlite3'))
    if not path.exists():
        return 0
    added = 0
    with sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True) as source:
        cursor = source.execute('SELECT key,vector FROM embedding_cache WHERE model=? AND dim=?', (model, dim))
        while rows := cursor.fetchmany(256):
            with session_scope() as db:
                known = cached_vectors(db, [r[0] for r in rows], model, dim)
                missing = {key: value for key, blob in rows
                           if key not in known and (value := decode_vector(blob, dim)) is not None}
                save_vectors(db, missing, model, dim)
                added += len(missing)
    return added
