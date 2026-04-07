param(
    [Parameter(Mandatory = $true)]
    [string]$RepoId,
    [string]$RepoRoot = "c:\Users\prath\OneDrive\Desktop\openenv\openenv\email-triage-env",
    [string]$Branch = "main"
)

$ErrorActionPreference = "Stop"
Set-Location $RepoRoot

Write-Host "[CHECK] Hugging Face authentication"
huggingface-cli whoami | Out-Host

Write-Host "[CHECK] Create Space repo if missing"
try {
    huggingface-cli repo create $RepoId --type space --space_sdk docker --yes | Out-Host
} catch {
    Write-Host "[WARN] Repo may already exist. Continuing."
}

$remoteUrl = "https://huggingface.co/spaces/$RepoId"
$existingRemote = git remote | Select-String -Pattern "^hf$"
if (-not $existingRemote) {
    git remote add hf $remoteUrl
} else {
    git remote set-url hf $remoteUrl
}

Write-Host "[CHECK] Pushing code to HF Space"
git push hf "$Branch"

Write-Host "[DONE] Space deployment pushed to $remoteUrl"
Write-Host "[NEXT] Set Space variables: API_BASE_URL, MODEL_NAME, HF_TOKEN (if using LLM path)."
