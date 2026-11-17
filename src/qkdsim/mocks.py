"""In-memory channel and the generic authenticated channel."""

from __future__ import annotations

from collections import deque

from qkdsim.interfaces import Channel, ChannelError, Session


class _Pipe:
    def __init__(self) -> None:
        self.queues: tuple[deque[bytes], deque[bytes]] = (deque(), deque())
        self.closed = False


class InMemoryChannel:
    def __init__(self, pipe: _Pipe, side: int) -> None:
        self._pipe = pipe
        self._inbox = pipe.queues[side]
        self._outbox = pipe.queues[1 - side]

    def send(self, data: bytes) -> None:
        if self._pipe.closed:
            raise ChannelError("channel is closed")
        self._outbox.append(bytes(data))

    def recv(self) -> bytes:
        if self._pipe.closed:
            raise ChannelError("channel is closed")
        if not self._inbox:
            raise ChannelError("nothing to receive")
        return self._inbox.popleft()

    def close(self) -> None:
        self._pipe.closed = True


def channel_pair() -> tuple[InMemoryChannel, InMemoryChannel]:
    pipe = _Pipe()
    return InMemoryChannel(pipe, 0), InMemoryChannel(pipe, 1)


class AuthenticatedChannel:
    def __init__(self, raw: Channel, session: Session) -> None:
        self._raw = raw
        self._session = session

    def send(self, data: bytes) -> None:
        self._raw.send(self._session.protect(data))

    def recv(self) -> bytes:
        return self._session.unprotect(self._raw.recv())

    def close(self) -> None:
        self._session.close()
        self._raw.close()
