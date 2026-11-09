"""Alice and Bob.

Each party owns its own randomness and secrets, and talks to the other only through its transport
endpoint (classical) and the quantum channel (driven by the protocol runner or by the node).

Classical messages (unauthenticated):
  Bob   -> Alice  "bases"   Bob's measurement bases
  Alice -> Bob    "sift"    mask of positions where the bases matched
  Alice -> Bob    "sample"  random positions of the sifted key and Alice's bits there
  Bob   -> Alice  "qber"    error rate Bob found on that sample

The sample is public after this exchange, so both sides drop it from the key.
"""

import numpy as np

from qkdsim.quantum import Pulses, measure
from qkdsim.rng import RandomSource
from qkdsim.sifting import matching_mask, sift
from qkdsim.transport import Endpoint, decode_bits, encode_bits


def sample_size(n_sifted: int, fraction: float) -> int:
    """How many sifted bits to sacrifice for error estimation (at least 1, at most all)."""
    if n_sifted <= 0:
        raise ValueError("no sifted bits to estimate the error rate on")
    if not 0 < fraction <= 1:
        raise ValueError("sample fraction must be in (0, 1]")
    return min(n_sifted, max(1, round(n_sifted * fraction)))


class Alice:
    def __init__(self, endpoint: Endpoint, rng: RandomSource, peer: str = "bob") -> None:
        self.endpoint = endpoint
        self.rng = rng
        self.peer = peer
        self._bits: np.ndarray | None = None
        self._bases: np.ndarray | None = None
        self.sifted_key: np.ndarray | None = None
        self.sample_size = 0
        self.qber: float | None = None
        self.key: np.ndarray | None = None

    def prepare(self, n: int) -> Pulses:
        self._bits = self.rng.bits(n)
        self._bases = self.rng.bits(n)
        return Pulses(bits=self._bits.copy(), bases=self._bases.copy())

    def sift(self) -> np.ndarray:
        msg = self.endpoint.recv("bases")
        bob_bases = decode_bits(msg.payload["bases"])
        mask = matching_mask(self._bases, bob_bases)
        self.endpoint.send(self.peer, "sift", {"mask": encode_bits(mask)})
        self.sifted_key = sift(self._bits, mask)
        return self.sifted_key

    def send_sample(self, fraction: float) -> None:
        """Reveal a random sample of the sifted key so Bob can count errors on it."""
        n = len(self.sifted_key)
        self.sample_size = sample_size(n, fraction)
        mask = np.zeros(n, dtype=bool)
        mask[self.rng.sample(n, self.sample_size)] = True
        self.endpoint.send(self.peer, "sample", {
            "mask": encode_bits(mask), "bits": encode_bits(self.sifted_key[mask]),
        })
        self.key = self.sifted_key[~mask].copy()

    def receive_qber(self) -> float:
        self.qber = float(self.endpoint.recv("qber").payload["qber"])
        return self.qber


class Bob:
    def __init__(self, endpoint: Endpoint, rng: RandomSource, peer: str = "alice") -> None:
        self.endpoint = endpoint
        self.rng = rng
        self.peer = peer
        self._bases: np.ndarray | None = None
        self._results: np.ndarray | None = None
        self.sifted_key: np.ndarray | None = None
        self.sample_size = 0
        self.qber: float | None = None
        self.key: np.ndarray | None = None

    def measure(self, pulses: Pulses) -> None:
        self._bases = self.rng.bits(len(pulses))
        self._results = measure(pulses, self._bases, self.rng)

    def announce_bases(self) -> None:
        self.endpoint.send(self.peer, "bases", {"bases": encode_bits(self._bases)})

    def sift(self) -> np.ndarray:
        msg = self.endpoint.recv("sift")
        mask = decode_bits(msg.payload["mask"]).astype(bool)
        self.sifted_key = sift(self._results, mask)
        return self.sifted_key

    def estimate_qber(self) -> float:
        msg = self.endpoint.recv("sample")
        mask = decode_bits(msg.payload["mask"]).astype(bool)
        if mask.shape != self.sifted_key.shape or not mask.any():
            raise ValueError("sample mask does not fit the sifted key")
        alice_bits = decode_bits(msg.payload["bits"])
        errors = int(np.count_nonzero(alice_bits != self.sifted_key[mask]))
        self.sample_size = int(mask.sum())
        self.qber = errors / self.sample_size
        self.endpoint.send(self.peer, "qber", {"qber": self.qber})
        self.key = self.sifted_key[~mask].copy()
        return self.qber
