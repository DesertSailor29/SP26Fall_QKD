"""Alice and Bob.

Each party owns its own randomness and secrets, and talks to the other only through its transport
endpoint (classical) and the quantum channel (driven by the protocol runner).

Sifting messages (phase 1, unauthenticated):
  Bob   -> Alice  "bases"  Bob's measurement bases
  Alice -> Bob    "sift"   mask of positions where the bases matched
"""

import numpy as np

from qkdsim.quantum import Pulses, measure
from qkdsim.rng import RandomSource
from qkdsim.sifting import matching_mask, sift
from qkdsim.transport import Endpoint, decode_bits, encode_bits


class Alice:
    def __init__(self, endpoint: Endpoint, rng: RandomSource, peer: str = "bob") -> None:
        self.endpoint = endpoint
        self.rng = rng
        self.peer = peer
        self._bits: np.ndarray | None = None
        self._bases: np.ndarray | None = None
        self.sifted_key: np.ndarray | None = None

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


class Bob:
    def __init__(self, endpoint: Endpoint, rng: RandomSource, peer: str = "alice") -> None:
        self.endpoint = endpoint
        self.rng = rng
        self.peer = peer
        self._bases: np.ndarray | None = None
        self._results: np.ndarray | None = None
        self.sifted_key: np.ndarray | None = None

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
