# Resume independent, limited Windows tasks. No secrets are stored in task arguments.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
Remove-Item -LiteralPath (Join-Path $PSScriptRoot 'data\site_archive\STOP') -ErrorAction SilentlyContinue
& (Join-Path $PSScriptRoot 'scripts\register_resource_workers.ps1')
Write-Host 'Keep this computer awake and connected. Use UL_RESOURCE_PROGRESS.ps1 for progress.'
