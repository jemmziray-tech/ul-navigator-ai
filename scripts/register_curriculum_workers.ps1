param([switch]$CollectOnly)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Remove-Item -LiteralPath (Join-Path $root 'data\curricula\STOP') -ErrorAction SilentlyContinue
$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Days 2)
$python = Join-Path $root '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $python)) { $python = Join-Path $root '.venv\Scripts\python.exe' }
$modes = if ($CollectOnly) { @('collect') } else { @('collect', 'publish') }
foreach ($mode in $modes) {
    $name = "ULNavigator-Modules-$mode"
    $existing = Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    if ($existing -and $existing.State -eq 'Running') { Write-Host "$name is already running"; continue }
    $action = New-ScheduledTaskAction -Execute $python -Argument ('"' + $root + '\scripts\curriculum_worker.py" ' + $mode) -WorkingDirectory $root
    Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Settings $settings -Description 'Resumable official UL programme/module collection requested by the project maintainer. No stored passwords.' -Force | Out-Null
    Start-ScheduledTask -TaskName $name
    Write-Host "$name started"
}
