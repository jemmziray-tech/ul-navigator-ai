$archive = Join-Path $PSScriptRoot 'data\site_archive'
New-Item -ItemType Directory -Path $archive -Force | Out-Null
New-Item -ItemType File -Path (Join-Path $archive 'STOP') -Force | Out-Null
Write-Host 'The collection and import will pause after their current request finishes.'
