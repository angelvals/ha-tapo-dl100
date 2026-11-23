"""An in-memory DL100 and TP-Link cloud, for offline tests of api.py.

It plays the server side of every step in PROTOCOL.md (cloud login, device
list, handshake0, control-key, handshake1/2, encrypted /app/request) and
checks what the client sends, so a test passes only if the client did the
real handshake and encryption. It also records the TLS setting used for each
request, which is how the TLS test sees which calls skip verification.

The jam states cannot be produced on a real lock on demand, so tests set
`FakeLock.lock_status` directly to 3 or 4.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

from Crypto.Cipher import AES
from multidict import CIMultiDict


def sha(*parts: bytes) -> bytes:
    h = hashlib.sha256()
    for part in parts:
        h.update(part)
    return h.digest()


def pad(data: bytes) -> bytes:
    n = 16 - len(data) % 16
    return data + bytes([n]) * n


def unpad(data: bytes) -> bytes:
    return data[: -data[-1]]


@dataclass
class Call:
    url: str
    ssl: Any


@dataclass
class FakeLock:
    lock_status: int = 0
    battery_percentage: int = 87
    # What the bolt does when setLockStatus arrives. None means it obeys;
    # a number means it ends up there instead (for example 4, jammed).
    command_result: int | None = None
    calls: list[Call] = field(default_factory=list)

    account_id: str = "1234567"
    device_id: str = "80FAKE0DEVICE0ID"
    control_key: str = field(default_factory=lambda: os.urandom(32).hex().upper())

    def __post_init__(self) -> None:
        self._ck = self.control_key.encode("ascii")
        self._lmk = sha(self._ck)
        self._local: bytes | None = None
        self._remote: bytes | None = None
        self._cookie = "TP_SESSIONID=" + os.urandom(8).hex()

    # aiohttp.ClientSession.post stand-in
    def post(self, url: str, headers: dict[str, str] | None = None, data: Any = None, ssl: Any = "default"):
        self.calls.append(Call(url=url, ssl=ssl))
        body = data.encode() if isinstance(data, str) else data
        status, resp_headers, payload = self._route(url, headers or {}, body)
        return _Response(status, resp_headers, payload)

    def ssl_for(self, fragment: str) -> list[Any]:
        return [c.ssl for c in self.calls if fragment in c.url]

    def _route(self, url: str, headers: dict[str, str], body: bytes):
        parsed = urlparse(url)
        if parsed.hostname == "wap.tplinkcloud.com":
            req = json.loads(body)
            if req["method"] == "login":
                return 200, {}, json.dumps({"error_code": 0, "result": {"token": "TOKEN", "accountId": self.account_id}}).encode()
            if req["method"] == "getDeviceList":
                devices = [{"deviceModel": "DL100", "alias": "Front Door", "deviceId": self.device_id}]
                return 200, {}, json.dumps({"error_code": 0, "result": {"deviceList": devices}}).encode()
        if parsed.path.endswith("/control-key"):
            req = json.loads(body)
            assert req["secret"] == "FAKESECRET", req
            assert len(req["random"]) == 8 and req["random"] == req["random"].upper(), req
            return 200, {}, json.dumps({"result": {"controlKey": self.control_key, "accessInfo": ""}}).encode()
        if parsed.path == "/app/handshake0":
            assert len(body) == 33 and body[32] == 0, "handshake0 body must be 32-byte digest + owner role byte"
            return 200, {}, b"FAKESECRET"
        if parsed.path == "/app/handshake1":
            local, proof = body[:16], body[16:]
            if proof != sha(local, self._ck):
                return 403, {}, b""
            self._local, self._remote = local, os.urandom(16)
            return 200, {"Set-Cookie": f"{self._cookie}; Path=/"}, self._remote + sha(local, self._remote, self._lmk)
        if parsed.path == "/app/handshake2":
            if headers.get("Cookie") != self._cookie or body != sha(self._remote, self._local, self._lmk):
                return 403, {}, b""
            return 200, {}, b""
        if parsed.path == "/app/request":
            return self._request(parsed, headers, body)
        return 404, {}, b""

    def _keys(self) -> tuple[bytes, bytes, bytes]:
        def kdf(tag: str) -> bytes:
            return sha(tag.encode("ascii"), self._local, self._remote, self._lmk)

        return kdf("lsk")[:16], kdf("ldk")[:28], kdf("iv")[:12]

    def _request(self, parsed, headers, body):
        if headers.get("Cookie") != self._cookie:
            return 403, {}, b""
        lsk, ldk, ivb = self._keys()
        seq = int(parse_qs(parsed.query)["seq"][0])
        seqb = seq.to_bytes(4, "big")
        mac, ct = body[:32], body[32:]
        if mac != sha(ldk, seqb, ct):
            return 403, {}, b""
        iv = ivb + seqb
        req = json.loads(unpad(AES.new(lsk, AES.MODE_CBC, iv).decrypt(ct)))
        responses = [self._handle(r) for r in req["params"]["requests"]]
        out = json.dumps({"error_code": 0, "result": {"responses": responses}}).encode()
        # The real lock puts a few bytes before the JSON (PROTOCOL.md 4.7).
        ct_out = AES.new(lsk, AES.MODE_CBC, iv).encrypt(pad(b"\x00\x00\x00\x01" + out))
        return 200, {}, sha(ldk, seqb, ct_out) + ct_out

    def _handle(self, r: dict[str, Any]) -> dict[str, Any]:
        if r["method"] == "getDeviceInfo":
            return {"method": "getDeviceInfo", "error_code": 0, "result": {
                "type": "SMART.TAPOLOCK", "model": "DL100", "fw_ver": "1.0.17 Build 260417 Rel.082002",
                "hw_ver": "1.0", "mac": "AA-BB-CC-DD-EE-FF", "lock_status": self.lock_status,
                "battery_percentage": self.battery_percentage, "at_low_battery": self.battery_percentage < 20,
                "rssi": -50,
            }}
        if r["method"] == "setLockStatus":
            assert r["params"]["sa_user_id"] == "local_1"
            wanted = r["params"]["lock_status"]
            self.lock_status = wanted if self.command_result is None else self.command_result
            return {"method": "setLockStatus", "error_code": 0, "result": {"status": 0}}
        return {"method": r["method"], "error_code": -40210}


class _Response:

    def __init__(self, status: int, headers: dict[str, str], payload: bytes) -> None:
        self.status = status
        self.headers = CIMultiDict(headers)
        self._payload = payload

    async def __aenter__(self) -> "_Response":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def read(self) -> bytes:
        return self._payload
