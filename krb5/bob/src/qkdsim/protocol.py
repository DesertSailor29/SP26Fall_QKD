"""Single-process BB84 runner: prepare, measure, sift, estimate QBER, accept or abort.

The parties live in qkdsim.alice and qkdsim.bob. For one process per party (e.g. one Docker
container each), see qkdsim.node.

Classical messages (unauthenticated):
  Bob   -> Alice  "bases"   Bob's measurement bases
  Alice -> Bob    "sift"    mask of positions where the bases matched
  Alice -> Bob    "sample"  random positions of the sifted key and Alice's bits there
  Bob   -> Alice  "qber"    error rate Bob found on that sample

The sample is public after this exchange, so both sides drop it from the key.
"""

from dataclasses import dataclass

import numpy as np

from qkdsim.alice import Alice
from qkdsim.bob import Bob
from qkdsim.params import QBER_THRESHOLD, SAMPLE_FRACTION
from qkdsim.quantum import InterceptResendEve, PerfectChannel, QuantumChannel
from qkdsim.rng import RandomSource, SeededRandom, SystemRandom
from qkdsim.transport import InMemoryTransport, TranscriptEntry


@dataclass(frozen=True)
class BB84Result:
    n_pulses: int
    sifted_bits: int
    sample_size: int
    qber: float
    aborted: bool
    alice_key: np.ndarray  # sifted key minus the public sample
    bob_key: np.ndarray
    transcript: list[TranscriptEntry]

    @property
    def keys_match(self) -> bool:
        return np.array_equal(self.alice_key, self.bob_key)


def make_rngs(seed: int | None) -> tuple[RandomSource, RandomSource, RandomSource]:
    """Independent randomness for Alice, Bob and Eve: OS CSPRNG by default, seeded if given."""
    if seed is None:
        return SystemRandom(), SystemRandom(), SystemRandom()
    seq_a, seq_b, seq_e = np.random.SeedSequence(seed).spawn(3)
    return SeededRandom(seq_a), SeededRandom(seq_b), SeededRandom(seq_e)


def run_bb84(
    n_pulses: int,
    seed: int | None = None,
    eve: bool = False,
    channel: QuantumChannel | None = None,
    sample_fraction: float = SAMPLE_FRACTION,
    qber_threshold: float = QBER_THRESHOLD,
) -> BB84Result:
    if n_pulses <= 0:
        raise ValueError("n_pulses must be positive")
    if eve and channel is not None:
        raise ValueError("pass either eve=True or a channel, not both")
    rng_a, rng_b, rng_e = make_rngs(seed)
    if channel is None:
        channel = InterceptResendEve(rng_e) if eve else PerfectChannel()
    transport = InMemoryTransport()
    alice = Alice(transport.endpoint("alice"), rng_a)
    bob = Bob(transport.endpoint("bob"), rng_b)

    # Quantum phase
    bob.measure(channel.transmit(alice.prepare(n_pulses)))

    # Classical phase: sifting, then error estimation on a sacrificed sample
    bob.announce_bases()
    alice.sift()
    bob.sift()
    alice.send_sample(sample_fraction)
    qber = bob.estimate_qber()
    alice.receive_qber()

    return BB84Result(
        n_pulses=n_pulses,
        sifted_bits=len(alice.sifted_key),
        sample_size=alice.sample_size,
        qber=qber,
        aborted=qber > qber_threshold,
        alice_key=alice.key,
        bob_key=bob.key,
        transcript=transport.transcript,
    )
