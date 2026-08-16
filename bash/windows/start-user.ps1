Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")
$env:CONFIG_PATH="config/user/config.yaml"
$env:USER_SYSTEM_HOST="0.0.0.0"
$env:USER_SYSTEM_PORT="8002"
uv run python -m src.user_system.main
