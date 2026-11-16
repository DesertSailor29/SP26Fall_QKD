# Interfaces (DRAFT 2; to be frozen once variants A and B have both been written against it)

These contracts let workstreams build independently. The Python definitions live in
[`src/qkdsim/interfaces.py`](../src/qkdsim/interfaces.py) as `typing.Protocol` classes and frozen
dataclasses; **that file is the source of truth**. This document explains the reasoning behind it. If
the two ever disagree, the code wins and this document is a bug.

Any change after the freeze needs agreement from every owner whose code uses the interface.

## How to use an interface

Code that _uses_ a component imports its `Protocol` from `interfaces.py` and never a concrete class.
Concrete classes are chosen in exactly one place, the **composition root** (a runner or a scenario),
and passed in. Swapping variant A for variant B is then one changed line, and nothing else notices.
That is the whole point of the architecture, so a test of any interface is: _can the consumer be
written without naming an implementation?_

## Conventions

- Bytes are `bytes`, times are `int` nanoseconds, IDs are `str`.
- Bit strings are 1-D `numpy.uint8` arrays of 0s and 1s (`Bits`), the same convention as `qkdsim.rng`.
- Data crossing a component boundary is a frozen dataclass. `KeyBlock` and `Event` must be JSON
  serializable. `Corrected` holds an array and stays between the QKD stages.
- Failures use the exceptions in the table at the end of this document, not return codes.

## Layers

```
Benchmark harness ............ builds a scenario, picks the implementations, reads MetricsSink
QKD stages ................... QKDSender / QKDReceiver  (use QuantumLink, ErrorCorrector, PrivacyAmplifier)
AuthenticatedChannel ......... Channel + Session. One generic class, not an interface
Authenticator / Session ...... the swappable part: PSK+WC, Kerberos-lite, PQC
Channel ...................... raw classical bytes: in-memory, TCP
KeyStore ..................... finished keys, per peer (ETSI-014 API sits on top)
```

## 1. `Channel` (WS2 → everyone)

A two-party pipe for messages. One `send` is one `recv`: message boundaries are preserved.

```python
class Channel(Protocol):
    def send(self, data: bytes) -> None: ...
    def recv(self) -> bytes: ...     # raises ChannelError if closed or empty
    def close(self) -> None: ...
```

Implementations: in-memory (tests), TCP (Docker), and wrappers that are themselves a `Channel`
(authentication, metering, later simulated latency). Because wrappers are channels, they stack.

## 2. `Authenticator` / `Session` (WS3, WS4 → WS1, WS5)

This is the interface that variants A, B and C implement.

```python
class Authenticator(Protocol):
    name: str                                  # "psk-wc" | "kerberos-lite" | "pqc-mldsa"
    def enroll(self, node_id: str) -> None: ...                # onboard a node
    def establish(self, local: str, peer: str, via: Channel) -> Session: ...
    def storage_bytes(self, node_id: str) -> int: ...          # long-term + cached auth material

class Session(Protocol):
    def protect(self, msg: bytes) -> bytes: ...      # message -> what goes on the wire
    def unprotect(self, wire: bytes) -> bytes: ...   # verify; raises AuthError on any failure
    def close(self) -> None: ...
```

- `establish` is the pair setup (for Kerberos, the TGS + AP exchange). `via` is an **unauthenticated**
  channel the handshake may use. PSK ignores it.
- A `Session` is for one local node and one peer, and keeps its own state: message counters, the
  one-time-pad position, the replay cache. **Direction is an internal detail.** Callers only protect
  outgoing and unprotect incoming messages.
- `unprotect` must reject tampered, replayed, reordered and reflected messages (a message you sent
  must not be accepted if bounced back as the peer's). Callers abort the QKD session on `AuthError`.

`AuthenticatedChannel(raw: Channel, session: Session)` is written **once**. `send` calls
`session.protect`, `recv` calls `session.unprotect`. It is itself a `Channel`, so QKD code cannot tell
whether its channel is authenticated. Authenticator authors never write it.

### `KeyPool` (WS3 ↔ WS2)

Where a key-consuming authenticator (PSK + Wegman–Carter) draws its one-time-pad bits:

```python
class KeyPool(Protocol):
    def available_bits(self, peer: str) -> int: ...
    def draw(self, peer: str, n_bits: int) -> bytes: ...   # raises KeyStoreError when empty
```

This resolves the bootstrap cycle: QKD needs authentication, PSK authentication needs key, and key comes
from QKD. The pool starts with an initial pre-shared amount (provisioning) and is refilled with
`KeyStore.put` after each successful QKD block. When the pool is empty the link must be
re-provisioned (backlog A4).

## 3. QKD stages (WS1 → WS2)

Alice and Bob are separate programs that share no state, so the interfaces are **per role**.

```python
class QKDSender(Protocol):        # Alice
    def run(self, n_pulses: int, quantum: PulseSender, classical: Channel) -> KeyBlock: ...

class QKDReceiver(Protocol):      # Bob
    def run(self, quantum: PulseReceiver, classical: Channel) -> KeyBlock: ...
```

`classical` should be an `AuthenticatedChannel`; **all** post-processing messages go through it.
Parameters such as error rate, loss and Eve are set in the constructor.

The stages inside a party are components of their own, because some of them have more than one planned
implementation:

```python
class QuantumLink(Protocol):           # model of the fibre: perfect, noisy, lossy, Eve
    def transmit(self, pulses: Pulses) -> Pulses: ...

class PulseSender(Protocol):   def send(self, pulses: Pulses) -> None: ...
class PulseReceiver(Protocol): def receive(self) -> Pulses: ...

class ErrorCorrector(Protocol):        # Cascade, or the leakage-formula fallback (backlog Q4 / Q7)
    def run(self, role: Role, key: Bits, channel: Channel) -> Corrected: ...

class PrivacyAmplifier(Protocol):      # Toeplitz hashing
    def run(self, role: Role, key: Bits, out_bits: int, channel: Channel) -> Bits: ...
```

Both sides run the same stage implementation, told apart by `Role`. `QuantumLink` is how an in-process
runner joins a `PulseSender` to a `PulseReceiver`; in the Docker setup the same pulses travel over TCP.

```python
@dataclass(frozen=True)
class Corrected:
    key: Bits
    leaked_bits: int        # bits disclosed during error correction

@dataclass(frozen=True)
class KeyBlock:
    link_id: str            # "alice--bob", with the node IDs sorted
    block_id: int           # increases for each new block on a link
    key: bytes              # final key after privacy amplification (b"" if aborted)
    qber: float             # estimated QBER
    raw_bits: int           # qubits sent
    sifted_bits: int
    leaked_bits: int
    aborted: bool           # True if QBER exceeded the threshold
```

## 4. `KeyStore` + ETSI-014 API (WS2 → everyone)

```python
class KeyStore(Protocol):
    def put(self, peer: str, key: bytes) -> None: ...
    def available_bits(self, peer: str) -> int: ...
    def take(self, peer: str, n_bits: int) -> tuple[str, bytes]: ...  # (key_id, key), consumed
    def get(self, peer: str, key_id: str) -> bytes: ...               # retrieved by peer, consumed
```

`take` and `get` raise `KeyStoreError` (not enough key, or unknown ID).

The REST API follows the ETSI GS QKD 014 paths (subset). It is an **adapter on top of `KeyStore`**,
not a separate interface (`enc_keys` → `take`, `dec_keys` → `get`):

- `GET  /api/v1/keys/{slave_SAE_ID}/status`
- `POST /api/v1/keys/{slave_SAE_ID}/enc_keys`: `{number, size}` → `{keys: [{key_ID, key}]}` (base64)
- `POST /api/v1/keys/{master_SAE_ID}/dec_keys`: `{key_IDs: [...]}` → `{keys: [...]}`

## 5. `MetricsSink` (WS5 → everyone)

```python
@dataclass(frozen=True)
class Event:
    run_id: str
    variant: str                 # authenticator name
    component: str               # "quantum" | "kms" | "auth" | "channel" | "kdc"
    event: str                   # "send", "recv", "session_start", "tgs_req", "key_stored", ...
    node: str
    peer: str | None = None
    cpu_ns: int | None = None    # None = not measured for this event
    round_trips: int = 0
    bytes_sent: int = 0
    key_bits_consumed: int = 0
    extra: dict[str, Any] = {}   # anything component-specific

class MetricsSink(Protocol):
    def emit(self, e: Event) -> None: ...
```

The default implementation appends JSONL to `runs/<run_id>.jsonl`.

**Who measures what.** Messages, bytes and round trips are measured **at the seam**: wrap a `Channel` in
a `MeteredChannel`, and every authenticator is measured the same way without its author doing anything.
Only things nobody else can see are emitted by the component itself, such as `key_bits_consumed`
(authenticator) or `tgs_req` (KDC). This keeps variant A and variant B comparable.

## 6. Shared pieces

```python
class Clock(Protocol):
    def now_ns(self) -> int: ...

@dataclass(frozen=True)
class QKDConfig:
    sample_fraction: float = 0.25
    qber_threshold: float = 0.11
    seed: int | None = None       # None = OS randomness; an int gives a reproducible run
    rtt_ns: int = 0               # simulated round-trip time of the classical channel
```

- **`Clock`** keeps simulated latency and tests independent of the wall clock.
- **`QKDConfig`** replaces the global constants in `params.py`, so a scenario can vary them.
- **`RandomSource`** (in `qkdsim.rng`) is unchanged: OS randomness by default, seeded for tests.

## Who provides and who uses

| Interface                                           | Provided by                 | Used by                              |
| --------------------------------------------------- | --------------------------- | ------------------------------------ |
| `Channel`                                           | Channel/transport (WS2)     | Everyone                             |
| `Authenticator` / `Session`                         | Auth layer (WS3, WS4)       | `AuthenticatedChannel`, benchmarks   |
| `KeyPool`                                           | KMS / PSK refill (WS2, WS3) | PSK authenticator                    |
| `QKDSender` / `QKDReceiver`                         | Quantum layer (WS1)         | Runner, benchmarks                   |
| `QuantumLink`, `ErrorCorrector`, `PrivacyAmplifier` | Quantum layer (WS1)         | QKD parties                          |
| `KeyStore` + ETSI-014                               | KMS (WS2)                   | PSK refill, applications, benchmarks |
| `MetricsSink`                                       | Benchmark harness (WS5)     | Everyone                             |

## Errors

| Exception       | Meaning                                                         | Caller should                      |
| --------------- | --------------------------------------------------------------- | ---------------------------------- |
| `ChannelError`  | Channel closed, or nothing to receive                           | Abort the session                  |
| `AuthError`     | A message failed authentication (bad tag, replay, wrong sender) | Abort the session                  |
| `KeyStoreError` | Not enough key material, or unknown key ID                      | Wait for more key, or re-provision |

## Testing

Each interface ships with a **mock** that other workstreams can develop against from day 1, and with
**contract tests** in `tests/contract/` that both the real component and the mock must pass. For
auth, that means a new scheme is added to the list in `test_authenticator_contract.py` and must pass
the shared tests plus the attack tests (tamper, replay, reflection, unenrolled node). Reference
implementations of the small interfaces are in `src/qkdsim/mocks.py`.

## Changes from draft 1

| Draft 1                                                   | Draft 2                                             | Why                                                                 |
| --------------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------- |
| `KeySource.run_session()` returns one `KeyBlock`          | `QKDSender` and `QKDReceiver`                       | Alice and Bob are separate programs that share no state             |
| `AuthenticatedChannel` is an interface implementers write | One generic class built from `Channel` + `Session`  | It was just a transport plus a session; now auth authors write less |
| `Session.tag` / `verify`                                  | `protect` / `unprotect`                             | Matches what goes on the wire, and keeps direction internal         |
| (no raw channel interface)                                | `Channel`                                           | The seam that authentication and metering wrap                      |
| Every implementation reports its own metrics              | Channel traffic is measured by `MeteredChannel`     | Variants are measured identically                                   |
| `Event` fields all required                               | Most optional, plus `extra`                         | Most events don't have a meaningful value for every field           |
| Quantum layer is a single box                             | `QuantumLink`, `ErrorCorrector`, `PrivacyAmplifier` | Q7 (leakage-only fallback) is a second implementation of one stage  |
| REST API listed as part of `KeyStore`                     | REST is an adapter on `KeyStore`                    | One contract, one front end                                         |
| Constants in `params.py`                                  | `QKDConfig` and `Clock`                             | Scenarios can vary them; latency doesn't use wall time              |
| (not covered)                                             | `KeyPool`                                           | Names how PSK auth gets key, which breaks the QKD/auth cycle        |

## Open questions to settle before the freeze

**Carried over**

- Wegman–Carter tag length and hash family (proposal: 128-bit tags with polynomial hashing over GF(2¹²⁸)).
- Where Kerberos long-term keys come from. Proposal: provisioned out of band at first, with a stretch
  goal of refilling them over a QKD link to the KDC.

**New**

- **Key IDs across two nodes.** Alice's and Bob's `KeyStore`s must give the same key bytes the same
  `key_id`. The reference store pretends there is only one store. Proposal: derive the ID from the link
  and the block ID plus an offset, so both sides can compute it independently.
- **`KeyPool` details.** How big is the initial provisioned pool, when does refill happen, and what
  exactly happens on exhaustion (A4)?
- **Reaching the KDC.** `establish(local, peer, via)` gives Kerberos one channel. If the KDC needs its
  own, does it go through the constructor of the Kerberos authenticator, or does `establish` change?

**Settled**

- ~~Whether `Session` covers both directions or one per direction.~~ One `Session` per pair; direction
  is internal to it.
