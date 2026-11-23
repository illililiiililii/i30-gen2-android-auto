"""Local synthetic phone and AOA backend. Uses real TLS with a test identity."""

from collections import deque
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
import ssl
import struct
import subprocess
from tempfile import TemporaryDirectory

from . import schema
from .audio import GUIDANCE, MIC, MUSIC, pcm_bytes
from .protocol import (CTL, GUIDANCE_CHANNEL, INPUT, INPUT_CHANNEL, MEDIA, MIC_CHANNEL, SHARED,
                       SINK, SOURCE, TOUCH_SIZE, VIDEO, codec, ctrl, input_code, keycode, media)
from .tls import TlsRecords, client_context
from .transport import Device, Disconnected, Timeout, TransportError
from .wire import CONTROL, ENCRYPTED, FrameReader, Message, ProtocolError, Reassembler, encode

PORT = "1-2.3"
PHONE = Device(PORT, 0x18d1, 0x4ee1, 9)
ACCESSORY = Device(PORT, 0x18d1, 0x2d00, 10)


class MockPlayback:
    format = MUSIC

    def __init__(self):
        self.active = False
        self.last = b''
        self.closed = 0

    def start(self):
        self.active = True

    def ready(self):
        return self.active

    def write(self, data):
        self.last = data

    def close(self):
        if self.active:
            self.active = False
            self.closed += 1


class MockCapture:
    format = MUSIC

    def __init__(self, clock):
        self.clock = clock
        self.deadline = None
        self.closed = 0
        self.speech = pcm_bytes([1000, 3000]) * (MUSIC.rate // 50)

    def start(self):
        self.deadline = self.clock() + 0.02

    def read(self):
        if self.deadline is None or self.clock() < self.deadline:
            return b''
        self.deadline = self.clock() + 0.02
        return self.speech

    def close(self):
        if self.deadline is not None:
            self.deadline = None
            self.closed += 1


class MockStockUi:
    def __init__(self):
        self.projected = False
        self.restored = 0
        self.buttons = []

    def show_projection(self):
        self.projected = True
        return True

    def restore_stock(self):
        self.projected = False
        self.restored += 1

    def stock_button(self, button, down, longpress):
        self.buttons.append((button, down, longpress))


class VirtualClock:
    def __init__(self):
        self.time = 1.0

    def now(self):
        return self.time

    def pause(self, seconds):
        self.time += seconds


@contextmanager
def test_identity(openssl: Path):
    with TemporaryDirectory(prefix="i30-mock-") as directory:
        cert, key = Path(directory) / "test.pem", Path(directory) / "test-key.pem"
        subprocess.run([str(openssl), "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                        "-subj", "/CN=i30-mock.local", "-addext", "subjectAltName=DNS:i30-mock.local",
                        "-out", str(cert), "-keyout", str(key)],
                       capture_output=True, timeout=20, check=True)
        server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server.minimum_version = server.maximum_version = ssl.TLSVersion.TLSv1_2
        server.load_cert_chain(cert, key)
        server.load_verify_locations(cafile=str(cert))
        server.verify_mode = ssl.CERT_REQUIRED
        yield cert, key, server


def mock_client(cert, key):
    return client_context(cert, "i30-mock.local", None, cert, key)


def synthetic_h264(av):
    width, height = TOUCH_SIZE
    encoder = av.CodecContext.create("libx264", "w")
    encoder.width, encoder.height = width, height
    encoder.pix_fmt = "yuv420p"
    encoder.time_base = Fraction(1, 30)
    encoder.options = {"preset": "ultrafast", "tune": "zerolatency", "profile": "baseline"}
    packets = []
    for index, luma in enumerate((48, 112, 176)):
        frame = av.VideoFrame(width, height, "yuv420p")
        frame.pts = index
        for plane, color in zip(frame.planes, (luma, 105, 160)):
            plane.update(bytes([color]) * plane.buffer_size)
        packets.extend(bytes(packet) for packet in encoder.encode(frame))
    packets.extend(bytes(packet) for packet in encoder.encode())
    return packets


class MockUsb:
    def __init__(self, server_context, platform, scenarios=("ok",), *, never_reenumerate=False,
                 tap=None, video_packets=(), phase3=False, interactive=False):
        self.context = server_context
        self.platform = platform
        self.scenarios = deque(scenarios)
        self.never_reenumerate = never_reenumerate
        self.switched_at = None
        self.requests = []
        self.claimed = 0
        self.closed = 0
        self.peer_pongs = 0
        self.media_acks = 0
        self.released = 0
        self.tap = tap
        self.touch_reports = []
        self.video_packets = video_packets
        self.phase3 = phase3
        self.interactive = interactive
        self.key_reports = []
        self.mic_blocks = 0
        self.mic_closed = 0

    def devices(self):
        if self.switched_at is None:
            return [PHONE]
        if not self.never_reenumerate and self.platform.clock() >= self.switched_at:
            return [ACCESSORY]
        return []

    def control_in(self, device, request, length, timeout_ms):
        if device != PHONE or (request, length) != (51, 2):
            raise TransportError("Invalid mock control request")
        self.requests.append((request, 0, b""))
        return b"\x02\x00"

    def control_out(self, device, request, index, payload, timeout_ms):
        if device != PHONE or request not in (52, 53):
            raise TransportError("Invalid mock control request")
        self.requests.append((request, index, payload))
        if request == 53:
            self.switched_at = self.platform.clock() + 0.2
            raise Disconnected("Mock AOA reenumeration")

    def release_control(self, device):
        self.released += 1

    def open_accessory(self, device):
        if device != ACCESSORY or not self.scenarios:
            raise TransportError("Mock accessory unavailable")
        self.claimed += 1
        return MockLink(self, self.scenarios.popleft())


class MockLink:
    def __init__(self, backend, scenario):
        self.backend = backend
        self.scenario = scenario
        self.reader = FrameReader()
        self.reassembler = Reassembler()
        self.responses = deque()
        self.tls = TlsRecords(backend.context, server=True)
        self.closed = False
        self.started_channels = 0
        self.media_channels = 3 if backend.phase3 else 2
        self.mic_id = None
        self.mic_stamp = 0
        self.mic_blocks = 0
        self.projecting = False
        self.ping = None
        self.touch_bound = False

    def read(self, timeout_ms):
        if self.responses:
            return self.responses.popleft()
        if self.scenario == "unplug" and self.started_channels == self.media_channels:
            raise Disconnected("Mock phone cable unplugged")
        self.backend.platform.pause(timeout_ms / 1000)
        raise Timeout("Mock read poll")

    def close(self):
        if not self.closed:
            self.closed = True
            self.backend.closed += 1
            self.responses.clear()

    def send(self, code, payload=b"", channel=0, *, secure=True, control=False, fragment_size=0x4000):
        data = payload if isinstance(payload, bytes) else payload.SerializeToString()
        flags = (ENCRYPTED if secure else 0) | (CONTROL if control else 0)
        for wire in encode(Message(channel, flags, code, data),
                           self.tls.encrypt if secure else None, fragment_size):
            self.responses.extend((wire[:1], wire[1:4], wire[4:]))

    def write(self, data, timeout_ms):
        if self.closed:
            raise Disconnected("Mock link closed")
        if self.scenario == "silent":
            return
        for frame in self.reader.feed(data):
            plain = self.tls.decrypt(frame.payload) if frame.flags & ENCRYPTED else frame.payload
            message = self.reassembler.push(frame, plain)
            if message is not None:
                self.handle(message)

    def handle(self, msg):
        number, code, payload = msg.channel, msg.code, msg.payload
        if number:
            if number == INPUT_CHANNEL:
                self.handle_touch(msg)
            elif number == MIC_CHANNEL:
                self.handle_capture(msg)
            else:
                self.handle_media(msg)
            return
        if code == ctrl("VERSION_REQUEST"):
            if payload != struct.pack(">HH", 1, 6):
                raise ProtocolError("Mock received an unexpected protocol version")
            self.send(ctrl("VERSION_RESPONSE"), struct.pack(">HHh", 1, 7, 0), secure=False)
        elif code == ctrl("ENCAPSULATED_SSL"):
            data = self.tls.handshake(payload)
            if data:
                self.send(ctrl("ENCAPSULATED_SSL"), data, secure=False)
        elif code == ctrl("AUTH_COMPLETE"):
            if not self.tls.ready or schema.parse(CTL + "AuthResponse", payload).status != 0:
                raise ProtocolError("Mock did not authenticate")
            self.send(ctrl("SERVICE_DISCOVERY_REQUEST"),
                      schema.message(CTL + "ServiceDiscoveryRequest")(device_name="Synthetic peer"),
                      fragment_size=7)
        elif code == ctrl("SERVICE_DISCOVERY_RESPONSE"):
            response = schema.parse(CTL + "ServiceDiscoveryResponse", payload)
            expected = {1, 3, 4} if self.backend.tap is not None and not self.backend.touch_reports else {3, 4}
            if self.backend.phase3:
                expected.update((INPUT_CHANNEL, GUIDANCE_CHANNEL, MIC_CHANNEL))
            if self.backend.interactive:
                expected.add(INPUT_CHANNEL)
            if {channel.id for channel in response.channels} != expected:
                raise ProtocolError("Mock received unexpected diagnostic services")
            for service in response.channels:
                if service.id == INPUT_CHANNEL:
                    screens = service.input_source_service.touchscreen
                    tap_expected = self.backend.interactive or (
                        self.backend.tap is not None and not self.backend.touch_reports)
                    if len(screens) != int(tap_expected) or (screens and (screens[0].width, screens[0].height) != TOUCH_SIZE):
                        raise ProtocolError("Mock received unexpected touch geometry")
                    if self.backend.phase3 and keycode('SEARCH') not in service.input_source_service.keycodes_supported:
                        raise ProtocolError("Mock did not receive a voice button")
                if service.id == MIC_CHANNEL:
                    config = service.media_source_service.audio_config
                    if (config.sampling_rate, config.number_of_bits, config.number_of_channels) != (16000, 16, 1):
                        raise ProtocolError("Mock microphone format was not 16 kHz mono PCM")
                request = schema.message(CTL + "ChannelOpenRequest")(priority=0, service_id=service.id)
                self.send(ctrl("CHANNEL_OPEN_REQUEST"), request, service.id, control=True)
            if self.scenario == "bad-frame":
                self.responses.append(bytes.fromhex("00 ff 00 01 00"))
            self.ping = 123456
            self.send(ctrl("PING_REQUEST"), schema.message(CTL + "PingRequest")(timestamp=self.ping, data=b"test"))
            if self.backend.phase3:
                self.send(ctrl("AUDIO_FOCUS_REQUEST"), schema.message(CTL + "AudioFocusRequest")(audio_focus_type=1))
        elif code == ctrl("PING_RESPONSE"):
            reply = schema.parse(CTL + "PingResponse", payload)
            if (reply.timestamp, reply.data) != (self.ping, b"test"):
                raise ProtocolError("Mock ping response did not echo the request")
            self.backend.peer_pongs += 1
        elif code == ctrl("PING_REQUEST"):
            request = schema.parse(CTL + "PingRequest", payload)
            if self.scenario != "no-pong":
                response = schema.message(CTL + "PingResponse")(timestamp=request.timestamp)
                self.send(ctrl("PING_RESPONSE"), response)
        elif code == ctrl("BYEBYE_REQUEST"):
            schema.parse(CTL + "ByeByeRequest", payload)
            self.send(ctrl("BYEBYE_RESPONSE"), schema.message(CTL + "ByeByeResponse")())

    def handle_touch(self, msg):
        if msg.code == ctrl("CHANNEL_OPEN_RESPONSE"):
            if not msg.flags & CONTROL or schema.parse(CTL + "ChannelOpenResponse", msg.payload).status != 0:
                raise ProtocolError("Mock touch channel was refused")
            binding = schema.message(MEDIA + "sink.message.KeyBindingRequest")()
            if self.backend.phase3:
                binding.keycodes.extend((keycode('SEARCH'), keycode('MEDIA_NEXT')))
            self.send(input_code("KEY_BINDING_REQUEST"), binding, INPUT_CHANNEL)
        elif msg.code == input_code("KEY_BINDING_RESPONSE"):
            if schema.parse(MEDIA + "sink.message.KeyBindingResponse", msg.payload).status != 0:
                raise ProtocolError("Mock touch binding was refused")
            self.touch_bound = True
        elif msg.code == input_code("INPUT_REPORT"):
            report = schema.parse(INPUT + "message.InputReport", msg.payload)
            if self.backend.phase3 and report.HasField('key_event'):
                if not self.touch_bound or msg.flags != ENCRYPTED:
                    raise ProtocolError("Unexpected mock key report")
                for key in report.key_event.keys:
                    self.backend.key_reports.append((key.keycode, key.down))
                    if key.keycode == keycode('SEARCH') and not key.down:
                        self.send(ctrl('VOICE_SESSION_NOTIFICATION'),
                                  schema.message(CTL + 'VoiceSessionNotification')(status=1))
                        self.capture_request(True)
                return
            reports = self.backend.touch_reports
            if self.backend.interactive and self.touch_bound and msg.flags == ENCRYPTED:
                if not report.HasField('touch_event'):
                    raise ProtocolError("Mock interactive input must contain a touch event")
                reports.append((report.touch_event.action, report.timestamp))
                return
            if self.backend.tap is None or not self.touch_bound or msg.flags != ENCRYPTED or len(reports) >= 2:
                raise ProtocolError("Mock received an unexpected touch report")
            touch = report.touch_event
            pointers = [(p.x, p.y, p.pointer_id) for p in touch.pointer_data]
            expected = "ACTION_DOWN" if not reports else "ACTION_UP"
            action = schema.value(INPUT + "message.PointerAction", expected)
            if (not touch.HasField("action") or touch.action != action or touch.action_index != 0
                    or pointers != [(*self.backend.tap, 0)] or report.timestamp <= 0
                    or (reports and report.timestamp <= reports[-1][1])):
                raise ProtocolError("Mock touch report did not match the requested tap")
            reports.append((expected, report.timestamp))

    def handle_media(self, msg):
        number, code, payload = msg.channel, msg.code, msg.payload
        if code == ctrl("CHANNEL_OPEN_RESPONSE"):
            if not msg.flags & CONTROL or schema.parse(CTL + "ChannelOpenResponse", payload).status != 0:
                raise ProtocolError("Mock channel refused")
            name = "VIDEO_H264_BP" if number == 3 else "AUDIO_PCM"
            self.send(media("SETUP"), schema.message(SHARED + "Setup")(type=codec(name)), number)
        elif code == media("CONFIG"):
            config = schema.parse(SHARED + "Config", payload)
            if config.status != 2 or list(config.configuration_indices) != [0]:
                raise ProtocolError("Mock media configuration refused")
            self.started_channels += 1
            self.send(media("START"), schema.message(SHARED + "Start")(
                session_id=100 + number, configuration_index=0), number)
            if number == 3 and (self.backend.video_packets or self.backend.phase3):
                projected = schema.value(VIDEO + "VideoFocusMode", "VIDEO_FOCUS_PROJECTED")
                request = schema.message(VIDEO + "VideoFocusRequestNotification")(mode=projected)
                self.send(media("VIDEO_FOCUS_REQUEST"), request, number)
            elif self.backend.phase3:
                fmt = GUIDANCE if number == GUIDANCE_CHANNEL else MUSIC
                value = 2000 if number == GUIDANCE_CHANNEL else 8000
                pcm = pcm_bytes([value]) * (fmt.block_bytes(60) // 2)
                self.send(media("DATA"), struct.pack(">Q", 42) + pcm, number)
            else:
                self.send(media("DATA"), struct.pack(">Q", 42) + b"synthetic test payload", number, fragment_size=7)
        elif code == media("VIDEO_FOCUS_NOTIFICATION") and number == 3 and (self.backend.video_packets or self.backend.phase3):
            reply = schema.parse(VIDEO + "VideoFocusNotification", payload)
            projected = reply.focus == schema.value(VIDEO + "VideoFocusMode", "VIDEO_FOCUS_PROJECTED")
            if not projected and not self.backend.phase3:
                raise ProtocolError("Mock video projection focus refused")
            if self.projecting == projected:
                return
            self.projecting = projected
            if not projected:
                return
            for index, packet in enumerate(self.backend.video_packets or (b'mock video',)):
                stamp = 42 + index * 33_333
                self.send(media("DATA"), struct.pack(">Q", stamp) + packet, number, fragment_size=1024)
            if not self.backend.phase3:
                self.send(media("STOP"), schema.message(SHARED + "Stop")(), number)
        elif code == media("ACK"):
            ack = schema.parse(MEDIA + "source.message.Ack", payload)
            if (ack.session_id, ack.ack) != (100 + number, 1):
                raise ProtocolError("Mock media ACK did not match the session")
            self.backend.media_acks += 1

    def capture_request(self, opening):
        request = schema.message(SOURCE + 'MicrophoneRequest')(open=opening, max_unacked=2)
        self.send(media('MICROPHONE_REQUEST'), request, MIC_CHANNEL)

    def handle_capture(self, msg):
        if msg.code == ctrl('CHANNEL_OPEN_RESPONSE'):
            self.send(media('SETUP'), schema.message(SHARED + 'Setup')(type=codec('AUDIO_PCM')), MIC_CHANNEL)
        elif msg.code == media('CONFIG'):
            config = schema.parse(SHARED + 'Config', msg.payload)
            if list(config.configuration_indices) != [0]:
                raise ProtocolError('Mock microphone setup failed')
        elif msg.code == media('MICROPHONE_RESPONSE'):
            reply = schema.parse(SOURCE + 'MicrophoneResponse', msg.payload)
            if reply.status != 0 or not reply.HasField('session_id'):
                raise ProtocolError('Mock microphone request failed')
            if self.mic_id is None:
                self.mic_id = reply.session_id
            elif self.mic_id == reply.session_id:
                self.mic_id = None
                self.backend.mic_closed += 1
        elif msg.code == media('DATA') and self.mic_id is not None:
            stamp = struct.unpack_from('>Q', msg.payload)[0]
            if stamp <= self.mic_stamp or msg.payload[8:] != pcm_bytes([2000]) * (MIC.rate // 50):
                raise ProtocolError('Mock received incorrect converted microphone samples')
            self.mic_stamp = stamp
            self.mic_blocks += 1
            self.backend.mic_blocks += 1
            self.send(media('ACK'), schema.message(SOURCE + 'Ack')(session_id=self.mic_id, ack=1), MIC_CHANNEL)
            if self.mic_blocks == 3:
                self.capture_request(False)
                self.send(ctrl('VOICE_SESSION_NOTIFICATION'), schema.message(CTL + 'VoiceSessionNotification')(status=2))
