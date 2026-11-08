"""Randomness sources.

Normal runs draw from the OS CSPRNG (os.urandom). Tests inject a seeded NumPy generator so runs are
reproducible. Never use the `random` module for protocol randomness.
"""

import os
from typing import Protocol

import numpy as np


class RandomSource(Protocol):
    def bits(self, n: int) -> np.ndarray:
        """Return n independent uniform bits as a uint8 array of 0s and 1s."""
        ...


class SystemRandom:
    """Cryptographically secure bits from os.urandom. The default for real runs."""

    def bits(self, n: int) -> np.ndarray:
        raw = np.frombuffer(os.urandom((n + 7) // 8), dtype=np.uint8)
        return np.unpackbits(raw)[:n].copy()


class SeededRandom:
    """Deterministic bits from a seeded NumPy generator. For tests and reproducible runs only."""

    def __init__(self, seed: int | np.random.SeedSequence) -> None:
        self._gen = np.random.default_rng(seed)

    def bits(self, n: int) -> np.ndarray:
        return self._gen.integers(0, 2, size=n, dtype=np.uint8)
