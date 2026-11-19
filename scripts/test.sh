#!/usr/bin/env bash
# Offline tests: status mapping, relock watch, and api.py against a fake lock.
# Needs only the integration's own runtime packages (aiohttp, pycryptodome),
# pulled into a throwaway uv environment. No Home Assistant, no lock, no cloud.
#
# The real aiohttp and Crypto are imported before discovery on purpose:
# tests/test_api.py stubs them with MagicMock via sys.modules.setdefault, and
# whichever test file loads first would otherwise decide for all of them.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run --quiet --no-project --python 3.13 --with aiohttp --with pycryptodome \
  python -c 'import aiohttp, Crypto.Cipher, multidict, unittest, sys; unittest.main(module=None, argv=["test", "discover", "-s", "tests", "-v", *sys.argv[1:]])' "$@"
