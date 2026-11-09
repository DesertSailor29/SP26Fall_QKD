"""Run one BB84 party per process: python -m qkdsim.node {alice,bob,eve} [options]

docker-compose.yml starts each party in its own container. Topology:

    alice ──quantum──▶ bob                  (no Eve)
    alice ──quantum──▶ eve ──quantum──▶ bob (with Eve: Alice is pointed at Eve instead)
    alice ◀──classical (TCP)──▶ bob

Neither Alice nor Bob is told whether Eve is present; they find out from the QBER.
"""

import argparse
import hashlib
import sys

import numpy as np

from qkdsim import net
from qkdsim.parties import Alice, Bob
from qkdsim.protocol import QBER_THRESHOLD, SAMPLE_FRACTION
from qkdsim.quantum import InterceptResendEve
from qkdsim.rng import SystemRandom

CLASSICAL_PORT = 5000
QUANTUM_PORT = 5001


def log(who: str, text: str) -> None:
    print(f"[{who}] {text}", flush=True)


def bits_str(bits: np.ndarray, limit: int) -> str:
    s = "".join(map(str, bits[:limit]))
    return s + ("..." if len(bits) > limit else "")


def report(who: str, party: Alice | Bob, threshold: float, show: int) -> int:
    log(who, f"sifted key: {len(party.sifted_key)} bits")
    log(who, f"QBER {party.qber:.1%} on {party.sample_size} sample bits "
             f"(abort above {threshold:.0%})")
    if party.qber > threshold:
        log(who, "ABORT: error rate too high, the channel may be eavesdropped; key discarded")
        return 0
    digest = hashlib.sha256(np.packbits(party.key).tobytes()).hexdigest()[:16]
    log(who, f"final key: {len(party.key)} bits  {bits_str(party.key, show)}")
    log(who, f"key fingerprint (sha256): {digest}  <- compare with the other side")
    return 0


def run_alice(args: argparse.Namespace) -> int:
    alice_rng = SystemRandom()
    log("alice", f"connecting classical channel to bob at {args.bob}")
    endpoint = net.TcpEndpoint("alice", net.connect(args.bob))
    alice = Alice(endpoint, alice_rng)

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


def run_bob(args: argparse.Namespace) -> int:
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


def run_eve(args: argparse.Namespace) -> int:
    server = net.listen(args.listen_port)
    log("eve", f"tapping the quantum channel on :{args.listen_port}, forwarding to {args.forward}")
    with net.accept(server) as asock:
        pulses = net.recv_pulses(asock)
    server.close()

    eve = InterceptResendEve(SystemRandom())
    resent = eve.transmit(pulses)
    log("eve", f"intercepted {len(pulses)} pulses, measured each in a random basis")
    log("eve", f"bases: {bits_str(eve.bases, args.show)}")
    log("eve", f"bits : {bits_str(eve.results, args.show)}")

    with net.connect(args.forward) as bsock:
        net.send_pulses(bsock, resent)
    log("eve", "resent my measurement results to bob")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="qkdsim.node", description="Run one BB84 party.")
    p.add_argument("--show", type=int, default=32, help="how many bits to print")
    p.add_argument("--threshold", type=float, default=QBER_THRESHOLD, help="QBER abort threshold")
    sub = p.add_subparsers(dest="role", required=True)

    a = sub.add_parser("alice", help="sender")
    a.add_argument("-n", "--pulses", type=int, default=1000, help="qubits to send")
    a.add_argument("--bob", default=f"bob:{CLASSICAL_PORT}", help="Bob's classical host:port")
    a.add_argument("--quantum", default=f"bob:{QUANTUM_PORT}",
                   help="where the quantum channel goes, host:port (Bob, or Eve to tap it)")
    a.add_argument("--sample-fraction", type=float, default=SAMPLE_FRACTION,
                   help="share of the sifted key sacrificed for the QBER estimate")

    b = sub.add_parser("bob", help="receiver")
    b.add_argument("--classical-port", type=int, default=CLASSICAL_PORT)
    b.add_argument("--quantum-port", type=int, default=QUANTUM_PORT)

    e = sub.add_parser("eve", help="intercept-resend eavesdropper on the quantum channel")
    e.add_argument("--listen-port", type=int, default=QUANTUM_PORT)
    e.add_argument("--forward", default=f"bob:{QUANTUM_PORT}", help="Bob's quantum host:port")

    args = p.parse_args(argv)
    if args.role == "alice" and args.pulses <= 0:
        p.error("--pulses must be positive")
    return {"alice": run_alice, "bob": run_bob, "eve": run_eve}[args.role](args)


if __name__ == "__main__":
    sys.exit(main())
