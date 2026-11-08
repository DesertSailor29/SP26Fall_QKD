"""The simulated quantum channel.

BB84 outcomes follow simple rules, so no quantum-state simulation is needed:
measuring in the basis the qubit was prepared in returns the prepared bit, and measuring in the
other basis returns a uniformly random bit.

Basis encoding: 0 = rectilinear (Z, +), 1 = diagonal (X, x).
"""

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from qkdsim.rng import RandomSource

RECTILINEAR = 0
DIAGONAL = 1


@dataclass(frozen=True)
class Pulses:
    """A batch of qubits in flight: pulse i encodes bits[i] in bases[i].

    Only the quantum channel and a measuring party may look inside. Eve, when added, will
    interact with pulses only by measuring them, which disturbs them like a real measurement.
    """

    bits: np.ndarray
    bases: np.ndarray

    def __post_init__(self) -> None:
        if self.bits.shape != self.bases.shape or self.bits.ndim != 1:
            raise ValueError("bits and bases must be 1-D arrays of equal length")

    def __len__(self) -> int:
        return len(self.bits)


def measure(pulses: Pulses, bases: np.ndarray, rng: RandomSource) -> np.ndarray:
    """Measure each pulse in the given basis and return the outcomes."""
    if bases.shape != pulses.bases.shape:
        raise ValueError("one measurement basis is needed per pulse")
    coin = rng.bits(len(pulses))
    return np.where(bases == pulses.bases, pulses.bits, coin).astype(np.uint8)


class QuantumChannel(Protocol):
    def transmit(self, pulses: Pulses) -> Pulses:
        """Carry pulses from sender to receiver, applying any noise or eavesdropping."""
        ...


class PerfectChannel:
    """No loss, no noise, no eavesdropper. Copies arrays so sender and receiver share nothing."""

    def transmit(self, pulses: Pulses) -> Pulses:
        return Pulses(bits=pulses.bits.copy(), bases=pulses.bases.copy())
