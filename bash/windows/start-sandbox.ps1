Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")
$env:SANDBOX_CONFIG_PATH="config/sandbox/config.yaml"
$env:SANDBOX_SERVICE_HOST="0.0.0.0"
$env:SANDBOX_SERVICE_PORT="8003"
uv run python -m src.sandbox.main
