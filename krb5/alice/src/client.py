import argparse
import hashlib

import gssapi

from qkdsim import net
from qkdsim.alice import Alice
from qkdsim.params import SAMPLE_FRACTION, QBER_THRESHOLD
from qkdsim.rng import SystemRandom


SERVICE_NAME = "bob/localhost@PROJECT.TEST"


def authenticate(connection):
    """Establish a mutually authenticated Kerberos GSSAPI context."""
    service_name = gssapi.Name(
        SERVICE_NAME,
        name_type=gssapi.NameType.kerberos_principal,
    )

    context = gssapi.SecurityContext(
        name=service_name,
        usage="initiate",
        flags=[
            gssapi.RequirementFlag.mutual_authentication,
            gssapi.RequirementFlag.confidentiality,
        ],
    )

    token = context.step()
    if token:
        net.send_frame(connection, token)

    while not context.complete:
        server_token = net.recv_frame(connection)
        token = context.step(server_token)
        if token:
            net.send_frame(connection, token)

    print("Kerberos mutual authentication successful.", flush=True)
    print(f"Authenticated server: {context.target_name}", flush=True)
    return context


def fingerprint(key):
    """Diagnostic fingerprint; never print or transmit the actual key."""
    return hashlib.sha256(key.tobytes()).hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser(description="Kerberos-authenticated BB84 Alice")
    parser.add_argument("--bob", default="bob:5000")
    parser.add_argument("--quantum", default="bob:5001")
    parser.add_argument("-n", "--pulses", type=int, default=1000)
    parser.add_argument("--sample-fraction", type=float, default=SAMPLE_FRACTION)
    parser.add_argument("--threshold", type=float, default=QBER_THRESHOLD)
    args = parser.parse_args()

    if args.pulses <= 0:
        parser.error("--pulses must be positive")
    if not 0 < args.sample_fraction <= 1:
        parser.error("--sample-fraction must be in (0, 1]")

    print(f"Connecting to Bob's classical channel at {args.bob}...", flush=True)

    connection = net.connect(args.bob)
    endpoint = None

    try:
        context = authenticate(connection)

        endpoint = net.GssapiTcpEndpoint(
            name="alice",
            sock=connection,
            context=context,
            peer="bob",
        )

        alice = Alice(endpoint, SystemRandom())

        pulses = alice.prepare(args.pulses)
        print(f"Prepared {args.pulses} random BB84 pulses.", flush=True)

        print(f"Sending pulses over the simulated quantum channel to {args.quantum}...",
              flush=True)
        with net.connect(args.quantum) as quantum_socket:
            net.send_pulses(quantum_socket, pulses)

        print("Quantum pulses sent.", flush=True)

        alice.sift()
        print(f"Sifting complete: {len(alice.sifted_key)} bits retained.",
              flush=True)

        alice.send_sample(args.sample_fraction)
        print(f"Revealed {alice.sample_size} sample bits for QBER estimation.",
              flush=True)

        qber = alice.receive_qber()
        accepted = qber <= args.threshold

        print(f"Measured QBER: {qber:.4f}", flush=True)
        print(f"QBER threshold: {args.threshold:.4f}", flush=True)
        print(f"QBER decision: {'ACCEPT' if accepted else 'ABORT'}", flush=True)

        if alice.key is None:
            raise RuntimeError("Alice did not produce a sifted key")

        alice_fingerprint = fingerprint(alice.key)

        # Diagnostic key comparison for this simulation.
        endpoint.send("bob", "key_check", {
            "fingerprint": alice_fingerprint,
        })
        result = endpoint.recv("key_check_result")

        print(f"Alice key fingerprint: {alice_fingerprint}", flush=True)
        print(f"Bob key fingerprint:   {result.payload['fingerprint']}", flush=True)
        print(f"Keys match: {result.payload['match']}", flush=True)

        if not accepted:
            print("BB84 session aborted because QBER exceeded the threshold.",
                  flush=True)
            return 1

        if not result.payload["match"]:
            print("BB84 key comparison failed.", flush=True)
            return 1

        print("BB84 simulation completed successfully.", flush=True)
        return 0

    finally:
        if endpoint is not None:
            endpoint.close()
        else:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
