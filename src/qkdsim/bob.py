"""Bob, the receiver: python -m qkdsim.bob [options]

He measures every incoming pulse in a random basis, then runs his side of the classical
post-processing with Alice (message flow: see qkdsim.protocol). He owns his own randomness and
secrets and talks to Alice only through his transport endpoint.

As a process he listens on two ports, one per channel. Alice connects to the classical one; the
quantum one is reached by Alice, or by Eve when she taps the link.
"""

import argparse
import sys

import numpy as np

from qkdsim import net
from qkdsim.node import CLASSICAL_PORT, QUANTUM_PORT, add_common_args, bits_str, log, report
from qkdsim.quantum import Pulses, measure
from qkdsim.rng import RandomSource, SystemRandom
from qkdsim.sifting import sift
from qkdsim.transport import Endpoint, decode_bits, encode_bits


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


def run(args: argparse.Namespace) -> int:
    """Run Bob as his own process (e.g. his own container) over TCP."""
    classical = net.listen(args.classical_port)
    quantum = net.listen(args.quantum_port)
    log("bob", f"listening: classical :{args.classical_port}, quantum :{args.quantum_port}")

    endpoint = net.TcpEndpoint("bob", net.accept(classical))
    log("bob", "classical channel connected")
    bob = Bob(endpoint, SystemRandom())

    with net.accept(quantum) as qsock:
        pulses = net.recv_pulses(qsock)
    bob.measure(pulses)
    log("bob", f"received {len(pulses)} pulses, measured in random bases")
    log("bob", f"bases: {bits_str(bob._bases, args.show)}")
    log("bob", f"bits : {bits_str(bob._results, args.show)}")

    bob.announce_bases()
    bob.sift()
    bob.estimate_qber()
    endpoint.close()
    classical.close()
    quantum.close()
    return report("bob", bob, args.threshold, args.show)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="qkdsim.bob", description="Run Bob, the receiver.")
    add_common_args(p)
    p.add_argument("--classical-port", type=int, default=CLASSICAL_PORT)
    p.add_argument("--quantum-port", type=int, default=QUANTUM_PORT)
    return run(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
