param([switch]$CrawlOnly)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Days 2)
$modes = if ($CrawlOnly) { @('crawl') } else { @('crawl','publish') }
foreach ($mode in $modes) {
    $name = "ULNavigator-Public-$mode"
    $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($existing -and $existing.State -eq 'Running') { Write-Host "$name is already running"; continue }
    $arg = '"' + $root + '\scripts\resource_worker.py" ' + $mode
    $action = New-ScheduledTaskAction -Execute "$root\.venv\Scripts\python.exe" -Argument $arg -WorkingDirectory $root
    Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Settings $settings -Description 'Resumable public UL website collection/import requested by project maintainer. No stored passwords.' -Force | Out-Null
    Start-ScheduledTask -TaskName $name
    Write-Host "$name started"
}
