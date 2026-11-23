"""Lock state rules that do not depend on Home Assistant.

The lock reports one integer, lock_status, and the entities, the coordinator
and the command line test script all need to agree on what it means. Keeping
the mapping and the relock watch here, with no homeassistant import, lets
`python -m unittest` exercise them without installing Home Assistant.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

# Encoding from the app's EnumDoorLockStatus, per PROTOCOL.md section 6 of
# tedholtz/homebridge-tapo-dl100. 0 is locked even though it reads like "off".
STATUS_LOCKED = 0
STATUS_UNLOCKED = 1
STATUS_UNINITIALIZED = 2
STATUS_JAM_UNLOCKING = 3
STATUS_JAM_LOCKING = 4

STATUS_NAMES = {
    STATUS_LOCKED: "locked",
    STATUS_UNLOCKED: "unlocked",
    STATUS_UNINITIALIZED: "uninitialized",
    STATUS_JAM_UNLOCKING: "jammed while unlocking",
    STATUS_JAM_LOCKING: "jammed while locking",
}

# After Home Assistant unlocks the door, poll fast so the lock's own
# auto-relock shows up in seconds instead of at the next 300 s poll. Same
# numbers the Homebridge plugin uses (5 s for up to 60 s). Auto-relock times
# longer than the window are still picked up, just by the normal poll.
RELOCK_POLL_SECONDS = 5.0
RELOCK_WINDOW_SECONDS = 60.0


def is_locked(status: int | None) -> bool | None:
    """Return True/False for a settled bolt, None when the state is not known."""

    if status == STATUS_LOCKED:
        return True
    if status == STATUS_UNLOCKED:
        return False
    return None


def is_jammed(status: int | None) -> bool:
    return status in (STATUS_JAM_UNLOCKING, STATUS_JAM_LOCKING)


def status_name(status: int | None) -> str:
    if status is None:
        return "unknown"
    return STATUS_NAMES.get(status, f"unknown ({status})")


async def watch_for_relock(
    refresh: Callable[[], Awaitable[int | None]],
    interval: float = RELOCK_POLL_SECONDS,
    window: float = RELOCK_WINDOW_SECONDS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> int:
    """Poll until the lock reports locked or the window runs out.

    `refresh` reads the lock and returns the new lock_status. Returns the
    number of polls made, so callers and tests can see how fast it stopped.
    A failed read does not end the watch: the lock radio sleeps between
    operations and one miss is normal.
    """

    polls = 0
    max_polls = max(1, int(window // interval))
    while polls < max_polls:
        await sleep(interval)
        polls += 1
        try:
            status = await refresh()
        except Exception:  # noqa: BLE001
            continue
        if status == STATUS_LOCKED or is_jammed(status):
            break
    return polls
