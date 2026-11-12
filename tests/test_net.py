"""Run the three nodes as separate processes over real TCP on localhost (what Docker does)."""

import socket
import subprocess
import sys
import time

import numpy as np
import pytest

from qkdsim import net
from qkdsim.quantum import Pulses
from qkdsim.rng import SeededRandom


def free_ports(n):
    socks = [socket.socket() for _ in range(n)]
    for s in socks:
        s.bind(("127.0.0.1", 0))
    ports = [s.getsockname()[1] for s in socks]
    for s in socks:
        s.close()
    return ports


def node(*args, module="qkdsim.node"):
    return subprocess.Popen([sys.executable, "-m", module, *args],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def finish(proc):
    out, _ = proc.communicate(timeout=60)
    assert proc.returncode == 0, out
    return out


def fingerprint(out):
    return next(line.split()[3] for line in out.splitlines() if "fingerprint" in line)


def test_pulses_roundtrip_over_tcp():
    (port,) = free_ports(1)
    rng = SeededRandom(1)
    pulses = Pulses(bits=rng.bits(777), bases=rng.bits(777))
    server = net.listen(port)
    with net.connect(f"127.0.0.1:{port}") as c, net.accept(server) as s:
        net.send_pulses(c, pulses)
        got = net.recv_pulses(s)
    server.close()
    assert np.array_equal(got.bits, pulses.bits) and np.array_equal(got.bases, pulses.bases)


def test_parse_addr():
    assert net.parse_addr("bob:5000") == ("bob", 5000)
    with pytest.raises(ValueError):
        net.parse_addr("bob")


def test_alice_bob_processes_agree():
    cport, qport = free_ports(2)
    bob = node("bob", "--classical-port", str(cport), "--quantum-port", str(qport))
    time.sleep(0.3)
    alice = node("alice", "-n", "2000", "--bob", f"127.0.0.1:{cport}",
                 "--quantum", f"127.0.0.1:{qport}")
    out_a, out_b = finish(alice), finish(bob)
    assert "ABORT" not in out_a and "ABORT" not in out_b
    assert fingerprint(out_a) == fingerprint(out_b)


def test_alice_and_bob_run_from_their_own_modules():
    cport, qport = free_ports(2)
    bob = node("--classical-port", str(cport), "--quantum-port", str(qport), module="qkdsim.bob")
    time.sleep(0.3)
    alice = node("-n", "2000", "--bob", f"127.0.0.1:{cport}", "--quantum", f"127.0.0.1:{qport}",
                 module="qkdsim.alice")
    out_a, out_b = finish(alice), finish(bob)
    assert "Warning" not in out_a + out_b  # e.g. runpy's "found in sys.modules" double import
    assert fingerprint(out_a) == fingerprint(out_b)


def test_eve_process_is_detected():
    cport, qport, eport = free_ports(3)
    bob = node("bob", "--classical-port", str(cport), "--quantum-port", str(qport))
    eve = node("eve", "--listen-port", str(eport), "--forward", f"127.0.0.1:{qport}")
    time.sleep(0.3)
    alice = node("alice", "-n", "4000", "--bob", f"127.0.0.1:{cport}",
                 "--quantum", f"127.0.0.1:{eport}")
    out_a, out_b, out_e = finish(alice), finish(bob), finish(eve)
    assert "ABORT" in out_a and "ABORT" in out_b
    assert "intercepted 4000 pulses" in out_e
