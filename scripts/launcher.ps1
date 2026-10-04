param([ValidateSet('setup','download','launch','check','stop')][string]$Action, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:PYTHONUTF8 = '1'
$env:PYTHONUNBUFFERED = '1'
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
function Studio-Ready {
    try {
        $result = Invoke-RestMethod 'http://127.0.0.1:7860/api/system' -TimeoutSec 3
        return ($result.engine -like '*TRELLIS*' -and $null -ne $result.max_resolution)
    } catch { return $false }
}
try {
    if ($Action -eq 'stop') {
        if (-not (Studio-Ready)) { Write-Host 'Studio is already stopped.'; exit 0 }
        $job = Invoke-RestMethod 'http://127.0.0.1:7860/api/jobs/current' -TimeoutSec 3
        if ($job -and $job.state -eq 'running') { throw 'Finish or stop the generation in the studio first.' }
        $listeners = @(Get-NetTCPConnection -LocalPort 7860 -State Listen -ErrorAction Stop)
        foreach ($listener in $listeners) {
            $owner = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
            if (-not $owner.CommandLine.Contains($projectRoot) -or $owner.CommandLine -notmatch 'uvicorn app:app') { throw 'This studio was started outside this launcher. Close its original terminal.' }
            Stop-Process -Id $owner.ProcessId -ErrorAction Stop
        }
        Write-Host 'Studio stopped. You can run setup or close the launcher.'; exit 0
    }
    if ($Action -eq 'setup') {
        if (Studio-Ready) { throw 'Click Stop studio before updating its environment.' }
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\install.ps1"
        exit $LASTEXITCODE
    }
    if (-not (Test-Path -LiteralPath $python)) { throw 'Choose Setup & download first.' }
    if ($Action -eq 'download' -or $Action -eq 'check') {
        if (Studio-Ready) {
            $job = Invoke-RestMethod 'http://127.0.0.1:7860/api/jobs/current' -TimeoutSec 3
            if ($job -and $job.state -eq 'running') { throw 'Wait for the current generation to finish before downloading or checking.' }
        }
        if ($Action -eq 'download') { & $python -u download_models.py --textures --pixal3d }
        else { & $python -u doctor.py --quick }
        exit $LASTEXITCODE
    }
    if (-not (Studio-Ready)) {
        $listener = Get-NetTCPConnection -LocalPort 7860 -State Listen -ErrorAction SilentlyContinue
        if ($listener) { throw 'Port 7860 is already in use by another service. Close that service before launching.' }
        New-Item -ItemType Directory -Force -Path logs | Out-Null
        $server = Start-Process -FilePath $python -ArgumentList "-m uvicorn app:app --app-dir `"$projectRoot`" --host 127.0.0.1 --port 7860" -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput 'logs\studio-out.log' -RedirectStandardError 'logs\studio-error.log' -PassThru
        $deadline = (Get-Date).AddSeconds(60)
        while (-not (Studio-Ready)) {
            $server.Refresh()
            if ($server.HasExited) { throw 'Studio could not start. See logs\studio-error.log.' }
            if ((Get-Date) -gt $deadline) { throw 'Studio is taking longer to start. Check the logs and click Launch studio again.' }
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:7860' }
    Write-Host 'Studio ready at http://127.0.0.1:7860. You can close the launcher.'
} catch { Write-Host $_.Exception.Message; exit 1 }
