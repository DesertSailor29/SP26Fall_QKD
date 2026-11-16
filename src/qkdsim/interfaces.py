"""The contracts between components. Nothing in this file does any work.

Rule of thumb: code that USES a component imports the Protocol from here, never a concrete class.
Concrete classes are chosen in exactly one place (the "composition root": a runner or a scenario),
and handed to the code that needs them.

Layers, from the wire up:

    Channel               raw bytes between two parties (in-memory, TCP, ...)
    Authenticator/Session proof that a message is genuine (PSK+Wegman-Carter, Kerberos-lite, ...)
    AuthenticatedChannel  a Channel + a Session. ONE concrete class (see mocks.py), nobody
                          reimplements it. Auth authors only write Authenticator + Session.
    QKD stages            QuantumLink, ErrorCorrector, PrivacyAmplifier, QKDSender/QKDReceiver
    KeyStore              where finished keys go
    MetricsSink           where measurements go
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

import numpy as np

from qkdsim.quantum import Pulses  # reused from the proof of concept: it is already clean

Bits = np.ndarray  # 1-D uint8 array of 0s and 1s, same convention as qkdsim.rng


# --------------------------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------------------------

class ChannelError(Exception):
    """The channel is closed, or there was nothing to receive."""


class AuthError(Exception):
    """A message failed authentication (bad tag, replay, wrong sender, ...). Callers must abort."""


class KeyStoreError(Exception):
    """Not enough key material, or unknown key id."""


class Role(Enum):
    ALICE = "alice"   # prepares and sends the qubits
    BOB = "bob"       # measures them


# --------------------------------------------------------------------------------------------
# Cross-cutting: time, configuration, randomness
# --------------------------------------------------------------------------------------------

class Clock(Protocol):
    """Time source, so simulated latency and tests don't depend on the wall clock."""

    def now_ns(self) -> int: ...


@dataclass(frozen=True)
class QKDConfig:
    """Everything a scenario might want to vary. Replaces the global constants in params.py."""

    sample_fraction: float = 0.25   # share of the sifted key sacrificed for the QBER estimate
    qber_threshold: float = 0.11    # abort above this
    seed: int | None = None         # None = OS randomness, int = reproducible run
    rtt_ns: int = 0                 # simulated round-trip time of the classical channel

# --------------------------------------------------------------------------------------------
# Channel (classical, raw)
# --------------------------------------------------------------------------------------------

class Channel(Protocol):
    """A two-party pipe for messages. Message boundaries are preserved: one send = one recv."""

    def send(self, data: bytes) -> None: ...
    def recv(self) -> bytes:
        """Return the next message. Raise ChannelError if the channel is closed or empty."""
        ...
    def close(self) -> None: ...


# --------------------------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------------------------

class Session(Protocol):
    """Authentication state between ONE local node and ONE peer.

    Implementations keep their own state (message counters, one-time-pad position, replay cache).
    Direction is an internal detail: the caller only protects outgoing and unprotects incoming.
    """

    def protect(self, msg: bytes) -> bytes:
        """Return what goes on the wire: the message plus whatever proof the scheme needs."""
        ...

    def unprotect(self, wire: bytes) -> bytes:
        """Verify and return the original message. Raise AuthError if anything is wrong."""
        ...

    def close(self) -> None: ...


class Authenticator(Protocol):
    """A way of authenticating messages. One class per scheme (A: PSK+WC, B: Kerberos-lite, ...)."""

    name: str  # "psk-wc" | "kerberos-lite" | "pqc-mldsa" | ...

    def enroll(self, node_id: str) -> None:
        """Onboard a node (install a pairwise key, register at the KDC, ...)."""
        ...

    def establish(self, local: str, peer: str, via: Channel) -> Session:
        """Set up a session with `peer`. `via` is an UNAUTHENTICATED channel the handshake may use
        (Kerberos needs it to reach the KDC and the peer; PSK ignores it). Raise AuthError if the
        pair cannot be authenticated."""
        ...

    def storage_bytes(self, node_id: str) -> int:
        """Long-term plus cached auth material held for this node (a metric)."""
        ...


class KeyPool(Protocol):
    """Where a key-consuming authenticator (PSK+Wegman-Carter) draws one-time-pad bits from.

    This is the answer to the bootstrap cycle: QKD needs auth, PSK auth needs key, key comes from
    QKD. The pool is seeded with an initial pre-shared amount (provisioning), and refilled with
    `KeyStore.put` once QKD has produced new key. If the pool runs dry, draw() raises KeyStoreError
    and the link must be re-provisioned (backlog A4).
    """

    def available_bits(self, peer: str) -> int: ...
    def draw(self, peer: str, n_bits: int) -> bytes: ...


# --------------------------------------------------------------------------------------------
# QKD stages (per role, because Alice and Bob are separate programs)
# --------------------------------------------------------------------------------------------

class PulseSender(Protocol):
    def send(self, pulses: Pulses) -> None: ...


class PulseReceiver(Protocol):
    def receive(self) -> Pulses: ...


class QuantumLink(Protocol):
    """Model of the fibre, including noise, loss or Eve. Used by in-process runners to join a
    PulseSender and a PulseReceiver. Same shape as QuantumChannel in qkdsim.quantum."""

    def transmit(self, pulses: Pulses) -> Pulses: ...


@dataclass(frozen=True)
class Corrected:
    key: Bits
    leaked_bits: int  # bits disclosed over the public channel while correcting errors


class ErrorCorrector(Protocol):
    """Makes Alice's and Bob's keys identical. Both sides run the same implementation.

    Two planned implementations: real Cascade, and a "leakage formula only" fallback that doesn't
    exchange anything and just reports f * h(QBER) * n leaked bits (backlog Q4 / Q7).
    """

    def run(self, role: Role, key: Bits, channel: Channel) -> Corrected: ...


class PrivacyAmplifier(Protocol):
    """Shrinks the corrected key so Eve's partial knowledge becomes irrelevant (Toeplitz hashing)."""

    def run(self, role: Role, key: Bits, out_bits: int, channel: Channel) -> Bits: ...


@dataclass(frozen=True)
class KeyBlock:
    link_id: str        # "alice--bob", node ids sorted
    block_id: int       # increases for each new block on a link
    key: bytes          # final key after privacy amplification (b"" if aborted)
    qber: float
    raw_bits: int       # qubits sent
    sifted_bits: int
    leaked_bits: int
    aborted: bool


class QKDSender(Protocol):
    """Alice's side of a whole QKD session. `classical` should be an AuthenticatedChannel."""

    def run(self, n_pulses: int, quantum: PulseSender, classical: Channel) -> KeyBlock: ...


class QKDReceiver(Protocol):
    """Bob's side."""

    def run(self, quantum: PulseReceiver, classical: Channel) -> KeyBlock: ...


# --------------------------------------------------------------------------------------------
# Key storage
# --------------------------------------------------------------------------------------------

class KeyStore(Protocol):
    """Finished keys, per peer. The ETSI GS QKD 014 REST API is a thin adapter on top of this
    (enc_keys -> take, dec_keys -> get), not a separate interface."""

    def put(self, peer: str, key: bytes) -> None: ...
    def available_bits(self, peer: str) -> int: ...
    def take(self, peer: str, n_bits: int) -> tuple[str, bytes]:
        """Consume n_bits and return (key_id, key). Raise KeyStoreError if not enough."""
        ...
    def get(self, peer: str, key_id: str) -> bytes:
        """Retrieve (and consume) a key that was issued earlier under key_id."""
        ...


# --------------------------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Event:
    run_id: str
    variant: str              # authenticator name
    component: str            # "quantum" | "kms" | "auth" | "channel" | "kdc"
    event: str                # "send", "recv", "session_start", "tgs_req", "key_stored", ...
    node: str
    peer: str | None = None
    cpu_ns: int | None = None  # None = not measured for this event
    round_trips: int = 0
    bytes_sent: int = 0
    key_bits_consumed: int = 0
    extra: dict[str, Any] = field(default_factory=dict)  # anything component-specific


class MetricsSink(Protocol):
    def emit(self, e: Event) -> None: ...
