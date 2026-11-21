"""Build a public-source-only embedding cache locally; no production chats are read."""
from pathlib import Path
import gzip
import json
import sqlite3
import sys

import faiss  # Load native library before test capture / ML libraries on Windows.
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'ingestion')]
from app.rag.embedding_cache import embedding_key
from app.rag.embeddings import get_embedder
from app.rag.text import normalize_ws
from app.rag.vector_store import FaissStore
from ul_ingest.chunking import chunk_markdown
from ul_ingest.extractors import extract_text


def main():
    meta = json.loads((ROOT/'data/index/faiss_meta.json').read_text())
    model, dim = meta['model'], meta['dim']
    out = sqlite3.connect(ROOT/'data/embedding_seed.sqlite3')
    out.execute('CREATE TABLE IF NOT EXISTS embedding_cache (key TEXT PRIMARY KEY,model TEXT,dim INTEGER,vector BLOB)')
    store = FaissStore(ROOT/'data/index', dim, model)
    ids = store.ids()
    local = sqlite3.connect((ROOT/'data/ul_navigator.db').as_uri()+'?mode=ro',uri=True)
    count = 0
    for cid, title, section, text in local.execute('SELECT c.id,d.title,c.section,c.text FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.status="indexed"'):
        if cid in ids:
            key = embedding_key(model, f'{title}\n{section}\n{text}')
            vector = np.asarray(store.index.reconstruct(cid),dtype='<f4').tobytes()
            out.execute('INSERT OR IGNORE INTO embedding_cache VALUES (?,?,?,?)',(key,model,dim,vector)); count += 1
    out.commit(); local.close()
    known = {r[0] for r in out.execute('SELECT key FROM embedding_cache')}
    pending = {}
    queue = sqlite3.connect(ROOT/'data/site_archive/queue.sqlite3')
    for (path,) in queue.execute("SELECT payload FROM pages WHERE state='ready'"):
        with gzip.open(path,'rt',encoding='utf-8') as f: doc=json.load(f)
        title=doc['title'][:300]
        md=normalize_ws(extract_text(doc['markdown'].encode()).markdown)
        if len(md.split())<25: continue
        for chunk in chunk_markdown(md,260,50,40):
            section=' > '.join(p for p in chunk.section.split(' > ') if p.strip().lower()!=title.strip().lower())[:480]
            text=f'{title}\n{section}\n{chunk.text}'
            key=embedding_key(model,text)
            if key not in known: pending[key]=text
    queue.close()
    print(json.dumps({'seed_vectors_reused':count,'new_embeddings_needed':len(pending)}),flush=True)
    if pending:
        embedder=get_embedder()
        assert embedder.name==model and embedder.dim==dim
        items=list(pending.items())
        for start in range(0,len(items),128):
            batch=items[start:start+128]
            vecs=embedder.encode([text for key,text in batch])
            out.executemany('INSERT OR IGNORE INTO embedding_cache VALUES (?,?,?,?)',
                [(key,model,dim,np.asarray(vec,dtype='<f4').tobytes()) for (key,_),vec in zip(batch,vecs)])
            out.commit()
            print(json.dumps({'prepared':min(start+128,len(items)),'total':len(items)}),flush=True)
    print(json.dumps({'cache_vectors':out.execute('SELECT count(*) FROM embedding_cache').fetchone()[0]}),flush=True)
    out.close()


if __name__=='__main__': main()
