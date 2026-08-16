#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
CONFIG_PATH=config/user/config.yaml USER_SYSTEM_HOST=0.0.0.0 USER_SYSTEM_PORT=8002 uv run python -m src.user_system.main
