"""Pre-shared key authentication with HMAC-SHA256."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import struct
from collections.abc import Mapping

from qkdsim.interfaces import AuthError, Channel

KEY_BYTES = 32
TAG_BYTES = 32
_COUNTER = struct.Struct(">Q")


def _pair(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def _label(name: str) -> bytes:
    raw = name.encode()
    return struct.pack(">H", len(raw)) + raw


class PSKSession:
    """Wire format: counter (8 bytes) | message | tag (32 bytes)."""

    def __init__(self, local: str, peer: str, key: bytes) -> None:
        self._key = key
        self._out_prefix = _label(local) + _label(peer)
        self._in_prefix = _label(peer) + _label(local)
        self._send_counter = 0
        self._recv_counter = 0
        self._closed = False

    def _tag(self, prefix: bytes, counter: bytes, msg: bytes) -> bytes:
        return hmac.new(self._key, prefix + counter + msg, hashlib.sha256).digest()

    def protect(self, msg: bytes) -> bytes:
        if self._closed:
            raise AuthError("session is closed")
        counter = _COUNTER.pack(self._send_counter)
        self._send_counter += 1
        return counter + msg + self._tag(self._out_prefix, counter, msg)

    def unprotect(self, wire: bytes) -> bytes:
        if self._closed:
            raise AuthError("session is closed")
        if len(wire) < _COUNTER.size + TAG_BYTES:
            raise AuthError("message too short")
        counter = wire[: _COUNTER.size]
        msg = wire[_COUNTER.size : -TAG_BYTES]
        tag = wire[-TAG_BYTES:]
        if not hmac.compare_digest(tag, self._tag(self._in_prefix, counter, msg)):
            raise AuthError("bad tag")
        (n,) = _COUNTER.unpack(counter)
        if n != self._recv_counter:
            raise AuthError(f"expected message {self._recv_counter}, got {n} (replay or reorder)")
        self._recv_counter += 1
        return msg

    def close(self) -> None:
        self._closed = True


class PSKAuthenticator:
    """One shared key per pair of nodes. Pass `keys` when each side loads the key itself."""

    name = "psk-hmac"

    def __init__(self, keys: Mapping[tuple[str, str], bytes] | None = None) -> None:
        self._keys: dict[tuple[str, str], bytes] = {}
        self._nodes: set[str] = set()
        for (a, b), key in (keys or {}).items():
            if len(key) != KEY_BYTES:
                raise ValueError(f"pre-shared keys must be {KEY_BYTES} bytes")
            self._keys[_pair(a, b)] = bytes(key)
            self._nodes.update((a, b))

    def enroll(self, node_id: str) -> None:
        if node_id in self._nodes:
            return
        for other in self._nodes:
            self._keys[_pair(node_id, other)] = secrets.token_bytes(KEY_BYTES)
        self._nodes.add(node_id)

    def establish(self, local: str, peer: str, via: Channel) -> PSKSession:
        if local == peer:
            raise AuthError("a node cannot open a session with itself")
        key = self._keys.get(_pair(local, peer))
        if key is None:
            raise AuthError(f"no pre-shared key for {local!r} and {peer!r}")
        return PSKSession(local, peer, key)

    def storage_bytes(self, node_id: str) -> int:
        return sum(len(k) for pair, k in self._keys.items() if node_id in pair)
