#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
CONFIG_PATH=config/mcp/config.yaml MCP_SERVICE_HOST=0.0.0.0 MCP_SERVICE_PORT=8001 uv run python -m src.mcp.main
