"""Command line: python -m qkdsim -n 1000 [--eve] [--seed 42] [--show 32]

Runs all parties in one process. For one container per party, see run.sh and qkdsim.node.
"""

import argparse

from qkdsim.protocol import QBER_THRESHOLD, run_bb84


def main() -> None:
    p = argparse.ArgumentParser(prog="qkdsim", description="Run one BB84 session in one process.")
    p.add_argument("-n", "--pulses", type=int, default=1000, help="qubits Alice sends")
    p.add_argument("--eve", action="store_true", help="put an intercept-resend Eve on the channel")
    p.add_argument("--seed", type=int, default=None, help="seed for a reproducible run")
    p.add_argument("--show", type=int, default=32, help="how many key bits to print")
    args = p.parse_args()

    r = run_bb84(args.pulses, seed=args.seed, eve=args.eve)
    print(f"eavesdropper    : {'intercept-resend' if args.eve else 'none'}")
    print(f"pulses sent     : {r.n_pulses}")
    print(f"sifted bits     : {r.sifted_bits} ({r.sifted_bits / r.n_pulses:.1%})")
    print(f"QBER            : {r.qber:.1%} on {r.sample_size} sample bits "
          f"(abort above {QBER_THRESHOLD:.0%})")
    if r.aborted:
        print("result          : ABORT, key discarded")
    else:
        print(f"final key bits  : {len(r.alice_key)}")
        print(f"keys match      : {r.keys_match}")
        print(f"alice key       : {''.join(map(str, r.alice_key[: args.show]))}...")
        print(f"bob key         : {''.join(map(str, r.bob_key[: args.show]))}...")
    print("classical transcript (what Eve sees):")
    for e in r.transcript:
        print(f"  #{e.seq} {e.sender} -> {e.recipient} {e.kind:6s} {e.size} bytes")


if __name__ == "__main__":
    main()
