$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Run scripts\setup.ps1 first." }
Set-Location -LiteralPath $root
. (Join-Path $PSScriptRoot "load_env.ps1")
Import-LocalEnvironment -Path (Join-Path $root ".env")
& $python scripts\ensure_ollama.py --start
if ($LASTEXITCODE -ne 0) { throw "The configured local Ollama service is not ready." }
& $python scripts\doctor.py
if ($LASTEXITCODE -ne 0) { throw "Required diagnostics failed." }
& $python -m resume_analyzer.web.app
