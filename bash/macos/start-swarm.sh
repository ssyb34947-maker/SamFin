#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
CONFIG_PATH=config/swarm/config.yaml SWARM_SERVICE_HOST=0.0.0.0 SWARM_SERVICE_PORT=8004 uv run python -m src.swarm.main
