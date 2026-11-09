import numpy as np
import pytest

from qkdsim.parties import sample_size
from qkdsim.quantum import InterceptResendEve, PerfectChannel, Pulses, measure
from qkdsim.rng import SeededRandom, SystemRandom
from qkdsim.sifting import matching_mask, sift
from qkdsim.transport import InMemoryTransport, TransportError, decode_bits, encode_bits

# --- rng ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("src", [SystemRandom(), SeededRandom(1)])
@pytest.mark.parametrize("n", [1, 7, 8, 9, 1000])
def test_bits_shape_and_values(src, n):
    b = src.bits(n)
    assert b.shape == (n,) and b.dtype == np.uint8
    assert set(np.unique(b)) <= {0, 1}


def test_seeded_is_reproducible():
    assert np.array_equal(SeededRandom(5).bits(100), SeededRandom(5).bits(100))


# --- quantum -----------------------------------------------------------------------------------

def test_matching_basis_returns_prepared_bit():
    rng = SeededRandom(0)
    p = Pulses(bits=rng.bits(1000), bases=rng.bits(1000))
    assert np.array_equal(measure(p, p.bases.copy(), rng), p.bits)


def test_wrong_basis_gives_coin_flip():
    n = 10_000
    p = Pulses(bits=np.zeros(n, np.uint8), bases=np.zeros(n, np.uint8))
    out = measure(p, np.ones(n, np.uint8), SeededRandom(0))
    assert abs(out.mean() - 0.5) < 0.02  # ~4 sigma


def test_perfect_channel_copies():
    p = Pulses(bits=np.array([0, 1], np.uint8), bases=np.array([1, 0], np.uint8))
    q = PerfectChannel().transmit(p)
    assert np.array_equal(p.bits, q.bits) and np.array_equal(p.bases, q.bases)
    assert not np.shares_memory(p.bits, q.bits)


def test_pulses_reject_mismatched_lengths():
    with pytest.raises(ValueError):
        Pulses(bits=np.zeros(3, np.uint8), bases=np.zeros(4, np.uint8))


# --- sifting -----------------------------------------------------------------------------------

def test_sifting_keeps_matching_positions():
    a = np.array([0, 1, 0, 1, 1], np.uint8)
    b = np.array([0, 0, 0, 1, 0], np.uint8)
    mask = matching_mask(a, b)
    assert mask.tolist() == [True, False, True, True, False]
    assert sift(np.array([1, 1, 0, 1, 0], np.uint8), mask).tolist() == [1, 0, 1]


# --- transport ---------------------------------------------------------------------------------

def test_send_recv_roundtrip_and_transcript():
    t = InMemoryTransport()
    a, b = t.endpoint("alice"), t.endpoint("bob")
    a.send("bob", "hello", {"x": 1})
    msg = b.recv("hello")
    assert (msg.sender, msg.recipient, msg.payload) == ("alice", "bob", {"x": 1})
    assert len(t.transcript) == 1 and t.transcript[0].kind == "hello"


def test_payload_is_copied_not_shared():
    t = InMemoryTransport()
    a, b = t.endpoint("alice"), t.endpoint("bob")
    payload = {"xs": [1, 2]}
    a.send("bob", "m", payload)
    payload["xs"].append(3)
    assert b.recv("m").payload == {"xs": [1, 2]}


def test_recv_errors():
    t = InMemoryTransport()
    a, b = t.endpoint("alice"), t.endpoint("bob")
    with pytest.raises(TransportError):
        b.recv("m")
    a.send("bob", "m", {})
    with pytest.raises(TransportError):
        b.recv("other")
    with pytest.raises(TransportError):
        a.send("carol", "m", {})


@pytest.mark.parametrize("n", [0, 1, 8, 13, 1000])
def test_bit_codec_roundtrip(n):
    bits = SeededRandom(n).bits(n)
    assert np.array_equal(decode_bits(encode_bits(bits)), bits)


@pytest.mark.parametrize("src", [SystemRandom(), SeededRandom(0)])
def test_sample_positions_are_distinct_sorted_in_range(src):
    idx = src.sample(100, 30)
    assert len(idx) == 30 == len(set(idx.tolist()))
    assert list(idx) == sorted(idx) and idx.min() >= 0 and idx.max() < 100


def test_sample_size_bounds():
    assert sample_size(100, 0.25) == 25
    assert sample_size(1, 0.25) == 1
    with pytest.raises(ValueError):
        sample_size(0, 0.25)
    with pytest.raises(ValueError):
        sample_size(10, 0)


def test_eve_resends_in_her_own_bases():
    rng = SeededRandom(5)
    pulses = Pulses(bits=rng.bits(1000), bases=rng.bits(1000))
    eve = InterceptResendEve(SeededRandom(6))
    out = eve.transmit(pulses)
    assert np.array_equal(out.bases, eve.bases) and np.array_equal(out.bits, eve.results)
    same = eve.bases == pulses.bases
    assert np.array_equal(out.bits[same], pulses.bits[same])
