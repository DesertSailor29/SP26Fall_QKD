"""qkdsim: a software simulation of BB84 quantum key distribution.

Phase 1: prepare, measure, sift and estimate the QBER, with an optional intercept-resend Eve.
No noise and no authentication yet.
"""

__all__ = ["BB84Result", "run_bb84"]


def __getattr__(name: str):
    # Imported lazily, so that `python -m qkdsim.alice` (or .bob) does not load that module once
    # through the package and then again as __main__.
    if name in __all__:
        from qkdsim import protocol
        return getattr(protocol, name)
    raise AttributeError(f"module 'qkdsim' has no attribute {name!r}")
