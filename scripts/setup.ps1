param(
    [switch]$Dev,
    [switch]$Nlp
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$version = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or [version]$version -lt [version]"3.10" -or [version]$version -ge [version]"3.14") {
    throw "Python 3.10, 3.11, or 3.12 is required."
}
if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    python -m venv .venv
}
$python = Join-Path $root ".venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
if ($Dev) { & $python -m pip install -r requirements-dev.txt }
if ($Nlp) { & $python -m pip install -r requirements-nlp.txt }
& $python -m pip install -e . --no-deps
if (-not (Test-Path -LiteralPath ".env")) { Copy-Item -LiteralPath ".env.example" -Destination ".env" }
& $python -m pip check
& $python -c "from resume_analyzer import ResumePipeline; from resume_analyzer.web.app import app; print('Import smoke passed')"
Write-Host "Setup complete."
Write-Host "Run diagnostics: .\.venv\Scripts\python.exe scripts\doctor.py"
Write-Host "Start the web app: .\scripts\run_web.ps1"
