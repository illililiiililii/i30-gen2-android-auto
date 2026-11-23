"""Services injected into the single-threaded projection core."""

from dataclasses import dataclass
from time import monotonic, sleep
from typing import Callable, Protocol


class MediaSink(Protocol):
    wants_projection: bool
    def channel(self, channel: int, kind: str, state: str) -> None: ...
    def packet(self, channel: int, kind: str, timestamp: int | None, data: bytes) -> None: ...


class DiagnosticSink:
    """Consume media synchronously, exposing size and channel status only."""

    wants_projection = False

    def __init__(self, log):
        self.log = log
        self.counts: dict[int, int] = {}

    def channel(self, channel, kind, state):
        if state == "closed":
            self.counts.pop(channel, None)
        self.log("channel", channel=channel, kind=kind, state=state)

    def packet(self, channel, kind, timestamp, data):
        count = self.counts[channel] = self.counts.get(channel, 0) + 1
        if count == 1 or count % 120 == 0:
            self.log("media", channel=channel, kind=kind, packets=count, bytes=len(data))


def quiet(*_, **__):
    pass


@dataclass(frozen=True)
class Platform:
    log: Callable = quiet
    clock: Callable[[], float] = monotonic
    pause: Callable[[float], None] = sleep
    allocate: Callable[..., bytearray] = bytearray
    stop_requested: Callable[[], bool] = lambda: False
