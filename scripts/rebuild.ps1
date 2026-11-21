# Rebuild the index from already-downloaded pages (no crawling), restart the app,
# then run the evaluation and capture screenshots. Logged to rebuild_log.txt.
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH = "$root\backend;$root\ingestion"
$PY = "$root\.venv\Scripts\python.exe"
Start-Transcript -Path "$root\rebuild_log.txt" -Append | Out-Null
function Step($n) { Write-Host "`n=== STEP: $n === $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Green }
function Run { & $args[0] $args[1..($args.Count - 1)] 2>&1 | ForEach-Object { "$_" } }

Step "stopping running app"
foreach ($port in 8000, 3000) {
  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Seconds 2

Step "indexing downloaded UL sources (offline)"
Run $PY -m ul_ingest crawl --offline --max-pages 150
Run $PY -m ul_ingest stats

Step "starting backend and frontend"
Start-Process -FilePath $PY -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
  -WorkingDirectory "$root\backend" -WindowStyle Minimized `
  -RedirectStandardOutput "$root\data\logs\api_stdout.txt" -RedirectStandardError "$root\data\logs\api_stderr.txt"
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run start > ..\data\logs\web_stdout.txt 2>&1" `
  -WorkingDirectory "$root\frontend" -WindowStyle Minimized
for ($i = 0; $i -lt 90; $i++) {
  Start-Sleep -Seconds 2
  try { $r = Invoke-RestMethod http://127.0.0.1:8000/health/ready -TimeoutSec 5; break } catch {}
}
$r | ConvertTo-Json -Depth 5
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 2
  try { Invoke-WebRequest http://localhost:3000 -UseBasicParsing -TimeoutSec 5 | Out-Null; break } catch {}
}

Step "evaluation"
Run $PY evaluation\run_eval.py

Step "screenshots"
Push-Location frontend
$env:SCREENSHOTS = "1"
Run npx.cmd playwright test e2e/screenshots.spec.ts --project=desktop
Remove-Item Env:SCREENSHOTS
Pop-Location

Step "ALL DONE"
Write-Host "App running at http://localhost:3000"
Start-Process "http://localhost:3000"
Stop-Transcript | Out-Null
