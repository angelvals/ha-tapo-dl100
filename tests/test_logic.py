"""Lock status mapping and the post-unlock relock watch.

These guard the two things the lock entity gets wrong silently: a jam shown
as "unknown" instead of jammed, and an auto-relock that HA keeps showing as
unlocked for minutes.
"""

from __future__ import annotations

import asyncio
import unittest

from _load import load

logic = load("logic")


class StatusMapping(unittest.TestCase):

    def test_locked_and_unlocked(self) -> None:
        self.assertIs(logic.is_locked(0), True)
        self.assertIs(logic.is_locked(1), False)

    def test_jam_codes_are_jammed_and_not_locked_or_unlocked(self) -> None:
        for code in (3, 4):
            self.assertTrue(logic.is_jammed(code))
            self.assertIsNone(logic.is_locked(code))

    def test_uninitialized_and_unknown_are_neither(self) -> None:
        for code in (2, 99, None):
            self.assertFalse(logic.is_jammed(code))
            self.assertIsNone(logic.is_locked(code))

    def test_names(self) -> None:
        self.assertEqual(logic.status_name(4), "jammed while locking")
        self.assertEqual(logic.status_name(99), "unknown (99)")


class RelockWatch(unittest.TestCase):

    def run_watch(self, statuses: list[object]) -> tuple[int, list[float]]:
        sleeps: list[float] = []
        reads = iter(statuses)

        async def sleep(seconds: float) -> None:
            sleeps.append(seconds)

        async def refresh() -> int | None:
            value = next(reads)
            if isinstance(value, Exception):
                raise value
            return value  # type: ignore[return-value]

        polls = asyncio.run(logic.watch_for_relock(refresh, interval=5, window=60, sleep=sleep))
        return polls, sleeps

    def test_stops_as_soon_as_the_lock_relocks(self) -> None:
        polls, sleeps = self.run_watch([1, 1, 0])
        self.assertEqual(polls, 3)
        self.assertEqual(sleeps, [5, 5, 5])

    def test_stops_on_jam(self) -> None:
        polls, _ = self.run_watch([1, 4])
        self.assertEqual(polls, 2)

    def test_gives_up_after_the_window(self) -> None:
        polls, _ = self.run_watch([1] * 20)
        self.assertEqual(polls, 12)

    def test_a_failed_read_does_not_end_the_watch(self) -> None:
        polls, _ = self.run_watch([TimeoutError("radio asleep"), 0])
        self.assertEqual(polls, 2)


if __name__ == "__main__":
    unittest.main()
