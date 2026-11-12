"""Kerberos (GSSAPI) authentication of the classical channel.

Before BB84 starts, Alice and Bob run the Kerberos AP exchange on the classical TCP connection:
Alice presents the service ticket for Bob she got from the KDC, and Bob proves he holds the key in
his keytab (mutual authentication). Both sides then share a Kerberos session key.

After that, every classical message is followed by a MIC: a tag over the message computed with the
session key, with a sequence number so replayed or reordered messages are rejected. Messages stay
in the clear on purpose: BB84 needs an authenticated channel, not a secret one, and the transcript
is exactly what Eve is allowed to read.

Needs python-gssapi and the Kerberos setup in krb5/: Alice needs a ticket (kinit), Bob a keytab.
The quantum channel is not authenticated.
"""

import socket

import gssapi

from qkdsim import net
from qkdsim.transport import TransportError

_FLAGS = [
    gssapi.RequirementFlag.mutual_authentication,
    gssapi.RequirementFlag.integrity,
    gssapi.RequirementFlag.replay_detection,
    gssapi.RequirementFlag.out_of_sequence_detection,
]


class AuthError(TransportError):
    """A message or the peer failed authentication; the caller must abort."""


def _principal(name: str) -> gssapi.Name:
    return gssapi.Name(name, name_type=gssapi.NameType.kerberos_principal)


def initiate(sock: socket.socket, service: str) -> gssapi.SecurityContext:
    """Alice's side: authenticate to `service` (Bob's principal) using her ticket cache."""
    context = gssapi.SecurityContext(name=_principal(service), usage="initiate", flags=_FLAGS)
    token = context.step()
    while True:
        if token:
            net.send_frame(sock, token)
        if context.complete:
            return context
        token = context.step(net.recv_frame(sock))


def accept(sock: socket.socket, service: str, peer: str) -> gssapi.SecurityContext:
    """Bob's side: authenticate as `service` from his keytab and require the client to be `peer`."""
    creds = gssapi.Credentials(name=_principal(service), usage="accept")
    context = gssapi.SecurityContext(creds=creds, usage="accept")
    while not context.complete:
        token = context.step(net.recv_frame(sock))
        if token:
            net.send_frame(sock, token)
    if str(context.initiator_name) != peer:
        raise AuthError(f"expected client {peer!r}, got {context.initiator_name}")
    return context


class KerberosEndpoint(net.TcpEndpoint):
    """TcpEndpoint whose messages each carry a MIC under the Kerberos session key."""

    def __init__(self, name: str, sock: socket.socket, context: gssapi.SecurityContext) -> None:
        super().__init__(name, sock)
        self.context = context

    def _write(self, raw: bytes) -> None:
        net.send_frame(self.sock, raw)
        net.send_frame(self.sock, self.context.get_signature(raw))

    def _read(self) -> bytes:
        raw = net.recv_frame(self.sock)
        tag = net.recv_frame(self.sock)
        try:
            self.context.verify_signature(raw, tag)
        except gssapi.exceptions.GSSError as e:
            raise AuthError(f"{self.name}: message failed authentication: {e}") from e
        return raw
