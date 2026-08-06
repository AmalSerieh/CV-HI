param(
    [int]$Port = 8765,
    [ValidateSet("none", "ollama")]
    [string]$Provider = "none"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\load_env.ps1"
Import-LocalEnvironment -Path (Join-Path $PSScriptRoot "..\.env")
$env:RESUME_AI_PROVIDER = $Provider
if ($Provider -eq "none") {
    $env:RESUME_AI_MODEL = ""
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$logDirectory = Join-Path $root "runtime\logs"
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$baseUrl = "http://127.0.0.1:$Port"

$probe = [System.Net.Sockets.TcpClient]::new()
try {
    $connect = $probe.ConnectAsync("127.0.0.1", $Port)
    if ($connect.Wait(300) -and $probe.Connected) {
        throw "Port $Port is already occupied. Stop the existing listener before validation."
    }
}
finally {
    $probe.Dispose()
}

$server = Start-Process `
    -FilePath $python `
    -ArgumentList "-m", "uvicorn", "resume_analyzer.web.app:app", "--host", "127.0.0.1", "--port", "$Port" `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logDirectory "web-validation.stdout.log") `
    -RedirectStandardError (Join-Path $logDirectory "web-validation.stderr.log") `
    -PassThru

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($server.HasExited) {
            throw (
                "Validation server exited before readiness with code " +
                "$($server.ExitCode). See runtime\\logs\\web-validation.stderr.log."
            )
        }
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "$baseUrl/api/health" -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $ready) {
        throw "Loopback web server did not become ready"
    }
    & $python (Join-Path $PSScriptRoot "validate_web_workflow.py") --base-url $baseUrl
    if ($LASTEXITCODE -ne 0) {
        throw "Web workflow validation failed"
    }
}
finally {
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -Force
    }
    Write-Output "validated_server_pid=$($server.Id)"
}
