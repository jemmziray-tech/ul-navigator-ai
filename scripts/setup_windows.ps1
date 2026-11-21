# UL Navigator AI - one-time setup on Windows 11 (PowerShell).
# Run from the repository root:  powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
$ErrorActionPreference = "Stop"

Write-Host "==> Creating Python virtual environment (.venv)" -ForegroundColor Green
py -3.12 -m venv .venv 2>$null; if (-not $?) { python -m venv .venv }
.\.venv\Scripts\python -m pip install --upgrade pip

Write-Host "==> Installing PyTorch with CUDA 12.8 (required for RTX 50-series / Blackwell GPUs)" -ForegroundColor Green
.\.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cu128

Write-Host "==> Installing backend, ingestion and ML dependencies" -ForegroundColor Green
.\.venv\Scripts\pip install -r requirements-dev.txt -r requirements-ml.txt

if (-not (Test-Path .env)) {
  Copy-Item .env.example .env
  Write-Host "==> Created .env from .env.example - add your GEMINI_API_KEY" -ForegroundColor Yellow
}

Write-Host "==> Installing frontend dependencies" -ForegroundColor Green
Push-Location frontend
npm install
if (-not (Test-Path .env.local)) { "NEXT_PUBLIC_API_URL=http://localhost:8000" | Out-File -Encoding utf8 .env.local }
npx playwright install chromium
Pop-Location

Write-Host "==> Checking the environment" -ForegroundColor Green
Push-Location backend
..\.venv\Scripts\python -m app.cli doctor
Pop-Location

Write-Host "`nNext steps:" -ForegroundColor Green
Write-Host "  1. Edit .env (GEMINI_API_KEY, CRAWL_USER_AGENT contact e-mail, admin hash + JWT secret)"
Write-Host "  2. Build the knowledge base:   .\scripts\ingest.ps1"
Write-Host "  3. Start the app:              .\scripts\run_dev.ps1"
