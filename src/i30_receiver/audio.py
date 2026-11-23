"""Bounded PCM conversion, playback mixing and microphone packetization."""

from array import array
from dataclasses import dataclass
from sys import byteorder
from typing import Protocol

from .wire import ProtocolError


@dataclass(frozen=True)
class Pcm:
    rate: int
    channels: int

    @property
    def frame_bytes(self):
        return 2 * self.channels  # Signed 16-bit little-endian PCM

    def block_bytes(self, milliseconds=20):
        return self.rate * milliseconds // 1000 * self.frame_bytes


MUSIC = Pcm(48000, 2)
GUIDANCE = MIC = Pcm(16000, 1)


class Playback(Protocol):
    format: Pcm

    def start(self) -> None: ...
    def ready(self) -> bool: ...
    def write(self, data: bytes) -> None: ...
    def close(self) -> None: ...


class Capture(Protocol):
    format: Pcm

    def start(self) -> None: ...
    def read(self) -> bytes: ...
    def close(self) -> None: ...


def samples(data):
    result = array('h')
    result.frombytes(data)
    if byteorder != 'little':
        result.byteswap()
    return result


def pcm_bytes(values):
    output = array('h', values)
    if byteorder != 'little':
        output.byteswap()
    return output.tobytes()


class PcmConverter:
    """Integrate source frames over the output interval and keep phase across packets."""

    def __init__(self, source, target):
        if any(not 8000 <= fmt.rate <= 96000 or fmt.channels not in (1, 2) for fmt in (source, target)):
            raise ValueError("Unsupported PCM format")
        self.source, self.target = source, target
        self.phase = self.left = self.right = 0

    def convert(self, data):
        if len(data) % self.source.frame_bytes:
            raise ProtocolError("Incomplete PCM sample frame")
        if self.source == self.target:
            return data
        source, target = self.source, self.target
        values = samples(data)
        result = array('h')
        phase, left, right = self.phase, self.left, self.right
        for index in range(0, len(values), source.channels):
            lvalue = values[index]
            rvalue = values[index + source.channels - 1]
            if target.channels == 1:
                lvalue = (lvalue + rvalue) // 2
            remaining = target.rate
            while remaining:
                width = min(remaining, source.rate - phase)
                left += lvalue * width
                right += rvalue * width
                phase += width
                remaining -= width
                if phase == source.rate:
                    result.append(left // source.rate)
                    if target.channels == 2:
                        result.append(right // source.rate)
                    phase = left = right = 0
        self.phase, self.left, self.right = phase, left, right
        return pcm_bytes(result)


class AudioMixer:
    """Keep at most 120 ms per stream and let guidance duck projected music only."""

    def __init__(self, output: Playback, volume=1.0):
        if not 0 <= volume <= 1:
            raise ValueError("Volume must be between 0 and 1")
        self.output = output
        self.volume = volume
        self.streams = {'audio': MUSIC, 'guidance': GUIDANCE}
        self.queues = {name: bytearray() for name in self.streams}
        self.converters = {}
        self.open = False
        self.dropped = 0
        self.blocks_written = 0
        self.duck_blocks = 0
        self.next_block = None

    def clear(self, kind):
        self.queues[kind].clear()
        self.converters.pop(kind, None)
        if kind == 'guidance':
            self.duck_blocks = 0

    def push(self, kind, data):
        fmt = self.streams[kind]
        if len(data) > fmt.block_bytes(120):
            self.dropped += (len(data) - fmt.block_bytes(120)) // fmt.frame_bytes
            self.converters.pop(kind, None)
            if len(data) % fmt.frame_bytes:
                raise ProtocolError("Incomplete PCM sample frame")
            data = data[-fmt.block_bytes(120):]
        if kind not in self.converters:
            self.converters[kind] = PcmConverter(fmt, self.output.format)
        queue = self.queues[kind]
        queue.extend(self.converters[kind].convert(data))
        excess = len(queue) - self.output.format.block_bytes(120)
        if excess > 0:
            del queue[:excess]
            self.dropped += excess // self.output.format.frame_bytes

    def tick(self, now):
        if not any(self.queues.values()):
            self.next_block = None
            return
        if self.next_block is None:
            self.next_block = now + 0.02
        if now < self.next_block:
            return
        if not self.open:
            self.output.start()
            self.open = True
        if not self.output.ready():
            return
        size = self.output.format.block_bytes()
        music, guidance = (samples(queue[:size]) for queue in self.queues.values())
        if any(guidance):
            self.duck_blocks = 4
        gain = 0.25 if self.duck_blocks else 1.0
        self.duck_blocks = max(0, self.duck_blocks - 1)
        count = size // 2
        music.extend([0] * (count - len(music)))
        guidance.extend([0] * (count - len(guidance)))
        self.output.write(pcm_bytes(max(-32768, min(32767, int((m * gain + g) * self.volume)))
                                    for m, g in zip(music, guidance)))
        self.blocks_written += 1
        self.next_block = max(self.next_block + 0.02, now - 0.01)
        for queue in self.queues.values():
            del queue[:size]

    def close(self):
        self.next_block = None
        for kind in self.queues:
            self.clear(kind)
        self.output.close()
        self.open = False


class Microphone:
    def __init__(self, capture: Capture):
        self.capture = capture
        self.pending = bytearray()
        self.converter = None

    def start(self):
        converter = PcmConverter(self.capture.format, MIC)
        self.capture.start()
        self.converter = converter

    def block(self, *, send):
        if self.converter is None:
            return b''
        data = self.capture.read()
        limit = self.capture.format.block_bytes(60)
        if len(data) > limit:
            raise ProtocolError("Microphone backend exceeded its capture bound")
        self.pending.extend(self.converter.convert(data))
        size = MIC.block_bytes()
        if len(self.pending) > size * 2:
            del self.pending[:((len(self.pending) - size * 2 + size - 1) // size) * size]
        if send and len(self.pending) >= size:
            block = bytes(self.pending[:size])
            del self.pending[:size]
            return block
        return b''

    def close(self):
        self.pending.clear()
        self.converter = None
        self.capture.close()
