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


def test_transcript_has_sifting_and_qber_messages():
    r = run_bb84(100, seed=0)
    assert [(e.sender, e.recipient, e.kind) for e in r.transcript] == [
        ("bob", "alice", "bases"),
        ("alice", "bob", "sift"),
        ("alice", "bob", "sample"),
        ("bob", "alice", "qber"),
    ]


def test_rejects_nonpositive_pulses():
    with pytest.raises(ValueError):
        run_bb84(0)


def test_no_eve_gives_zero_qber_and_a_key():
    r = run_bb84(4000, seed=3)
    assert r.qber == 0 and not r.aborted
    assert r.keys_match
    assert len(r.alice_key) == r.sifted_bits - r.sample_size


def test_sample_is_removed_from_key():
    r = run_bb84(1000, seed=4, sample_fraction=0.5)
    assert abs(r.sample_size - r.sifted_bits / 2) <= 1
    assert len(r.alice_key) == len(r.bob_key) == r.sifted_bits - r.sample_size


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_intercept_resend_eve_is_detected(seed):
    r = run_bb84(4000, seed=seed, eve=True)
    # Expected QBER 25%; sample ~500 bits gives sigma ~2%.
    assert 0.17 < r.qber < 0.33
    assert r.aborted
    assert not r.keys_match


def test_eve_and_channel_are_exclusive():
    from qkdsim.quantum import PerfectChannel
    with pytest.raises(ValueError):
        run_bb84(100, eve=True, channel=PerfectChannel())
