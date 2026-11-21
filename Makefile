# Linux/macOS/WSL convenience targets (Windows: see scripts/*.ps1)
PY ?= .venv/bin/python
export PYTHONPATH := backend:ingestion
setup:
	python3 -m venv .venv && $(PY) -m pip install -r requirements-dev.txt -r requirements-ml.txt && cd frontend && npm install
ingest:
	$(PY) -m ul_ingest crawl
api:
	cd backend && ../$(PY) -m uvicorn app.main:app --reload --port 8000
web:
	cd frontend && npm run dev
test:
	$(PY) -m pytest && cd frontend && npm run lint
e2e:
	cd frontend && npm run test:e2e
eval:
	$(PY) evaluation/run_eval.py
demo:
	DATA_DIR=data_demo EMBEDDING_BACKEND=hash $(PY) scripts/seed_demo.py
