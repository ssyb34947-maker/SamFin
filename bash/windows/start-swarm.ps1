Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")
$env:CONFIG_PATH="config/swarm/config.yaml"
$env:SWARM_SERVICE_HOST="0.0.0.0"
$env:SWARM_SERVICE_PORT="8004"
uv run python -m src.swarm.main
