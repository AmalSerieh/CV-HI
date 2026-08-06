$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Run scripts\setup.ps1 -Dev first." }
Set-Location -LiteralPath $root
$env:PYTHONDONTWRITEBYTECODE = "1"
& $python -m pytest -q -p no:cacheprovider
exit $LASTEXITCODE
