param([ValidateSet('crawl','publish')][string]$Mode)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$env:PYTHONPATH = 'backend;ingestion'
$env:PYTHONUTF8 = '1'
$arguments = @('-m','ul_ingest.site_archive',$Mode)
if ($Mode -eq 'crawl') {
    $arguments += @('--inventory','work/ul-sitemap-urls.json','--retry-failed')
} else {
    $arguments += @('--max-documents','1000','--max-chunks','24000','--watch','--retry-failed')
}
& "$root\.venv\Scripts\python.exe" @arguments *>> "$root\data\site_archive\$Mode.log"
exit $LASTEXITCODE
