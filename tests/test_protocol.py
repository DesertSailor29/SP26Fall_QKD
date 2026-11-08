import numpy as np
import pytest

from qkdsim import run_bb84


@pytest.mark.parametrize("seed", [0, 1, 2, None])
def test_sifted_keys_match_without_noise(seed):
    r = run_bb84(2000, seed=seed)
    assert r.keys_match
    assert r.sifted_bits > 0


def test_sifted_length_is_about_half():
    n = 10_000
    r = run_bb84(n, seed=123)
    # Binomial(n, 1/2): sigma = 50. Allow 4 sigma.
    assert abs(r.sifted_bits - n / 2) < 200


def test_seeded_runs_are_reproducible():
    a, b = run_bb84(500, seed=7), run_bb84(500, seed=7)
    assert np.array_equal(a.alice_key, b.alice_key)
    assert [e.raw for e in a.transcript] == [e.raw for e in b.transcript]


def test_different_seeds_differ():
    assert not np.array_equal(run_bb84(500, seed=1).alice_key, run_bb84(500, seed=2).alice_key)


def test_keys_are_not_shared_objects():
    r = run_bb84(500, seed=0)
    assert not np.shares_memory(r.alice_key, r.bob_key)


def test_transcript_has_sifting_messages_only():
    r = run_bb84(100, seed=0)
    assert [(e.sender, e.recipient, e.kind) for e in r.transcript] == [
        ("bob", "alice", "bases"),
        ("alice", "bob", "sift"),
    ]


def test_rejects_nonpositive_pulses():
    with pytest.raises(ValueError):
        run_bb84(0)
