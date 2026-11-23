"""Inspect offline Android Auto frame bytes and run a socket-pair mock exchange."""

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import socket
import struct

FIRST = 1
LAST = 2
ENCRYPTED = 8
MAX_MESSAGE = 8 * 1024 * 1024
HEADER = struct.Struct(">BBH")


@dataclass(frozen=True)
class Frame:
    channel: int
    flags: int
    wire_payload_bytes: int
    announced_message_bytes: int | None
    message_id: int | None
    version_words_be: tuple[int, ...] | None


def read_exact(stream, count):
    result = bytearray()
    while len(result) < count:
        chunk = stream.read(count - len(result))
        if not chunk:
            raise ValueError("Truncated projection frame")
        result.extend(chunk)
    return bytes(result)


def read_frame(stream):
    first = stream.read(1)
    if not first:
        return None
    channel, flags, size = HEADER.unpack(first + read_exact(stream, HEADER.size - 1))
    if flags & 0xf0:
        raise ValueError(f"Flags outside the supported frame layout: {flags:#x}")
    fragment = flags & (FIRST | LAST)
    total = None
    if fragment == FIRST:
        total = struct.unpack(">I", read_exact(stream, 4))[0]
        if not 0 < total <= MAX_MESSAGE:
            raise ValueError("Announced message size outside analysis limit")
    payload = read_exact(stream, size)
    message_id = None
    version = None
    if not flags & ENCRYPTED and fragment == (FIRST | LAST):
        if len(payload) < 2:
            raise ValueError("Plain message has no message ID")
        message_id = struct.unpack_from(">H", payload)[0]
        if channel == 0 and message_id in (1, 2):
            word_count = 2 if message_id == 1 else 3
            if len(payload) != 2 + 2 * word_count:
                raise ValueError("Unexpected version message size")
            version = struct.unpack_from(f">{word_count}H", payload, 2)
    return Frame(channel, flags, size, total, message_id, version)


def mock_exchange():
    """Exercise known framing across a local stream. Both peers are synthetic."""
    request = bytes.fromhex("00 03 00 06 00 01 00 01 00 07")
    response = bytes.fromhex("00 03 00 08 00 02 00 01 00 07 00 00")
    head_unit, phone = socket.socketpair()
    with head_unit, phone, head_unit.makefile("rb") as incoming, phone.makefile("rb") as outgoing:
        head_unit.settimeout(2)
        phone.settimeout(2)
        head_unit.sendall(request[:3])
        head_unit.sendall(request[3:])
        received_request = read_frame(outgoing)
        if received_request is None or received_request.version_words_be != (1, 7):
            raise ValueError("Mock peer received the wrong request")
        phone.sendall(response)
        received_response = read_frame(incoming)
        if received_response is None or received_response.version_words_be != (1, 7, 0):
            raise ValueError("Mock receiver got the wrong response")
    return {"source": "synthetic local peers", "request": asdict(received_request),
            "response": asdict(received_response)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--mock", action="store_true")
    source.add_argument("--frames", type=Path,
                        help="File of consecutive frame bytes in one direction (no PCAP headers)")
    args = parser.parse_args()
    if args.mock:
        print(json.dumps(mock_exchange(), indent=2))
        return
    with args.frames.open("rb") as stream:
        for frame in iter(lambda: read_frame(stream), None):
            print(json.dumps(asdict(frame)))


if __name__ == "__main__":
    main()
