import argparse
import hashlib

import gssapi

from qkdsim import net
from qkdsim.bob import Bob
from qkdsim.params import QBER_THRESHOLD
from qkdsim.rng import SystemRandom


SERVICE_NAME = "bob/localhost@PROJECT.TEST"


def fingerprint(key):
    """Diagnostic fingerprint; never print or transmit the actual key."""
    return hashlib.sha256(key.tobytes()).hexdigest()[:16]


def authenticate(connection, credentials):
    """Accept Alice's Kerberos GSSAPI context and verify mutual authentication."""
    context = gssapi.SecurityContext(
        creds=credentials,
        usage="accept",
    )

    token = net.recv_frame(connection)

    while not context.complete:
        output_token = context.step(token)

        if output_token:
            net.send_frame(connection, output_token)

        if not context.complete:
            token = net.recv_frame(connection)

    print("Kerberos mutual authentication successful.", flush=True)
    print(f"Authenticated client: {context.initiator_name}", flush=True)
    return context


def main():
    parser = argparse.ArgumentParser(description="Kerberos-authenticated BB84 Bob")
    parser.add_argument("--classical-port", type=int, default=5000)
    parser.add_argument("--quantum-port", type=int, default=5001)
    parser.add_argument("--threshold", type=float, default=QBER_THRESHOLD)
    args = parser.parse_args()

    service_name = gssapi.Name(
        SERVICE_NAME,
        name_type=gssapi.NameType.kerberos_principal,
    )

    credentials = gssapi.Credentials(
        name=service_name,
        usage="accept",
    )

    print("Bob's Kerberos identity:", SERVICE_NAME, flush=True)
    print(
        f"Listening on classical port {args.classical_port} "
        f"and quantum port {args.quantum_port}.",
        flush=True,
    )

    with net.listen(args.classical_port) as classical_server, \
            net.listen(args.quantum_port) as quantum_server:

        while True:
            connection = net.accept(classical_server)
            endpoint = None

            try:
                print("\nAlice connected on the classical channel.", flush=True)

                context = authenticate(connection, credentials)

                endpoint = net.GssapiTcpEndpoint(
                    name="bob",
                    sock=connection,
                    context=context,
                    peer="alice",
                )

                bob = Bob(endpoint, SystemRandom())

                print("Waiting for quantum pulses...", flush=True)

                with net.accept(quantum_server) as quantum_socket:
                    pulses = net.recv_pulses(quantum_socket)

                print(f"Received {len(pulses)} quantum pulses.", flush=True)

                bob.measure(pulses)
                print("Measured pulses in random bases.", flush=True)

                bob.announce_bases()
                bob.sift()
                qber = bob.estimate_qber()

                accepted = qber <= args.threshold

                print(f"Measured QBER: {qber:.4f}", flush=True)
                print(f"QBER threshold: {args.threshold:.4f}", flush=True)
                print(f"QBER decision: {'ACCEPT' if accepted else 'ABORT'}",
                      flush=True)

                if bob.key is None:
                    raise RuntimeError("Bob did not produce a sifted key")

                bob_fingerprint = fingerprint(bob.key)

                # Diagnostic key comparison for this simulation.
                check = endpoint.recv("key_check")
                alice_fingerprint = check.payload["fingerprint"]
                keys_match = alice_fingerprint == bob_fingerprint

                endpoint.send("alice", "key_check_result", {
                    "fingerprint": bob_fingerprint,
                    "match": keys_match,
                })

                print(f"Alice key fingerprint: {alice_fingerprint}", flush=True)
                print(f"Bob key fingerprint:   {bob_fingerprint}", flush=True)
                print(f"Keys match: {keys_match}", flush=True)

                if accepted and keys_match:
                    print("BB84 simulation completed successfully.", flush=True)
                else:
                    print("BB84 session failed its acceptance checks.", flush=True)

            except Exception as error:
                print(f"BB84 session failed: {error}", flush=True)

            finally:
                if endpoint is not None:
                    endpoint.close()
                else:
                    connection.close()


if __name__ == "__main__":
    main()
