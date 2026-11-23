"""api.py against the fake lock: handshake, commands, jams and TLS policy.

The TLS test is the one that matters most: before this change every cloud
call, including the login that carries the account password, went out with
certificate checks off.
"""

from __future__ import annotations

import asyncio
import logging
import unittest

from _load import load
from fake_lock import FakeLock

api_mod = load("api")
logic = load("logic")


def make_api(lock: FakeLock):
    return api_mod.DlklapApi(
        ip="192.0.2.10",
        cloud_username="user@example.com",
        cloud_password="pw",
        lock_name="Front Door",
        websession=lock,
        logger=logging.getLogger("test"),
    )


class Api(unittest.TestCase):

    def test_reads_state_through_a_full_handshake(self) -> None:
        lock = FakeLock(lock_status=1, battery_percentage=55)
        info = asyncio.run(make_api(lock).get_device_info())
        self.assertEqual(info.lock_status, 1)
        self.assertEqual(info.battery_percentage, 55)
        self.assertEqual(info.raw["model"], "DL100")

    def test_lock_and_unlock_change_the_bolt(self) -> None:
        lock = FakeLock(lock_status=0)
        api = make_api(lock)

        async def run() -> None:
            await api.set_lock(False)
            self.assertEqual(lock.lock_status, 1)
            await api.set_lock(True)
            self.assertEqual(lock.lock_status, 0)

        asyncio.run(run())

    def test_jam_reported_by_the_lock_reads_as_jammed(self) -> None:
        for code in (3, 4):
            info = asyncio.run(make_api(FakeLock(lock_status=code)).get_device_info())
            self.assertTrue(logic.is_jammed(info.lock_status))
            self.assertIsNone(logic.is_locked(info.lock_status))

    def test_a_command_that_jams_fails_instead_of_reporting_success(self) -> None:
        lock = FakeLock(lock_status=1, command_result=4)
        with self.assertRaises(api_mod.DlklapError):
            asyncio.run(make_api(lock).set_lock(True))
        self.assertEqual(lock.lock_status, 4)


class TlsPolicy(unittest.TestCase):

    def test_password_call_is_verified_and_only_control_key_skips_it(self) -> None:
        lock = FakeLock()
        asyncio.run(make_api(lock).get_device_info())
        # "default" means api.py passed no ssl argument, so aiohttp verifies.
        self.assertEqual(set(lock.ssl_for("wap.tplinkcloud.com")), {"default"})
        self.assertEqual(lock.ssl_for("/control-key"), [False])


if __name__ == "__main__":
    unittest.main()
