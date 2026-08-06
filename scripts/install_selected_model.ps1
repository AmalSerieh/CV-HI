param(
    [string]$Model,
    [switch]$Yes
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
. (Join-Path $PSScriptRoot "load_env.ps1")
Import-LocalEnvironment -Path (Join-Path $root ".env")
if (-not $Model) { $Model = $env:RESUME_AI_MODEL }
if (-not $Model) { throw "Pass -Model or configure RESUME_AI_MODEL in .env." }
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) { throw "Ollama is not installed or is not on PATH." }
& $ollama.Source list | Out-Null
if ($LASTEXITCODE -ne 0) { throw "The Ollama service is not reachable." }
& $ollama.Source show $Model *> $null
if ($LASTEXITCODE -ne 0) {
    if (-not $Yes) {
        $answer = Read-Host "Model '$Model' may require several GB. Download it? [y/N]"
        if ($answer -notmatch '^(?i:y|yes)$') { Write-Host "Cancelled."; exit 2 }
    }
    & $ollama.Source pull $Model
    if ($LASTEXITCODE -ne 0) { throw "Ollama could not pull '$Model'." }
}
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "python" }
& $python scripts\verify_ollama.py
if ($LASTEXITCODE -ne 0) { throw "Structured-output verification failed." }
Write-Host "Validated: RESUME_AI_MODEL=$Model"
