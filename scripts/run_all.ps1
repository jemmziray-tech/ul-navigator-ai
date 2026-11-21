# UL Navigator AI - full automated setup + ingestion + evaluation + screenshots (Windows).
# Launched by RUN_ME.bat. Everything is logged to setup_log.txt in the project root.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Start-Transcript -Path "$root\setup_log.txt" -Append | Out-Null
function Step($name) { Write-Host "`n=== STEP: $name === $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Green }
function Fail($msg) { Write-Host "=== FAILED: $msg ===" -ForegroundColor Red; Stop-Transcript | Out-Null; Read-Host "Press Enter to close"; exit 1 }

Step "environment"
Write-Host "Windows: $([Environment]::OSVersion.VersionString)"
try { nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv } catch { Write-Host "nvidia-smi not found" }
$hasGpu = $null -ne (Get-Command nvidia-smi -ErrorAction SilentlyContinue)

# ---- Python -------------------------------------------------------------------
$py = $null
foreach ($v in @("3.12", "3.13", "3.11")) {
  & py "-$v" -c "import sys; print(sys.version)" 2>$null
  if ($LASTEXITCODE -eq 0) { $py = @("py", "-$v"); break }
}
if (-not $py) {
  $ver = & python -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
  Write-Host "python on PATH: $ver"
  if ($ver -in @("3.11", "3.12", "3.13")) { $py = @("python") }
}
if (-not $py) {
  Step "installing Python 3.12 with winget"
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent
  $py = @("py", "-3.12")
}
Write-Host "Using Python launcher: $($py -join ' ')"

Step "virtual environment"
if (-not (Test-Path ".venv\Scripts\python.exe")) {
  if ($py.Count -gt 1) { & $py[0] $py[1] -m venv .venv } else { & $py[0] -m venv .venv }
}
if (-not (Test-Path ".venv\Scripts\python.exe")) { Fail "could not create .venv" }
$PY = "$root\.venv\Scripts\python.exe"
& $PY --version
& $PY -m pip install --upgrade pip --quiet

Step "PyTorch"
$hasTorch = & $PY -c "import torch; print(torch.__version__)" 2>$null
if (-not $hasTorch) {
  if ($hasGpu) { & $PY -m pip install torch --index-url https://download.pytorch.org/whl/cu128 }
  else { & $PY -m pip install torch --index-url https://download.pytorch.org/whl/cpu }
}
& $PY -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"

Step "Python dependencies"
& $PY -m pip install -r requirements-dev.txt -r requirements-ml.txt
if ($LASTEXITCODE -ne 0) { Fail "pip install failed" }

Step "configure .env"
& $PY scripts\make_env.py

Step "backend tests"
& $PY -m pytest -q -p no:cacheprovider

# ---- Node -------------------------------------------------------------------
Step "Node.js"
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements --silent
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
node --version
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Fail "Node.js is not available" }

Step "frontend install + build"
Push-Location frontend
if (-not (Test-Path ".env.local")) { "NEXT_PUBLIC_API_URL=http://localhost:8000" | Out-File -Encoding ascii .env.local }
npm install --no-fund --no-audit
npx playwright install chromium
npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; Fail "frontend build failed" }
Pop-Location

Step "doctor (downloads embedding + reranker models on first run)"
Push-Location backend
& $PY -m app.cli doctor
Pop-Location

# ---- Knowledge base ----------------------------------------------------------
Step "crawl official UL sources"
$env:PYTHONPATH = "$root\backend;$root\ingestion"
& $PY -m ul_ingest crawl
& $PY -m ul_ingest stats

# ---- Run the app ---------------------------------------------------------------
Step "starting backend and frontend"
New-Item -ItemType Directory -Force -Path "$root\data\logs" | Out-Null
Start-Process -FilePath $PY -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
  -WorkingDirectory "$root\backend" -WindowStyle Minimized `
  -RedirectStandardOutput "$root\data\logs\api_stdout.txt" -RedirectStandardError "$root\data\logs\api_stderr.txt"
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run start > ..\data\logs\web_stdout.txt 2>&1" `
  -WorkingDirectory "$root\frontend" -WindowStyle Minimized
$ok = $false
for ($i = 0; $i -lt 90; $i++) {
  Start-Sleep -Seconds 2
  try { $r = Invoke-RestMethod http://127.0.0.1:8000/health/ready -TimeoutSec 5; $ok = $true; break } catch {}
}
if (-not $ok) { Fail "backend did not become ready (see data\logs\api_stderr.txt)" }
$r | ConvertTo-Json -Depth 5
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 2
  try { Invoke-WebRequest http://localhost:3000 -UseBasicParsing -TimeoutSec 5 | Out-Null; break } catch {}
}

Step "evaluation (116 questions)"
& $PY evaluation\run_eval.py

Step "screenshots"
Push-Location frontend
$env:SCREENSHOTS = "1"
npx playwright test e2e/screenshots.spec.ts --project=desktop
Remove-Item Env:SCREENSHOTS
Pop-Location

Step "ALL DONE"
Write-Host "App running at http://localhost:3000 (API http://localhost:8000/docs)."
Start-Process "http://localhost:3000"
Stop-Transcript | Out-Null
