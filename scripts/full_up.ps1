# All PaddleX SPA capabilities up (no on-demand stop).
# Usage: .\scripts\full_up.ps1
# RAM: several GB — every tm-paddlex-* in the default stack.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "== docker compose up (all caps) =="
docker compose -f docker-compose.yml up -d --build --wait
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "OK — open http://localhost:8000/"
Write-Host "All default PaddleX services running; UI capas activas al boot."
