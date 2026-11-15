"""Alice, the sender: python -m qkdsim.alice [options]

She prepares random bits in random bases, sends them over the quantum channel, and then runs her
side of the classical post-processing with Bob (message flow: see qkdsim.protocol). She owns her
own randomness and secrets and talks to Bob only through her transport endpoint.

As a process she connects to Bob's classical port, and sends the pulses to whatever address she is
given for the quantum channel: Bob, or Eve tapping it. She is not told which.
"""

import argparse
import sys

import numpy as np

from qkdsim import net
from qkdsim.node import CLASSICAL_PORT, QUANTUM_PORT, add_common_args, bits_str, log, report
from qkdsim.params import SAMPLE_FRACTION
from qkdsim.quantum import Pulses
from qkdsim.rng import RandomSource, SystemRandom
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


def run(args: argparse.Namespace) -> int:
    """Run Alice as her own process (e.g. her own container) over TCP."""
    log("alice", f"connecting classical channel to bob at {args.bob}")
    endpoint = net.TcpEndpoint("alice", net.connect(args.bob))
    alice = Alice(endpoint, SystemRandom())

    pulses = alice.prepare(args.pulses)
    log("alice", f"bits : {bits_str(alice._bits, args.show)}")
    log("alice", f"bases: {bits_str(alice._bases, args.show)}")
    log("alice", f"sending {args.pulses} pulses over the quantum channel to {args.quantum}")
    with net.connect(args.quantum) as qsock:
        net.send_pulses(qsock, pulses)

    alice.sift()
    alice.send_sample(args.sample_fraction)
    alice.receive_qber()
    endpoint.close()

    log("alice", "classical transcript (public, Eve may read all of it):")
    for e in endpoint.transcript:
        log("alice", f"  #{e.seq} {e.sender} -> {e.recipient} {e.kind:6s} {e.size} bytes")
    return report("alice", alice, args.threshold, args.show)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="qkdsim.alice", description="Run Alice, the sender.")
    add_common_args(p)
    p.add_argument("-n", "--pulses", type=int, default=1000, help="qubits to send")
    p.add_argument("--bob", default=f"bob:{CLASSICAL_PORT}", help="Bob's classical host:port")
    p.add_argument("--quantum", default=f"bob:{QUANTUM_PORT}",
                   help="where the quantum channel goes, host:port (Bob, or Eve to tap it)")
    p.add_argument("--sample-fraction", type=float, default=SAMPLE_FRACTION,
                   help="share of the sifted key sacrificed for the QBER estimate")
    args = p.parse_args(argv)
    if args.pulses <= 0:
        p.error("--pulses must be positive")
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
