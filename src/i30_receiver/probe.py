"""A short live probe: selected USB port, AOA, bulk link, and plain version."""

from .protocol import version_request, version_response
from .transport import Timeout
from .wire import ENCRYPTED, FrameReader, ProtocolError, Reassembler, encode


def probe(transport, platform, seconds=5.0):
    device = transport.detect()
    if device is None:
        raise Timeout("No USB device on the specified port")
    platform.log("device_detected", port=device.port, vid=f"{device.vendor:04x}", pid=f"{device.product:04x}")
    link = transport.connect(device)
    platform.log("accessory_open", port=device.port)
    try:
        for frame in encode(version_request()):
            link.write(frame, 1000)
        reader = FrameReader(platform.allocate)
        assembler = Reassembler(platform.allocate)
        deadline = platform.clock() + seconds
        while platform.clock() < deadline and not platform.stop_requested():
            try:
                data = link.read(150)
            except Timeout:
                continue
            for frame in reader.feed(data):
                if frame.flags & ENCRYPTED:
                    raise ProtocolError("Protected frame arrived during plain version probe")
                message = assembler.push(frame, frame.payload)
                if message is not None:
                    return version_response(message)
        raise Timeout("No Android Auto version response")
    finally:
        link.close()
