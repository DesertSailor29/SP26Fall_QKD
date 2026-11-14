"""Basis sifting: keep only the positions where Alice and Bob used the same basis."""

import numpy as np


def matching_mask(bases_a: np.ndarray, bases_b: np.ndarray) -> np.ndarray:
    if bases_a.shape != bases_b.shape:
        raise ValueError("basis arrays must have equal length")
    return bases_a == bases_b


def sift(bits: np.ndarray, mask: np.ndarray) -> np.ndarray:
    if bits.shape != mask.shape:
        raise ValueError("bits and mask must have equal length")
    return bits[mask].copy()
