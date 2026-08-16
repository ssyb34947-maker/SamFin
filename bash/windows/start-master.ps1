Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")
$env:CONFIG_PATH="config/master/config.yaml"
$env:MASTER_SERVICE_HOST="0.0.0.0"
$env:MASTER_SERVICE_PORT="8000"
uv run python -m src.master.main
