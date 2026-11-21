$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'scripts\register_curriculum_workers.ps1')
Write-Host 'Module collection/import resumed. Keep this computer awake and connected.'
