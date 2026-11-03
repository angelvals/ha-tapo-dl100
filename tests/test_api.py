"""Unit tests for Tapo DL100 API and alias matching."""

import os
import sys
import unittest
from unittest.mock import MagicMock

# Stub Home Assistant and third-party dependencies so tests can run in pure Python CI
for mod in [
    "voluptuous",
    "homeassistant",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.exceptions",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.util",
    "Crypto",
    "Crypto.Cipher",
    "aiohttp",
]:
    sys.modules.setdefault(mod, MagicMock())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from custom_components.tapo_dl100.api import _decode_alias


class TestTapoDl100Api(unittest.TestCase):
    """Test suite for alias decoding and device matching."""

    def test_decode_alias_valid_base64(self):
        """Test decoding valid base64 aliases."""
        self.assertEqual(_decode_alias("RnJvbnQgRG9vciBEZWFkYm9sdA=="), "Front Door Deadbolt")
        self.assertEqual(_decode_alias("QmFjayBEb29yIERlYWRib2x0"), "Back Door Deadbolt")
        self.assertEqual(_decode_alias("R2FyYWdlIERlYWRib2x0"), "Garage Deadbolt")
        self.assertEqual(_decode_alias("RnJvbnQgRG9vciBMb2Nr"), "Front Door Lock")

    def test_decode_alias_plain_string(self):
        """Test fallback on plain string (not valid base64)."""
        self.assertEqual(_decode_alias("Front Door Lock"), "Front Door Lock")
        self.assertEqual(_decode_alias("Back Door"), "Back Door")

    def test_decode_alias_empty_or_none(self):
        """Test handling of None, empty strings, and whitespace."""
        self.assertEqual(_decode_alias(""), "")
        self.assertEqual(_decode_alias(None), "")
        self.assertEqual(_decode_alias("   "), "")

    def test_multi_lock_matching_logic(self):
        """Test matching logic with multiple locks."""
        dl_locks = [
            {
                "deviceId": "dev_front_123",
                "deviceModel": "DL110",
                "alias": "RnJvbnQgRG9vciBMb2Nr",  # "Front Door Lock" in base64
            },
            {
                "deviceId": "dev_back_456",
                "deviceModel": "DL110",
                "alias": "QmFjayBEb29yIExvY2s=",   # "Back Door Lock" in base64
            },
        ]

        def find_match(target_name: str, devices: list[dict]):
            target = target_name.strip()
            for d in devices:
                raw_alias = str(d.get("alias") or "").strip()
                decoded = _decode_alias(raw_alias)
                dev_id = str(d.get("deviceId") or "").strip()
                if (
                    target.lower() == decoded.lower()
                    or target == raw_alias
                    or target == dev_id
                ):
                    return d
            if len(devices) == 1:
                return devices[0]
            return None

        # Match by plain text
        match_front = find_match("Front Door Lock", dl_locks)
        self.assertIsNotNone(match_front)
        self.assertEqual(match_front["deviceId"], "dev_front_123")

        # Match by case-insensitive plain text
        match_front_lower = find_match("front door lock", dl_locks)
        self.assertIsNotNone(match_front_lower)
        self.assertEqual(match_front_lower["deviceId"], "dev_front_123")

        # Match back door
        match_back = find_match("Back Door Lock", dl_locks)
        self.assertIsNotNone(match_back)
        self.assertEqual(match_back["deviceId"], "dev_back_456")

        # Match by deviceId
        match_id = find_match("dev_front_123", dl_locks)
        self.assertIsNotNone(match_id)
        self.assertEqual(match_id["deviceId"], "dev_front_123")

        # Match by raw base64 string
        match_raw = find_match("RnJvbnQgRG9vciBMb2Nr", dl_locks)
        self.assertIsNotNone(match_raw)
        self.assertEqual(match_raw["deviceId"], "dev_front_123")

        # Non-matching name returns None
        self.assertIsNone(find_match("Garage Lock", dl_locks))


if __name__ == "__main__":
    unittest.main()
