"""The classical channel.

Parties talk only through endpoints of a transport. Messages are serialized to bytes on send and
parsed again on receive, so no Python object is ever shared between parties. The byte form is also
what authentication will tag in phase 2.

The transport records every message in a transcript. Eve sees the entire classical channel, so the
transcript is exactly what she learns; it doubles as analysis data.
"""

import base64
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np


@dataclass(frozen=True)
class Message:
    sender: str
    recipient: str
    kind: str
    payload: dict[str, Any]

    def to_bytes(self) -> bytes:
        return json.dumps(
            {"sender": self.sender, "recipient": self.recipient, "kind": self.kind,
             "payload": self.payload},
            sort_keys=True, separators=(",", ":"),
        ).encode()

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        d = json.loads(data)
        return cls(sender=d["sender"], recipient=d["recipient"], kind=d["kind"],
                   payload=d["payload"])


@dataclass(frozen=True)
class TranscriptEntry:
    seq: int
    sender: str
    recipient: str
    kind: str
    size: int
    raw: bytes


class TransportError(Exception):
    pass


class Endpoint(Protocol):
    name: str

    def send(self, to: str, kind: str, payload: dict[str, Any]) -> None: ...

    def recv(self, kind: str) -> Message:
        """Return the next message; raise TransportError if none or if its kind differs."""
        ...


class InMemoryTransport:
    """Single-process transport: one FIFO inbox per named endpoint."""

    def __init__(self) -> None:
        self._inboxes: dict[str, deque[bytes]] = {}
        self.transcript: list[TranscriptEntry] = []

    def endpoint(self, name: str) -> "InMemoryEndpoint":
        if name in self._inboxes:
            raise ValueError(f"endpoint {name!r} already exists")
        self._inboxes[name] = deque()
        return InMemoryEndpoint(name, self)

    def _deliver(self, msg: Message) -> None:
        if msg.recipient not in self._inboxes:
            raise TransportError(f"unknown recipient {msg.recipient!r}")
        raw = msg.to_bytes()
        self.transcript.append(TranscriptEntry(
            seq=len(self.transcript), sender=msg.sender, recipient=msg.recipient,
            kind=msg.kind, size=len(raw), raw=raw,
        ))
        self._inboxes[msg.recipient].append(raw)

    def _take(self, name: str) -> bytes:
        inbox = self._inboxes[name]
        if not inbox:
            raise TransportError(f"{name}: no message waiting")
        return inbox.popleft()


@dataclass
class InMemoryEndpoint:
    name: str
    _transport: InMemoryTransport = field(repr=False)

    def send(self, to: str, kind: str, payload: dict[str, Any]) -> None:
        self._transport._deliver(Message(self.name, to, kind, payload))

    def recv(self, kind: str) -> Message:
        msg = Message.from_bytes(self._transport._take(self.name))
        if msg.kind != kind:
            raise TransportError(f"{self.name}: expected {kind!r}, got {msg.kind!r}")
        return msg


def encode_bits(bits: np.ndarray) -> dict[str, Any]:
    """Pack a 0/1 array into a JSON-safe payload field."""
    packed = np.packbits(bits.astype(np.uint8))
    return {"n": int(len(bits)), "b64": base64.b64encode(packed.tobytes()).decode()}


def decode_bits(field_: dict[str, Any]) -> np.ndarray:
    packed = np.frombuffer(base64.b64decode(field_["b64"]), dtype=np.uint8)
    return np.unpackbits(packed)[: field_["n"]].copy()
