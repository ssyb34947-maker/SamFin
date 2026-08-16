#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
SANDBOX_CONFIG_PATH=config/sandbox/config.yaml SANDBOX_SERVICE_HOST=0.0.0.0 SANDBOX_SERVICE_PORT=8003 uv run python -m src.sandbox.main
