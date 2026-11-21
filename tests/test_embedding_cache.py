from sqlalchemy import select, delete


def test_reconcile_restores_vectors_without_encoding(loaded_index, monkeypatch):
    from ul_ingest.pipeline import reconcile
    expected=loaded_index.store.ids()
    loaded_index.store.reset()
    monkeypatch.setattr(loaded_index.embedder,'encode',lambda *a,**k: (_ for _ in ()).throw(AssertionError('must restore saved vectors')))
    result=reconcile(index=loaded_index)
    assert loaded_index.store.ids()==expected
    assert result['vectors']==len(expected)


def test_cache_keys_bind_model_and_exact_input():
    from app.rag.embedding_cache import embedding_key,decode_vector
    assert embedding_key('a','Title\nText')!=embedding_key('b','Title\nText')
    assert embedding_key('a','Title\nText')!=embedding_key('a','title\ntext')
    assert decode_vector(b'bad',384) is None


def test_corrupt_cached_vector_is_recomputed(loaded_index,monkeypatch):
    from app.db import EmbeddingCache,session_scope
    from ul_ingest.pipeline import reconcile
    with session_scope() as db:
        entry=db.scalar(select(EmbeddingCache))
        entry.vector=b'bad'
    original=loaded_index.embedder.encode
    calls=[]
    def encode(texts,**kwargs):
        calls.extend(texts)
        return original(texts,**kwargs)
    monkeypatch.setattr(loaded_index.embedder,'encode',encode)
    reconcile(index=loaded_index)
    assert len(calls)==1


def test_seed_import_preserves_existing_database(loaded_index,tmp_path):
    import sqlite3
    from app.rag.embedding_cache import import_seed_embeddings
    from app.db import EmbeddingCache,session_scope,Chunk
    with session_scope() as db:
        rows=[(r.key,r.model,r.dim,r.vector) for r in db.scalars(select(EmbeddingCache))]
        expected=list(db.scalars(select(Chunk.id)))
        db.execute(delete(EmbeddingCache))
    path=tmp_path/'seed.sqlite3'
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE embedding_cache(key TEXT PRIMARY KEY,model TEXT,dim INTEGER,vector BLOB)')
        c.executemany('INSERT INTO embedding_cache VALUES (?,?,?,?)',rows)
    assert import_seed_embeddings(loaded_index.embedder.name,loaded_index.embedder.dim,path)==len(rows)
    with session_scope() as db:
        assert list(db.scalars(select(Chunk.id)))==expected
    assert import_seed_embeddings(loaded_index.embedder.name,loaded_index.embedder.dim,path)==0
