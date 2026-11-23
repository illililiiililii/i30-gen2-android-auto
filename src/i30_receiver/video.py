"""Bounded Annex B H.264 decoder and optional one-frame PC preview."""

from fractions import Fraction

from .platform import DiagnosticSink
from .wire import ProtocolError


MAX_PIXELS = 1920 * 1088  # Allow coded padding for a 1080p H.264 frame.
MAX_PENDING = 2 * 1024 * 1024


class H264Decoder:
    def __init__(self, av):
        self.codec = av.CodecContext.create("h264", "r")
        self.codec.thread_count = 1
        self.codec.options = {"max_pixels": str(MAX_PIXELS), "err_detect": "explode"}
        self.codec.open()
        if self.codec.options:
            raise ValueError("The H.264 decoder did not accept its limits")
        self.pending = 0

    def push(self, data):
        if len(data) > MAX_PENDING:
            raise ValueError("H.264 input chunk exceeds 2 MiB")
        packets = self.codec.parse(data)
        self.pending = max(0, self.pending + len(data) - sum(packet.size for packet in packets))
        if self.pending > MAX_PENDING:
            raise ValueError("H.264 parser buffered more than 2 MiB")
        for packet in packets:
            yield from self.check_frames(self.codec.decode(packet))

    def finish(self):
        for packet in self.codec.parse():
            yield from self.check_frames(self.codec.decode(packet))
        yield from self.check_frames(self.codec.decode())

    @staticmethod
    def check_frames(frames):
        for frame in frames:
            if frame.is_corrupt:
                raise ValueError("H.264 decoder reported a corrupt frame")
            yield frame


def write_preview(av, frame, path):
    encoder = av.CodecContext.create("png", "w")
    encoder.width, encoder.height = frame.width, frame.height
    encoder.pix_fmt = "rgb24"
    encoder.time_base = Fraction(1, 30)
    rgb = frame.reformat(format="rgb24")
    rgb.pts = 0
    encoded = encoder.encode(rgb) + encoder.encode()
    if not encoded:
        raise ValueError("PNG encoder produced no preview")
    with path.open("xb") as preview:
        for packet in encoded:
            preview.write(bytes(packet))


def frame_ppm(frame, width, height):
    plane = frame.reformat(width=width, height=height, format='rgb24').planes[0]
    stride = plane.line_size
    data = bytes(plane)
    pixels = b''.join(data[row * stride:row * stride + width * 3] for row in range(height))
    return f'P6\n{width} {height}\n255\n'.encode('ascii') + pixels


class VideoPreviewSink(DiagnosticSink):
    wants_projection = True

    def __init__(self, log, av, output):
        super().__init__(log)
        self.av, self.output = av, output
        self.decoder = None
        self.total_frames = 0
        self.preview_written = False

    def channel(self, channel, kind, state):
        super().channel(channel, kind, state)
        if kind != "video":
            return
        if state == "receiving":
            try:
                self.decoder = H264Decoder(self.av)
            except (ValueError, self.av.FFmpegError) as exc:
                raise ProtocolError(f"Could not initialize H.264 decoder: {exc}") from exc
        elif state == "open" and self.decoder is not None:  # A media STOP drains the decoder.
            try:
                self.consume(self.decoder.finish())
            finally:
                self.decoder = None
        elif state == "closed":
            self.decoder = None  # An incomplete stream may remain after USB disconnect.

    def packet(self, channel, kind, timestamp, data):
        super().packet(channel, kind, timestamp, data)
        if kind == "video" and self.decoder is not None:
            self.consume(self.decoder.push(data))

    def consume(self, frames):
        try:
            for frame in frames:
                self.total_frames += 1
                if not self.preview_written:
                    write_preview(self.av, frame, self.output)
                    self.preview_written = True
                    self.log("video_preview", width=frame.width, height=frame.height)
        except (OSError, ValueError, self.av.FFmpegError) as exc:
            raise ProtocolError(f"Video preview failed: {exc}") from exc
