param(
    [string]$RepoRoot = "c:\Users\prath\OneDrive\Desktop\openenv\openenv\email-triage-env",
    [string]$ImageTag = "email-triage-env-smoke",
    [string]$SpaceUrl = "",
    [string]$LogPath = "inference_run.log"
)

$ErrorActionPreference = "Stop"
Set-Location $RepoRoot

Write-Host "[CHECK] Docker daemon"
try {
    docker info | Out-Null
    Write-Host "[PASS] Docker daemon is running"
} catch {
    Write-Host "[FAIL] Docker daemon is not running. Start Docker Desktop and retry."
    exit 1
}

Write-Host "[CHECK] Docker build"
docker build -t $ImageTag . | Out-Host
Write-Host "[PASS] Docker image built: $ImageTag"

Write-Host "[CHECK] Hugging Face login"
try {
    huggingface-cli whoami | Out-Host
    Write-Host "[PASS] Hugging Face login detected"
} catch {
    Write-Host "[WARN] Hugging Face CLI not logged in. Run: huggingface-cli login"
}

if ($SpaceUrl -ne "") {
    Write-Host "[CHECK] HF Space health"
    try {
        Invoke-RestMethod -Method GET -Uri "$SpaceUrl/" | Out-Null
        Write-Host "[PASS] Space health reachable"
        Invoke-RestMethod -Method POST -Uri "$SpaceUrl/reset/task_1" | Out-Null
        Write-Host "[PASS] Space reset/task_1 reachable"
    } catch {
        Write-Host "[FAIL] Space health/reset failed for URL: $SpaceUrl"
        throw
    }
}

$venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $pythonExe = $venvPython
} else {
    $pythonExe = "python"
}

Write-Host "[CHECK] Local API + inference run"
$apiProcess = Start-Process -FilePath $pythonExe -ArgumentList "-m", "uvicorn", "api.main:app", "--app-dir", $RepoRoot, "--host", "127.0.0.1", "--port", "8000" -PassThru

try {
    $ready = $false
    for ($i = 0; $i -lt 200; $i++) {
        try {
            $null = Invoke-RestMethod -Method GET -Uri "http://127.0.0.1:8000/"
            $ready = $true
            break
        } catch {
            # busy retry
        }
    }

    if (-not $ready) {
        Write-Host "[FAIL] Local API did not become ready"
        exit 1
    }

    $env:ENV_URL = "http://127.0.0.1:8000"
    if (-not $env:USE_LLM_TASK1) { $env:USE_LLM_TASK1 = "0" }
    & $pythonExe "inference.py" | Tee-Object -FilePath $LogPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] inference.py exited with code $LASTEXITCODE"
        exit $LASTEXITCODE
    }

    Write-Host "[CHECK] Inference log format"
    & $pythonExe "scripts\validate_inference_log.py" --log $LogPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[FAIL] log format validation failed"
        exit $LASTEXITCODE
    }
    Write-Host "[PASS] inference.py completed and logs validated"
} finally {
    if ($apiProcess -and -not $apiProcess.HasExited) {
        Stop-Process -Id $apiProcess.Id -Force
    }
}

Write-Host "[DONE] Pre-submission smoke checks completed"
