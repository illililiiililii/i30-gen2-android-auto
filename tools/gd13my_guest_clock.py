"""The optional, read-only UTC mailbox on the GD13MY emulator's DiskA."""

from datetime import datetime, timezone
import struct

UTC_PATH = '/Application/NAVI/i30-emu-utc.bin'
UTC_PLACEHOLDER = b'I30UTC00' + bytes(16)


def utc_mailbox():
    now = datetime.now(timezone.utc)
    return struct.pack('<8s8H', b'I30UTC01', now.year, now.month, (now.weekday() + 1) % 7, now.day,
                       now.hour, now.minute, now.second, now.microsecond // 1000)
