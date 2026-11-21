$folder = Join-Path $PSScriptRoot 'data\curricula'
New-Item -ItemType Directory -Path $folder -Force | Out-Null
New-Item -ItemType File -Path (Join-Path $folder 'STOP') -Force | Out-Null
Write-Host 'Module workers will pause after the current request.'
