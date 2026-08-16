Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")
$env:CONFIG_PATH="config/mcp/config.yaml"
$env:MCP_SERVICE_HOST="0.0.0.0"
$env:MCP_SERVICE_PORT="8001"
uv run python -m src.mcp.main
