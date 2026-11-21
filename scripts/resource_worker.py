"""Independent Windows task entrypoint; never stores credentials in task arguments."""
from pathlib import Path
import os
import sys
import traceback
root=Path(__file__).resolve().parents[1]
os.chdir(root)
sys.path[:0]=[str(root/'backend'),str(root/'ingestion')]
mode=sys.argv[1]
assert mode in {'crawl','publish'}
log=(root/'data/site_archive'/f'{mode}.log').open('a',encoding='utf-8',buffering=1)
sys.stdout=sys.stderr=log
sys.argv=[sys.argv[0],mode,'--retry-failed']
if mode=='crawl': sys.argv+=['--inventory','work/ul-sitemap-urls.json']
else: sys.argv+=['--max-documents','1000','--max-chunks','24000','--watch']
try:
    from ul_ingest.site_archive import main
    main()
except Exception:
    traceback.print_exc()
    raise
