#!/usr/bin/env bash
# Live test against the real lock with the integration's api.py. See scripts/dl100.py.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run --quiet --no-project --python 3.13 --with aiohttp --with pycryptodome --with certifi \
  python scripts/dl100.py "$@"
