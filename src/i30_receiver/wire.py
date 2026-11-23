"""Android Auto transport framing, based on aasdk FrameHeader and FrameSize."""

import struct
from dataclasses import dataclass
from typing import Callable

FIRST, LAST, CONTROL, ENCRYPTED = 1, 2, 4, 8
BULK = FIRST | LAST
HEADER = struct.Struct(">BBH")
MESSAGE_ID = struct.Struct(">H")
MAX_FRAME = 0x4200  # aasdk's 0x4000 plaintext plus bounded TLS overhead
MAX_MESSAGE = 2 * 1024 * 1024
MAX_PENDING = 4 * 1024 * 1024


class ProtocolError(Exception):
    """Invalid, unexpected or unsupported protocol input."""


@dataclass(frozen=True)
class Frame:
    channel: int
    flags: int
    payload: bytes
    total: int | None = None


@dataclass(frozen=True)
class Message:
    channel: int
    flags: int
    code: int
    payload: bytes = b""


class FrameReader:
    def __init__(self, allocate: Callable[..., bytearray] = bytearray):
        self.buffer = allocate()

    def feed(self, data: bytes):
        if len(data) > 0x8000 or len(self.buffer) + len(data) > 0x8000 + MAX_FRAME + 8:
            raise ProtocolError("Transport chunk exceeds frame-buffer budget")
        self.buffer.extend(data)
        offset = 0
        try:
            while len(self.buffer) - offset >= HEADER.size:
                channel, flags, size = HEADER.unpack_from(self.buffer, offset)
                if flags & 0xf0 or not 0 < size <= MAX_FRAME:
                    raise ProtocolError("Invalid frame flags or length")
                header_size = 8 if (flags & BULK) == FIRST else 4
                if len(self.buffer) - offset < header_size + size:
                    break
                total = struct.unpack_from(">I", self.buffer, offset + 4)[0] if header_size == 8 else None
                if total is not None and not 2 <= total <= MAX_MESSAGE:
                    raise ProtocolError("Invalid advertised message size")
                start = offset + header_size
                offset = start + size
                yield Frame(channel, flags, bytes(self.buffer[start:offset]), total)
        finally:
            del self.buffer[:offset]


@dataclass
class Pending:
    flags: int
    total: int
    data: bytearray


class Reassembler:
    def __init__(self, allocate: Callable[..., bytearray] = bytearray):
        self.allocate = allocate
        self.pending: dict[int, Pending] = {}
        self.reserved = 0

    def push(self, frame: Frame, plain: bytes) -> Message | None:
        fragment = frame.flags & BULK
        flags = frame.flags & ~BULK
        active = self.pending.get(frame.channel)
        if not plain:
            raise ProtocolError("Empty message fragment")
        if fragment == BULK:
            if active:
                raise ProtocolError("Complete message interrupted a partial message")
            return make_message(frame.channel, flags, plain)
        if fragment == FIRST:
            if active or frame.total is None or frame.total <= len(plain):
                raise ProtocolError("Invalid first fragment")
            if len(self.pending) >= 8 or self.reserved + frame.total > MAX_PENDING:
                raise ProtocolError("Reassembly budget exhausted")
            self.pending[frame.channel] = Pending(flags, frame.total, self.allocate(plain))
            self.reserved += frame.total
            return None
        if active is None or active.flags != flags:
            raise ProtocolError("Orphan fragment or inconsistent flags")
        length = len(active.data) + len(plain)
        if length > active.total or (fragment == LAST) != (length == active.total):
            raise ProtocolError("Fragment boundary differs from advertised size")
        active.data.extend(plain)
        if fragment == LAST:
            self.reserved -= active.total
            del self.pending[frame.channel]
            return make_message(frame.channel, flags, active.data)
        return None


def make_message(channel, flags, data):
    if len(data) < 2:
        raise ProtocolError("Missing message ID")
    return Message(channel, flags, MESSAGE_ID.unpack_from(data)[0], bytes(data[2:]))


def encode(message: Message, encrypt=None, fragment_size=0x4000):
    if message.flags & ~(CONTROL | ENCRYPTED) or bool(message.flags & ENCRYPTED) != bool(encrypt):
        raise ProtocolError("Invalid transmit protection flags")
    if not 1 <= fragment_size <= 0x4000:
        raise ValueError("Invalid outgoing fragment size")
    raw = MESSAGE_ID.pack(message.code) + message.payload
    if len(raw) > MAX_MESSAGE:
        raise ProtocolError("Outgoing message exceeds size limit")
    for start in range(0, len(raw), fragment_size):
        chunk = raw[start:start + fragment_size]
        first, last = start == 0, start + len(chunk) == len(raw)
        flags = message.flags | (FIRST if first else 0) | (LAST if last else 0)
        wire = encrypt(chunk) if encrypt else chunk
        if not 0 < len(wire) <= MAX_FRAME:
            raise ProtocolError("Invalid outgoing frame length")
        extension = struct.pack(">I", len(raw)) if first and not last else b""
        yield HEADER.pack(message.channel, flags, len(wire)) + extension + wire
