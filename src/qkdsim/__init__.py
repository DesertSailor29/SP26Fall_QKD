"""qkdsim: a software simulation of BB84 quantum key distribution.

Phase 1: prepare, measure and sift over a perfect channel. No noise, no Eve, no authentication.
"""

from qkdsim.protocol import BB84Result, run_bb84

__all__ = ["BB84Result", "run_bb84"]
