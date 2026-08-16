#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
CONFIG_PATH=config/master/config.yaml MASTER_SERVICE_HOST=0.0.0.0 MASTER_SERVICE_PORT=8000 uv run python -m src.master.main
