#Requires -Version 5.1
<#
.SYNOPSIS
  Starts the FastAPI backend and Streamlit UI (each in its own window), and
  optionally the end-to-end agent pipeline demo - the full local dev stack.

.EXAMPLE
  .\scripts\run_dev.ps1
.EXAMPLE
  .\scripts\run_dev.ps1 -SkipSeed -ApiPort 8080
.EXAMPLE
  .\scripts\run_dev.ps1 -RunAgentDemo
#>
param(
    [switch]$SkipSeed,
    [switch]$RunAgentDemo,
    [int]$ApiPort = 8000
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$VenvActivate = Join-Path $RepoRoot ".venv\Scripts\Activate.ps1"
# Each spawned window is a fresh shell, so re-activate the venv (and relax the
# process-scoped execution policy) inside it rather than relying on this one.
$LaunchPrefix = if (Test-Path $VenvActivate) {
    "Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force; & '$VenvActivate';"
} else {
    ""
}

if (Test-Path $VenvActivate) {
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
    & $VenvActivate
}

if (-not $SkipSeed) {
    Write-Host "Seeding local SQLite DB (admin user + sample schemes)..." -ForegroundColor Cyan
    python scripts/seed_db.py
}

Write-Host "Starting FastAPI backend on http://localhost:$ApiPort ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "$LaunchPrefix cd '$RepoRoot'; uvicorn backend.app.main:app --reload --port $ApiPort"
)

Write-Host "Starting Streamlit UI on http://localhost:8501 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "$LaunchPrefix cd '$RepoRoot'; `$env:API_BASE_URL='http://localhost:$ApiPort'; streamlit run streamlit_app.py"
)

if ($RunAgentDemo) {
    Write-Host "Running end-to-end agent pipeline demo (requires model credentials in .env)..." -ForegroundColor Cyan
    python scripts/run_pipeline_demo.py
}

Write-Host "`nBackend and Streamlit are running in their own windows - close them (or Ctrl+C inside) to stop." -ForegroundColor Green
