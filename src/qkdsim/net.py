"""TCP links, so each party can run in its own process or container.

Two kinds of link, each a TCP connection carrying length-prefixed frames:

- classical: JSON messages, the same bytes InMemoryTransport carries. TcpEndpoint implements the
  Endpoint protocol, so Alice and Bob work unchanged on top of it.
- quantum: one frame holding a batch of pulses. This is a model of a fibre, not a quantum link: the
  frame holds the prepared bits and bases in the clear, and the receiving party may only pass them
  to measure() (see docs/SIMPLIFICATIONS.md).
"""

import json
import socket
import struct
import time
from typing import Any

from qkdsim.quantum import Pulses
from qkdsim.transport import Message, TranscriptEntry, TransportError, decode_bits, encode_bits

_HEADER = struct.Struct("!I")
MAX_FRAME = 64 * 1024 * 1024
IO_TIMEOUT = 60.0


def parse_addr(addr: str) -> tuple[str, int]:
    host, sep, port = addr.rpartition(":")
    if not sep or not host:
        raise ValueError(f"expected host:port, got {addr!r}")
    return host, int(port)


def connect(addr: str, wait: float = 30.0) -> socket.socket:
    """Connect to host:port, retrying while the peer (or its DNS name) is not up yet."""
    host, port = parse_addr(addr)
    deadline = time.monotonic() + wait
    while True:
        try:
            sock = socket.create_connection((host, port), timeout=5.0)
            sock.settimeout(IO_TIMEOUT)
            return sock
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.2)


def listen(port: int) -> socket.socket:
    return socket.create_server(("", port), backlog=4, reuse_port=False)


def accept(server: socket.socket, wait: float = IO_TIMEOUT) -> socket.socket:
    server.settimeout(wait)
    sock, _ = server.accept()
    sock.settimeout(IO_TIMEOUT)
    return sock


def send_frame(sock: socket.socket, data: bytes) -> None:
    sock.sendall(_HEADER.pack(len(data)) + data)


def recv_frame(sock: socket.socket) -> bytes:
    (length,) = _HEADER.unpack(_recv_exact(sock, _HEADER.size))
    if length > MAX_FRAME:
        raise TransportError(f"frame of {length} bytes exceeds the limit")
    return _recv_exact(sock, length)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise TransportError("connection closed by peer")
        buf += chunk
    return bytes(buf)


def send_pulses(sock: socket.socket, pulses: Pulses) -> None:
    body = {"bits": encode_bits(pulses.bits), "bases": encode_bits(pulses.bases)}
    send_frame(sock, json.dumps(body).encode())


def recv_pulses(sock: socket.socket) -> Pulses:
    body = json.loads(recv_frame(sock))
    return Pulses(bits=decode_bits(body["bits"]), bases=decode_bits(body["bases"]))


class TcpEndpoint:
    """Classical-channel endpoint over one TCP connection to a single peer."""

    def __init__(self, name: str, sock: socket.socket) -> None:
        self.name = name
        self.sock = sock
        self.transcript: list[TranscriptEntry] = []

    def send(self, to: str, kind: str, payload: dict[str, Any]) -> None:
        msg = Message(self.name, to, kind, payload)
        raw = msg.to_bytes()
        self._record(msg, raw)
        send_frame(self.sock, raw)

    def recv(self, kind: str) -> Message:
        raw = recv_frame(self.sock)
        msg = Message.from_bytes(raw)
        self._record(msg, raw)
        if msg.recipient != self.name:
            raise TransportError(f"{self.name}: message addressed to {msg.recipient!r}")
        if msg.kind != kind:
            raise TransportError(f"{self.name}: expected {kind!r}, got {msg.kind!r}")
        return msg

    def close(self) -> None:
        self.sock.close()

    def _record(self, msg: Message, raw: bytes) -> None:
        self.transcript.append(TranscriptEntry(
            seq=len(self.transcript), sender=msg.sender, recipient=msg.recipient,
            kind=msg.kind, size=len(raw), raw=raw,
        ))
