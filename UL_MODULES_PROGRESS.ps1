foreach ($name in @('module-progress.json','publish-progress.json')) {
    $path = Join-Path $PSScriptRoot ('data\curricula\' + $name)
    if (Test-Path -LiteralPath $path) { Get-Content -LiteralPath $path }
}
