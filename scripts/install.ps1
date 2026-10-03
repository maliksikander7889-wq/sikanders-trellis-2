param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot 'logs') | Out-Null
Start-Transcript -Path (Join-Path $projectRoot 'logs\install.log') -Append | Out-Null
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User') + ';' + (Join-Path $env:USERPROFILE '.local\bin')
}
function Install-Package([string]$Id) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "Windows App Installer (winget) is missing. Install App Installer from Microsoft Store, then rerun INSTALL.bat. Needed package: $Id"
    }
    & winget install --exact --id $Id --source winget --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw "Installation of $Id failed ($LASTEXITCODE). Install it manually, then rerun INSTALL.bat." }
    Refresh-Path
}
try {
    Write-Host "`nSIKANDER'S TRELLIS 2 - ONE-CLICK SETUP`n" -ForegroundColor DarkYellow
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { throw 'Windows x64 is required.' }
    $gpu = Get-Command nvidia-smi -ErrorAction SilentlyContinue
    if (-not $gpu) { throw 'Install a current NVIDIA graphics driver, restart Windows, and rerun INSTALL.bat.' }
    & nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    if ($LASTEXITCODE -ne 0) { throw 'The NVIDIA driver is not responding.' }
    Write-Host 'First install needs at least 60 GB of free space for both engines and a large model download. 32 GB RAM and 12 GB VRAM are recommended for 1024.'
    $drive = [System.IO.DriveInfo]::new([System.IO.Path]::GetPathRoot($projectRoot))
    if ($drive.AvailableFreeSpace -lt 60GB -and -not (Test-Path '.venv\Scripts\python.exe')) { throw 'Free at least 60 GB on this drive before installation.' }
    if ($CheckOnly) {
        Write-Host 'Preflight passed. No software or models were downloaded.'
        return
    }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Install-Package 'Git.Git' }
    $blender = Get-Command blender -ErrorAction SilentlyContinue
    $blenderFiles = @(Get-ChildItem -Path 'C:\Program Files\Blender Foundation\Blender*\blender.exe' -ErrorAction SilentlyContinue)
    if (-not $blender -and $blenderFiles.Count -eq 0) { Install-Package 'BlenderFoundation.Blender' }
    $vc = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64' -ErrorAction SilentlyContinue
    if (-not $vc -or $vc.Installed -ne 1) { Install-Package 'Microsoft.VCRedist.2015+.x64' }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        $uvInstaller = Join-Path $projectRoot 'logs\uv-install.ps1'
        Invoke-WebRequest 'https://astral.sh/uv/0.12.22/install.ps1' -OutFile $uvInstaller -UseBasicParsing
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $uvInstaller
        if ($LASTEXITCODE -ne 0) { throw 'The uv installer failed.' }
        Refresh-Path
    }
    & uv python install 3.12
    if ($LASTEXITCODE -ne 0) { throw 'Python download failed.' }
    $pythonPath = (& uv python find 3.12 | Select-Object -Last 1)
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $pythonPath)) { throw 'Python 3.12 was not found.' }
    $env:PYTHONUTF8 = '1'
    & $pythonPath setup.py
    if ($LASTEXITCODE -ne 0) { throw 'Environment setup failed. See the error above.' }
    & '.\.venv\Scripts\python.exe' download_models.py --textures --pixal3d
    if ($LASTEXITCODE -ne 0) { throw 'Model download failed. Rerun INSTALL.bat to resume.' }
    Write-Host "`nReady. Opening Sikander's Trellis 2." -ForegroundColor Green
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
} finally {
    Stop-Transcript | Out-Null
}
