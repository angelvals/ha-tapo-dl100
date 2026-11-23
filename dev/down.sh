#!/usr/bin/env bash
# Stop the throwaway Home Assistant and delete its config, so up.sh starts clean.
set -euo pipefail
cd "$(dirname "$0")"
docker compose down
rm -rf config
