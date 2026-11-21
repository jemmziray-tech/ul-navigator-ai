# Backend unit/integration tests, then frontend type-check. E2E needs both servers running.
.\.venv\Scripts\python -m pytest
Push-Location frontend; npm run lint; Pop-Location
Write-Host "For E2E: start the app (scripts\run_dev.ps1) then: cd frontend; npm run test:e2e"
