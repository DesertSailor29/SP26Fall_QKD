import pytest

from qkdsim.interfaces import AuthError, ChannelError
from qkdsim.mocks import AuthenticatedChannel, channel_pair
from qkdsim.psk import KEY_BYTES, PSKAuthenticator


@pytest.fixture
def auth():
    a = PSKAuthenticator()
    a.enroll("alice")
    a.enroll("bob")
    return a


def sessions(auth):
    raw_a, raw_b = channel_pair()
    return auth.establish("alice", "bob", raw_a), auth.establish("bob", "alice", raw_b)


# --- normal use --------------------------------------------------------------------------------

def test_messages_get_through_both_ways(auth):
    raw_a, raw_b = channel_pair()
    alice = AuthenticatedChannel(raw_a, auth.establish("alice", "bob", raw_a))
    bob = AuthenticatedChannel(raw_b, auth.establish("bob", "alice", raw_b))
    for i in range(5):
        alice.send(f"hello {i}".encode())
        assert bob.recv() == f"hello {i}".encode()
        bob.send(b"ack")
        assert alice.recv() == b"ack"


def test_empty_message(auth):
    a, b = sessions(auth)
    assert b.unprotect(a.protect(b"")) == b""


def test_separate_programs_with_same_provisioned_key():
    key = bytes(range(KEY_BYTES))
    alice_side = PSKAuthenticator(keys={("alice", "bob"): key})
    bob_side = PSKAuthenticator(keys={("bob", "alice"): key})
    a = alice_side.establish("alice", "bob", None)
    b = bob_side.establish("bob", "alice", None)
    assert b.unprotect(a.protect(b"sifting data")) == b"sifting data"


# --- attacks: every one must raise AuthError ---------------------------------------------------

@pytest.mark.parametrize("pos", [0, 7, 8, 12, -1])  # counter, message, tag
def test_tampered_byte_is_rejected(auth, pos):
    a, b = sessions(auth)
    wire = bytearray(a.protect(b"bases: 0110"))
    wire[pos] ^= 0x01
    with pytest.raises(AuthError):
        b.unprotect(bytes(wire))


def test_replay_is_rejected(auth):
    a, b = sessions(auth)
    wire = a.protect(b"go ahead")
    b.unprotect(wire)
    with pytest.raises(AuthError):
        b.unprotect(wire)


def test_reordering_is_rejected(auth):
    a, b = sessions(auth)
    first, second = a.protect(b"1"), a.protect(b"2")
    with pytest.raises(AuthError):
        b.unprotect(second)
    assert b.unprotect(first) == b"1"


def test_reflection_is_rejected(auth):
    a, _ = sessions(auth)
    with pytest.raises(AuthError):
        a.unprotect(a.protect(b"my own message"))


def test_wrong_key_is_rejected():
    one, two = PSKAuthenticator(), PSKAuthenticator()
    for x in (one, two):
        x.enroll("alice")
        x.enroll("bob")
    a = one.establish("alice", "bob", None)
    b = two.establish("bob", "alice", None)
    with pytest.raises(AuthError):
        b.unprotect(a.protect(b"hi"))


def test_message_meant_for_someone_else_is_rejected():
    auth = PSKAuthenticator()
    for n in ("alice", "bob", "carol"):
        auth.enroll(n)
    to_bob = auth.establish("alice", "bob", None)
    carol = auth.establish("carol", "alice", None)
    with pytest.raises(AuthError):
        carol.unprotect(to_bob.protect(b"for bob"))


def test_truncated_message_is_rejected(auth):
    a, b = sessions(auth)
    with pytest.raises(AuthError):
        b.unprotect(a.protect(b"x")[:20])


def test_unenrolled_node_cannot_establish(auth):
    with pytest.raises(AuthError):
        auth.establish("alice", "eve", None)


def test_closed_session_refuses(auth):
    a, _ = sessions(auth)
    a.close()
    with pytest.raises(AuthError):
        a.protect(b"x")


# --- bookkeeping -------------------------------------------------------------------------------

def test_storage_grows_with_number_of_peers():
    auth = PSKAuthenticator()
    for n in ("a", "b", "c", "d"):
        auth.enroll(n)
    assert all(auth.storage_bytes(n) == 3 * KEY_BYTES for n in "abcd")


def test_bad_key_length_is_refused():
    with pytest.raises(ValueError):
        PSKAuthenticator(keys={("alice", "bob"): b"short"})


def test_in_memory_channel_errors():
    a, b = channel_pair()
    with pytest.raises(ChannelError):
        b.recv()
    a.close()
    with pytest.raises(ChannelError):
        a.send(b"x")
