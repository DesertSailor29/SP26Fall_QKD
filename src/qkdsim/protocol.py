"""Single-process BB84 runner (phase 1)."""

from dataclasses import dataclass

import numpy as np

from qkdsim.parties import Alice, Bob
from qkdsim.quantum import PerfectChannel, QuantumChannel
from qkdsim.rng import RandomSource, SeededRandom, SystemRandom
from qkdsim.transport import InMemoryTransport, TranscriptEntry


@dataclass(frozen=True)
class BB84Result:
    n_pulses: int
    alice_key: np.ndarray
    bob_key: np.ndarray
    transcript: list[TranscriptEntry]

    @property
    def sifted_bits(self) -> int:
        return len(self.alice_key)

    @property
    def keys_match(self) -> bool:
        return np.array_equal(self.alice_key, self.bob_key)


def make_rngs(seed: int | None) -> tuple[RandomSource, RandomSource]:
    """Independent randomness for Alice and Bob: OS CSPRNG by default, seeded if a seed is given."""
    if seed is None:
        return SystemRandom(), SystemRandom()
    seq_a, seq_b = np.random.SeedSequence(seed).spawn(2)
    return SeededRandom(seq_a), SeededRandom(seq_b)


def run_bb84(
    n_pulses: int,
    seed: int | None = None,
    channel: QuantumChannel | None = None,
) -> BB84Result:
    if n_pulses <= 0:
        raise ValueError("n_pulses must be positive")
    rng_a, rng_b = make_rngs(seed)
    channel = channel or PerfectChannel()
    transport = InMemoryTransport()
    alice = Alice(transport.endpoint("alice"), rng_a)
    bob = Bob(transport.endpoint("bob"), rng_b)

    # Quantum phase
    bob.measure(channel.transmit(alice.prepare(n_pulses)))

    # Classical phase: sifting
    bob.announce_bases()
    alice_key = alice.sift()
    bob_key = bob.sift()

    return BB84Result(n_pulses, alice_key, bob_key, transport.transcript)
