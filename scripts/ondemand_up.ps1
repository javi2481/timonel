# Deprecated: use full_up.ps1 (all capabilities up at boot).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Write-Host "ondemand_up is deprecated → scripts/full_up.ps1"
& "$Root\scripts\full_up.ps1"
