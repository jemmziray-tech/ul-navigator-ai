Set-Location -LiteralPath $PSScriptRoot
foreach ($mode in @('crawl','publish')) {
    Write-Host "`n$mode progress:"
    $file = Join-Path $PSScriptRoot "data\site_archive\$mode-status.json"
    if (Test-Path -LiteralPath $file) { Get-Content -LiteralPath $file }
}
