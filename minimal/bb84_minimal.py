"""Bare-bones BB84, just functions, so you can see each step.

A qubit is modelled as a (bit, basis) pair. Basis 0 = rectilinear (+), basis 1 = diagonal (x).
Measuring in the same basis it was prepared in returns the bit; measuring in the other basis
returns a random bit. Nothing else from quantum mechanics is modelled.

Run:  python minimal/bb84_minimal.py
"""

import random


def random_bits(n):
    return [random.randint(0, 1) for _ in range(n)]


def alice_prepare(bits, bases):
    """Alice encodes each bit in her chosen basis -> list of 'qubits'."""
    return list(zip(bits, bases))


def measure(qubit, basis):
    """Measure one qubit in a basis. Wrong basis = coin flip."""
    bit, prep_basis = qubit
    if basis == prep_basis:
        return bit
    return random.randint(0, 1)


def eve_intercept(qubits):
    """Intercept-resend attack: Eve measures in a random basis and resends what she saw."""
    eve_bases = random_bits(len(qubits))
    return [(measure(q, b), b) for q, b in zip(qubits, eve_bases)]


def bob_measure(qubits, bases):
    return [measure(q, b) for q, b in zip(qubits, bases)]


def sift(alice_bases, bob_bases, bits):
    """Keep only the positions where Alice and Bob used the same basis."""
    return [bit for a, b, bit in zip(alice_bases, bob_bases, bits) if a == b]


def estimate_qber(alice_key, bob_key, sample_size):
    """Publicly compare a random sample of the sifted key, then throw that sample away."""
    idx = set(random.sample(range(len(alice_key)), sample_size))
    errors = sum(alice_key[i] != bob_key[i] for i in idx)
    alice_rest = [b for i, b in enumerate(alice_key) if i not in idx]
    bob_rest = [b for i, b in enumerate(bob_key) if i not in idx]
    return errors / sample_size, alice_rest, bob_rest


def show(label, values, limit=20):
    s = "".join(str(v) for v in values[:limit])
    more = "..." if len(values) > limit else ""
    print(f"{label:<22}{s}{more}  ({len(values)})")


def run_bb84(n=200, with_eve=False, sample_fraction=0.25, qber_threshold=0.11):
    print(f"\n=== BB84, n={n}, eve={'yes' if with_eve else 'no'} ===")

    # 1. Alice picks random bits and random bases, prepares qubits
    alice_bits = random_bits(n)
    alice_bases = random_bits(n)
    qubits = alice_prepare(alice_bits, alice_bases)
    show("Alice bits", alice_bits)
    show("Alice bases", alice_bases)

    # 2. Quantum channel (optionally Eve in the middle)
    if with_eve:
        qubits = eve_intercept(qubits)

    # 3. Bob picks random bases and measures
    bob_bases = random_bits(n)
    bob_bits = bob_measure(qubits, bob_bases)
    show("Bob bases", bob_bases)
    show("Bob bits", bob_bits)

    # 4. Sifting: bases are announced publicly, keep matching positions
    alice_sifted = sift(alice_bases, bob_bases, alice_bits)
    bob_sifted = sift(alice_bases, bob_bases, bob_bits)
    show("Alice sifted", alice_sifted)
    show("Bob sifted", bob_sifted)

    # 5. Error estimation on a sacrificed sample
    sample_size = max(1, int(len(alice_sifted) * sample_fraction))
    qber, alice_key, bob_key = estimate_qber(alice_sifted, bob_sifted, sample_size)
    print(f"QBER on {sample_size} sample bits: {qber:.1%}")

    # 6. Decide
    if qber > qber_threshold:
        print(f"ABORT: QBER above {qber_threshold:.0%}, channel likely eavesdropped")
        return None
    show("Final key (Alice)", alice_key)
    show("Final key (Bob)", bob_key)
    print("Keys match:", alice_key == bob_key)
    return alice_key


if __name__ == "__main__":
    run_bb84(with_eve=False)
    run_bb84(with_eve=True)
