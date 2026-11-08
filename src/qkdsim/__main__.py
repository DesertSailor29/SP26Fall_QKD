"""Command line: python -m qkdsim -n 1000 [--seed 42] [--show 32]"""

import argparse

from qkdsim.protocol import run_bb84


def main() -> None:
    p = argparse.ArgumentParser(prog="qkdsim", description="Run one BB84 session (phase 1).")
    p.add_argument("-n", "--pulses", type=int, default=1000, help="qubits Alice sends")
    p.add_argument("--seed", type=int, default=None, help="seed for a reproducible run")
    p.add_argument("--show", type=int, default=32, help="how many key bits to print")
    args = p.parse_args()

    r = run_bb84(args.pulses, seed=args.seed)
    print(f"pulses sent     : {r.n_pulses}")
    print(f"sifted bits     : {r.sifted_bits} ({r.sifted_bits / r.n_pulses:.1%})")
    print(f"keys match      : {r.keys_match}")
    print(f"alice key       : {''.join(map(str, r.alice_key[: args.show]))}...")
    print(f"bob key         : {''.join(map(str, r.bob_key[: args.show]))}...")
    print("classical transcript (what Eve sees):")
    for e in r.transcript:
        print(f"  #{e.seq} {e.sender} -> {e.recipient} {e.kind:6s} {e.size} bytes")


if __name__ == "__main__":
    main()
