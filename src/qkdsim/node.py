"""Run one BB84 party per process: python -m qkdsim.node {alice,bob,eve} [options]

Each party has its own module (qkdsim.alice, qkdsim.bob) with its class and its process; this
module picks one to run and holds what the party processes share: ports, logging and the final
report. Eve's process is still here until she gets her own module.

docker-compose.yml starts each party in its own container. Topology:

    alice ──quantum──▶ bob                  (no Eve)
    alice ──quantum──▶ eve ──quantum──▶ bob (with Eve: Alice is pointed at Eve instead)
    alice ◀──classical (TCP)──▶ bob

Neither Alice nor Bob is told whether Eve is present; they find out from the QBER.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from typing import TYPE_CHECKING

import numpy as np

from qkdsim import net
from qkdsim.params import QBER_THRESHOLD
from qkdsim.quantum import InterceptResendEve
from qkdsim.rng import SystemRandom

if TYPE_CHECKING:
    from qkdsim.alice import Alice
    from qkdsim.bob import Bob

CLASSICAL_PORT = 5000
QUANTUM_PORT = 5001
ROLES = ("alice", "bob", "eve")


def log(who: str, text: str) -> None:
    print(f"[{who}] {text}", flush=True)


def bits_str(bits: np.ndarray, limit: int) -> str:
    s = "".join(map(str, bits[:limit]))
    return s + ("..." if len(bits) > limit else "")


def add_common_args(p: argparse.ArgumentParser) -> None:
    """Options Alice and Bob both take."""
    p.add_argument("--show", type=int, default=32, help="how many bits to print")
    p.add_argument("--threshold", type=float, default=QBER_THRESHOLD, help="QBER abort threshold")


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


def eve_main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="qkdsim.node eve",
                                description="Run Eve, an intercept-resend eavesdropper on the "
                                            "quantum channel.")
    p.add_argument("--show", type=int, default=32, help="how many bits to print")
    p.add_argument("--listen-port", type=int, default=QUANTUM_PORT)
    p.add_argument("--forward", default=f"bob:{QUANTUM_PORT}", help="Bob's quantum host:port")
    return run_eve(p.parse_args(argv))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="qkdsim.node", description="Run one BB84 party.",
                                epilog="Options after the role go to that party, "
                                       "e.g. python -m qkdsim.node alice --help")
    p.add_argument("role", choices=ROLES)
    p.add_argument("args", nargs=argparse.REMAINDER, help="options for that party")
    ns = p.parse_args(argv)
    # Imported here, not at the top: alice.py and bob.py import this module's helpers.
    if ns.role == "alice":
        from qkdsim.alice import main as party_main
    elif ns.role == "bob":
        from qkdsim.bob import main as party_main
    else:
        party_main = eve_main
    return party_main(ns.args)


if __name__ == "__main__":
    sys.exit(main())
