# Interfaces (DRAFT; to be frozen at the end of week 1)

These contracts let workstreams build independently. The Python definitions will live in
`src/qkdsim/interfaces.py`, as `typing.Protocol` classes and frozen dataclasses. This document is the
human-readable version. Any change after the freeze needs agreement from every owner whose code uses
the interface.

Conventions: bytes are `bytes`, times are `int` nanoseconds, and IDs are `str`. Every message that
crosses a layer boundary is a dataclass that can be serialized to JSON.

## 1. `KeySource` (WS1 → WS2)

One QKD link between two nodes.

```python
@dataclass(frozen=True)
class KeyBlock:
    link_id: str            # "alice--bob", with the node IDs sorted
    block_id: int           # increases for each new block on a link
    key: bytes              # final key after privacy amplification
    qber: float             # estimated QBER
    raw_bits: int           # qubits sent
    sifted_bits: int
    leaked_bits: int        # bits disclosed during error correction
    aborted: bool           # True if QBER exceeded the threshold (key is then b"")

class KeySource(Protocol):
    def run_session(self, n_pulses: int, channel: AuthenticatedChannel) -> KeyBlock: ...
```

`run_session` sends **all** post-processing messages through `channel`. Parameters such as error rate,
loss and Eve are set in the constructor.

## 2. `KeyStore` + ETSI-014 API (WS2 → everyone)

```python
class KeyStore(Protocol):
    def put(self, peer: str, key: bytes) -> None: ...
    def available_bits(self, peer: str) -> int: ...
    def take(self, peer: str, n_bits: int) -> tuple[str, bytes]: ...  # (key_id, key), consumed
    def get(self, peer: str, key_id: str) -> bytes: ...               # retrieved by peer, consumed
```

The REST API follows the ETSI GS QKD 014 paths (subset):

- `GET  /api/v1/keys/{slave_SAE_ID}/status`
- `POST /api/v1/keys/{slave_SAE_ID}/enc_keys`: `{number, size}` → `{keys: [{key_ID, key}]}` (base64)
- `POST /api/v1/keys/{master_SAE_ID}/dec_keys`: `{key_IDs: [...]}` → `{keys: [...]}`

## 3. `Authenticator` / `AuthenticatedChannel` (WS3, WS4 → WS1, WS5)

```python
class Authenticator(Protocol):
    name: str                                            # "psk-wc" | "kerberos-lite" | "pqc-mldsa"
    def enroll(self, node_id: str) -> None: ...          # onboarding a node
    def open(self, local: str, peer: str) -> Session: ...# pair setup (e.g. the Kerberos TGS + AP exchange)
    def storage_bytes(self, node_id: str) -> int: ...    # long-term + cached auth material

class Session(Protocol):
    def tag(self, msg: bytes) -> bytes: ...
    def verify(self, msg: bytes, tag: bytes) -> bool: ...   # False → caller aborts
    def close(self) -> None: ...

class AuthenticatedChannel(Protocol):
    def send(self, msg: bytes) -> None: ...      # tags msg using the Session
    def recv(self) -> bytes: ...                 # verifies, raises AuthError on failure
```

Every implementation reports these counts to `MetricsSink`: messages, bytes, round trips and QKD key
bits consumed.

## 4. `MetricsSink` (WS5 → everyone)

```python
@dataclass(frozen=True)
class Event:
    run_id: str
    variant: str            # authenticator name
    component: str          # "quantum" | "kms" | "auth" | "channel" | "kdc"
    event: str              # e.g. "session_start", "tag", "tgs_req", "key_stored"
    node: str
    peer: str | None
    cpu_ns: int
    round_trips: int
    bytes_sent: int
    key_bits_consumed: int

class MetricsSink(Protocol):
    def emit(self, e: Event) -> None: ...        # default implementation appends JSONL to runs/<run_id>.jsonl
```

## Open questions to settle in week 1

- Wegman–Carter tag length and hash family (proposal: 128-bit tags with polynomial hashing over GF(2¹²⁸)).
- Where Kerberos long-term keys come from. Proposal: provisioned out of band at first, with a stretch
  goal of refilling them over a QKD link to the KDC.
- Whether `Session` covers both directions or there is one per direction.
