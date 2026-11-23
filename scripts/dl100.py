"""Drive a real DL100 with the integration's own api.py, without Home Assistant.

Usage (from the repo root):
  scripts/live.sh info            read state, battery and the fields the HA device uses
  scripts/live.sh unlock          unlock, then watch for the auto-relock like HA does
  scripts/live.sh lock            lock
  scripts/live.sh watch           only run the relock watch (after a keypad unlock, say)

Credentials come from TAPO_USERNAME, TAPO_PASSWORD and TAPO_LOCK_IP, read from
the environment or from the first .env found in the repo or its parent.

TLS is verified with certifi's roots, the same bundle Home Assistant uses, so
a pass here means the verified login works inside HA too.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import ssl
import sys
import time
from pathlib import Path

import aiohttp
import certifi

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from _load import load  # noqa: E402

api_mod = load("api")
logic = load("logic")


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for candidate in (ROOT / ".env", ROOT.parent / ".env"):
        if candidate.is_file():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    values[key.strip()] = value.strip().strip('"').strip("'")
            break
    for key in ("TAPO_USERNAME", "TAPO_PASSWORD", "TAPO_LOCK_IP", "TAPO_LOCK_NAME"):
        if os.environ.get(key):
            values[key] = os.environ[key]
    missing = [k for k in ("TAPO_USERNAME", "TAPO_PASSWORD", "TAPO_LOCK_IP") if not values.get(k)]
    if missing:
        sys.exit(f"Missing {', '.join(missing)}. Put them in .env next to the repo or export them.")
    return values


def show(info) -> None:
    raw = info.raw
    print(f"  lock_status : {info.lock_status} ({logic.status_name(info.lock_status)})")
    print(f"  HA lock     : locked={logic.is_locked(info.lock_status)} jammed={logic.is_jammed(info.lock_status)}")
    print(f"  battery     : {info.battery_percentage}%  low={info.at_low_battery}")
    print(f"  rssi        : {raw.get('rssi')}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["info", "lock", "unlock", "watch"])
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logs from api.py")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format="%(message)s")

    env = read_env()
    ctx = ssl.create_default_context(cafile=certifi.where())
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ctx)) as session:
        api = api_mod.DlklapApi(
            ip=env["TAPO_LOCK_IP"],
            cloud_username=env["TAPO_USERNAME"],
            cloud_password=env["TAPO_PASSWORD"],
            lock_name=env.get("TAPO_LOCK_NAME", ""),
            websession=session,
            logger=logging.getLogger("dl100"),
        )

        started = time.monotonic()
        info = await api.get_device_info()
        print(f"Connected in {time.monotonic() - started:.1f}s (verified TLS login, cloud deviceId {api.device_id})")

        if args.command == "info":
            show(info)
            raw = info.raw
            print("HA device fields:")
            print(f"  model={raw.get('model')} sw={raw.get('fw_ver')} hw={raw.get('hw_ver')} mac={raw.get('mac')} serial={api.device_id}")
            hidden = {"ssid", "nickname", "latitude", "longitude", "ip"}
            print("All getDeviceInfo keys:", ", ".join(sorted(k for k in raw if k not in hidden)))
            return

        if args.command in ("lock", "unlock"):
            locked = args.command == "lock"
            t = time.monotonic()
            await api.set_lock(locked)
            print(f"{args.command} confirmed by the lock in {time.monotonic() - t:.1f}s")
            show(await api.get_device_info())
            if locked:
                return

        print(f"Watching for relock every {logic.RELOCK_POLL_SECONDS:.0f}s for up to {logic.RELOCK_WINDOW_SECONDS:.0f}s")
        t = time.monotonic()

        async def refresh() -> int:
            current = await api.get_device_info()
            print(f"  +{time.monotonic() - t:5.1f}s  {logic.status_name(current.lock_status)}")
            return current.lock_status

        polls = await logic.watch_for_relock(refresh)
        print(f"Watch ended after {polls} poll(s), {time.monotonic() - t:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
