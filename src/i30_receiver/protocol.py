"""Head unit side of the PC projection control and diagnostic media channels."""

from contextlib import ExitStack
from dataclasses import dataclass
from enum import Enum
import struct

from . import schema
from .audio import GUIDANCE, MIC, MUSIC
from .integration import BUTTONS
from .wire import CONTROL, ENCRYPTED, FrameReader, Message, ProtocolError, Reassembler, encode

CTL = schema.CTL
MEDIA = schema.MEDIA
SHARED = MEDIA + "shared.message."
VIDEO = MEDIA + "video.message."
SOURCE = MEDIA + "source.message."
SINK = MEDIA + "sink.message."
INPUT = "aap_protobuf.service.inputsource."
INPUT_CHANNEL = 1
GUIDANCE_CHANNEL = 5
MIC_CHANNEL = 9
TOUCH_SIZE = (800, 480)
VERSION = (1, 6)  # AASDK_MAJOR/MINOR in the pinned release


def ctrl(name):
    return schema.value(CTL + "ControlMessageType", "MESSAGE_" + name)


def media(name):
    return schema.value(MEDIA + "sink.MediaMessageId", "MEDIA_MESSAGE_" + name)


def input_code(name):
    return schema.value(INPUT + "InputMessageId", "INPUT_MESSAGE_" + name)


def keycode(name):
    return schema.value(SINK + "KeyCode", "KEYCODE_" + name)


def validate_tap(x, y):
    width, height = TOUCH_SIZE
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError(f"Touch coordinates must be inside {width}x{height}")


def codec(name):
    return schema.value(SHARED + "MediaCodecType", "MEDIA_CODEC_" + name)


def version_request():
    return Message(0, 0, ctrl("VERSION_REQUEST"), struct.pack(">HH", *VERSION))


def version_response(message):
    if (message.channel != 0 or message.flags or message.code != ctrl("VERSION_RESPONSE")
            or len(message.payload) != 6):
        raise ProtocolError("Expected a six-byte version response on channel zero")
    major, minor, status = struct.unpack(">HHh", message.payload)
    if status != 0 or major != VERSION[0]:
        raise ProtocolError(f"Version refused or unsupported ({major}.{minor}, status={status})")
    return major, minor


class Stage(Enum):
    VERSION = "version"
    TLS = "tls"
    DISCOVERY = "discovery"
    ACTIVE = "active"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass
class Channel:
    kind: str
    codec: int | None = None
    status: str = "advertised"
    session_id: int | None = None


class ProtocolSession:
    def __init__(self, send, tls_factory, platform, sink, state_changed, *,
                 negotiation_seconds=10.0, ping_seconds=5.0, pong_seconds=4.0, touch=False,
                 host=None, audio=None, microphone=None):
        self.send = send
        self.tls_factory = tls_factory
        self.platform = platform
        self.sink = sink
        self.state_changed = state_changed
        self.host, self.audio, self.microphone = host, audio, microphone
        self.touch = touch
        self.keys = {keycode(name) for name in BUTTONS.values()} if host else set()
        self.bound_keys = set()
        self.held_keys = set()
        self.pointer_position = None
        self.input_stamp = 0
        self.audio_focused = False
        self.requested_focus = None
        self.video_focus = None
        self.mic_serial = 0
        self.mic_window = self.mic_pending = 0
        self.mic_stamp = 0
        self.reader = FrameReader(platform.allocate)
        self.assembler = Reassembler(platform.allocate)
        self.tls = None
        self.stage = Stage.VERSION
        self.deadline = platform.clock() + negotiation_seconds
        self.negotiation_seconds = negotiation_seconds
        self.ping_seconds = ping_seconds
        self.pong_seconds = pong_seconds
        self.next_ping = 0.0
        self.ping_stamp = None
        self.channels = {3: Channel("video", codec("VIDEO_H264_BP")),
                         4: Channel("audio", codec("AUDIO_PCM"))}
        if touch or self.keys:
            self.channels[INPUT_CHANNEL] = Channel("touch")
        if audio:
            self.channels[GUIDANCE_CHANNEL] = Channel("guidance", codec("AUDIO_PCM"))
        if microphone:
            self.channels[MIC_CHANNEL] = Channel("microphone", codec("AUDIO_PCM"))
        self.graceful = False
        self.announced = False
        self.ignored = set()

    def emit(self, code, payload=b"", channel=0, *, control=False, secure=True):
        flags = (CONTROL if control else 0) | (ENCRYPTED if secure else 0)
        data = payload if isinstance(payload, bytes) else payload.SerializeToString()
        for frame in encode(Message(channel, flags, code, data), self.tls.encrypt if secure else None):
            self.send(frame, 1000)
        if channel == 0 or code > 1:
            self.platform.log("protocol", direction="out", channel=channel, code=code,
                              size=len(data), encrypted=secure)

    def start(self):
        request = version_request()
        self.emit(request.code, request.payload, secure=False)

    def feed(self, data):
        for frame in self.reader.feed(data):
            secure = bool(frame.flags & ENCRYPTED)
            if secure and (self.tls is None or not self.tls.ready):
                raise ProtocolError("Encrypted packet arrived before TLS authentication")
            if not secure and self.stage not in {Stage.VERSION, Stage.TLS}:
                raise ProtocolError("Unprotected message after TLS authentication")
            plain = self.tls.decrypt(frame.payload) if secure else frame.payload
            message = self.assembler.push(frame, plain)
            if message is not None:
                self.handle(message)
            if self.stage == Stage.CLOSED:
                break

    def handle(self, message):
        channel, flags, code, payload = message.channel, message.flags, message.code, message.payload
        if channel == 0 or code > 1:
            self.platform.log("protocol", direction="in", channel=channel, code=code,
                              size=len(payload), encrypted=bool(flags & ENCRYPTED))
        if self.stage == Stage.VERSION:
            major, minor = version_response(message)
            self.platform.log("version", peer=f"{major}.{minor}", local=f"{VERSION[0]}.{VERSION[1]}")
            self.stage = Stage.TLS
            self.deadline = self.platform.clock() + self.negotiation_seconds
            self.tls = self.tls_factory()
            self.advance_tls(b"")
            return
        if self.stage == Stage.TLS:
            if channel != 0 or flags or code != ctrl("ENCAPSULATED_SSL") or not payload:
                raise ProtocolError("Expected encapsulated TLS handshake data")
            self.advance_tls(payload)
            return
        if channel == 0:
            if flags & CONTROL:
                raise ProtocolError("Invalid channel-zero message type")
            self.handle_control(code, payload)
        elif self.stage == Stage.ACTIVE:
            self.handle_channel(channel, flags, code, payload)
        elif self.stage != Stage.CLOSING:
            raise ProtocolError("Media channel message before service discovery")

    def advance_tls(self, payload):
        output = self.tls.handshake(payload)
        if output:
            self.emit(ctrl("ENCAPSULATED_SSL"), output, secure=False)
        if self.tls.ready:
            version, cipher = self.tls.negotiated()
            self.platform.log("tls_authenticated", version=version, cipher=cipher)
            self.emit(ctrl("AUTH_COMPLETE"), schema.message(CTL + "AuthResponse")(status=0), secure=False)
            self.stage = Stage.DISCOVERY
            self.deadline = self.platform.clock() + self.negotiation_seconds
            self.state_changed("Connected", "TLS authenticated")

    def discovery(self):
        response = schema.message(CTL + "ServiceDiscoveryResponse")(display_name="i30 PC Diagnostics")
        response.headunit_info.head_unit_make = "i30 Research"
        response.headunit_info.head_unit_model = "PC Diagnostics"
        response.headunit_info.head_unit_software_version = "0.2.0"
        for number, channel in sorted(self.channels.items()):
            descriptor = response.channels.add(id=number)
            if channel.kind == "touch":
                service = descriptor.input_source_service
                service.keycodes_supported.extend(sorted(self.keys))
                if self.touch:
                    width, height = TOUCH_SIZE
                    service.touchscreen.add(width=width, height=height)
                continue
            if channel.kind == "microphone":
                service = descriptor.media_source_service
                service.available_type = channel.codec
                service.available_while_in_call = False
                self.set_audio_format(service.audio_config, MIC)
                continue
            service = descriptor.media_sink_service
            service.available_type = channel.codec
            if channel.kind == "video":
                enums = MEDIA + "sink.message."
                service.video_configs.add(
                    codec_resolution=schema.value(enums + "VideoCodecResolutionType", "VIDEO_800x480"),
                    frame_rate=schema.value(enums + "VideoFrameRateType", "VIDEO_FPS_30"), density=160)
            else:
                guidance = channel.kind == "guidance"
                service.audio_type = schema.value(SINK + "AudioStreamType",
                                                  "AUDIO_STREAM_GUIDANCE" if guidance else "AUDIO_STREAM_MEDIA")
                self.set_audio_format(service.audio_configs.add(), GUIDANCE if guidance else MUSIC)
        return response

    @staticmethod
    def set_audio_format(config, fmt):
        config.sampling_rate = fmt.rate
        config.number_of_bits = 16
        config.number_of_channels = fmt.channels

    def audio_focus(self, grant, *, unsolicited):
        self.audio_focused = grant
        if not grant:
            self.audio.close()
        state = schema.value(CTL + "AudioFocusStateType", "AUDIO_FOCUS_STATE_GAIN" if grant else "AUDIO_FOCUS_STATE_LOSS")
        response = schema.message(CTL + "AudioFocusNotification")(focus_state=state, unsolicited=unsolicited)
        self.emit(ctrl("AUDIO_FOCUS_NOTIFICATION"), response)

    def handle_control(self, code, payload):
        if code == ctrl("BYEBYE_REQUEST"):
            schema.parse(CTL + "ByeByeRequest", payload)
            self.emit(ctrl("BYEBYE_RESPONSE"), schema.message(CTL + "ByeByeResponse")())
            self.graceful = True
            self.stage = Stage.CLOSED
            return
        if self.stage == Stage.CLOSING:
            if code == ctrl("BYEBYE_RESPONSE"):
                schema.parse(CTL + "ByeByeResponse", payload)
                self.graceful = True
                self.stage = Stage.CLOSED
            return
        if code == ctrl("PING_REQUEST"):
            request = schema.parse(CTL + "PingRequest", payload)
            response = schema.message(CTL + "PingResponse")(timestamp=request.timestamp)
            if request.HasField("data"):
                response.data = request.data
            self.emit(ctrl("PING_RESPONSE"), response)
            return
        if self.stage == Stage.DISCOVERY:
            if code != ctrl("SERVICE_DISCOVERY_REQUEST"):
                raise ProtocolError("Expected service discovery after TLS")
            schema.parse(CTL + "ServiceDiscoveryRequest", payload)
            self.emit(ctrl("SERVICE_DISCOVERY_RESPONSE"), self.discovery())
            self.stage = Stage.ACTIVE
            self.announced = True
            self.next_ping = self.platform.clock() + self.ping_seconds
            self.state_changed("SessionActive", "service discovery completed")
            for number, channel in self.channels.items():
                self.sink.channel(number, channel.kind, channel.status)
        elif code == ctrl("PING_RESPONSE"):
            response = schema.parse(CTL + "PingResponse", payload)
            if self.ping_stamp is not None and response.timestamp == self.ping_stamp:
                self.ping_stamp = None
                self.next_ping = self.platform.clock() + self.ping_seconds
        elif code == ctrl("AUDIO_FOCUS_REQUEST") and self.audio is not None:
            request = schema.parse(CTL + "AudioFocusRequest", payload)
            release = schema.value(CTL + "AudioFocusRequestType", "AUDIO_FOCUS_RELEASE")
            self.audio_focus(request.audio_focus_type != release and (self.host is None or self.host.available),
                             unsolicited=False)
        elif code == ctrl("VOICE_SESSION_NOTIFICATION") and self.microphone is not None:
            notice = schema.parse(CTL + "VoiceSessionNotification", payload)
            if notice.status == schema.value(CTL + "VoiceSessionStatus", "VOICE_SESSION_END"):
                self.stop_microphone()
        else:
            self.ignore(0, code)

    def ignore(self, channel, code):
        key = (channel, code)
        if key not in self.ignored and len(self.ignored) < 32:
            self.ignored.add(key)
            self.platform.log("unsupported_message", channel=channel, code=code)

    def channel_state(self, number, channel, status):
        channel.status = status
        self.sink.channel(number, channel.kind, status)

    def handle_channel(self, number, flags, code, payload):
        channel = self.channels.get(number)
        if flags & CONTROL and code == ctrl("CHANNEL_OPEN_REQUEST"):
            request = schema.parse(CTL + "ChannelOpenRequest", payload)
            valid = channel is not None and request.service_id == number and channel.status in ("advertised", "closed")
            status = "STATUS_SUCCESS" if valid else "STATUS_INVALID_SERVICE"
            response = schema.message(CTL + "ChannelOpenResponse")(
                status=schema.value("aap_protobuf.shared.MessageStatus", status))
            self.emit(ctrl("CHANNEL_OPEN_RESPONSE"), response, number, control=True)
            if valid:
                self.channel_state(number, channel, "open")
            return
        if channel is None or channel.status in ("closed", "advertised"):
            self.ignore(number, code)
            return
        if flags & CONTROL:
            if code == ctrl("CHANNEL_CLOSE_NOTIFICATION"):
                if channel.kind == "microphone":
                    self.stop_microphone()
                if self.audio and channel.kind in self.audio.streams:
                    self.audio.clear(channel.kind)
                if channel.kind == "touch":
                    self.bound_keys.clear()
                    self.held_keys.clear()
                    self.pointer_position = None
                if channel.kind == "video":
                    self.requested_focus = self.video_focus = None
                    if self.host:
                        self.host.hide()
                        self.revoke_projection()
                channel.session_id = None
                self.channel_state(number, channel, "closed")
            else:
                self.ignore(number, code)
        elif channel.kind == "touch":
            self.handle_touch(channel, code, payload)
        elif channel.kind == "microphone" and code != media("SETUP"):
            self.handle_microphone(number, channel, code, payload)
        else:
            self.handle_media(number, channel, code, payload)

    def handle_touch(self, channel, code, payload):
        if code != input_code("KEY_BINDING_REQUEST"):
            self.ignore(INPUT_CHANNEL, code)
            return
        request = schema.parse(MEDIA + "sink.message.KeyBindingRequest", payload)
        requested = set(request.keycodes)
        valid = requested <= self.keys
        if self.held_keys:
            self.release_keys()
        self.release_pointer()
        self.bound_keys = requested if valid else set()
        status = "STATUS_SUCCESS" if valid else "STATUS_KEYCODE_NOT_BOUND"
        response = schema.message(MEDIA + "sink.message.KeyBindingResponse")(
            status=schema.value("aap_protobuf.shared.MessageStatus", status))
        self.emit(input_code("KEY_BINDING_RESPONSE"), response, INPUT_CHANNEL)
        self.channel_state(INPUT_CHANNEL, channel, "bound" if valid else "open")

    @property
    def touch_ready(self):
        channel = self.channels.get(INPUT_CHANNEL)
        return self.touch and self.stage == Stage.ACTIVE and channel is not None and channel.status == "bound"

    def input_report(self):
        self.input_stamp = max(self.input_stamp + 1, int(self.platform.clock() * 1_000_000))
        return schema.message(INPUT + "message.InputReport")(timestamp=self.input_stamp)

    def key(self, name, down, longpress=False):
        code = keycode(name)
        if self.stage != Stage.ACTIVE or code not in self.bound_keys:
            return False
        if down and self.video_focus != schema.value(VIDEO + "VideoFocusMode", "VIDEO_FOCUS_PROJECTED"):
            return False
        if not down and code not in self.held_keys:
            return False
        report = self.input_report()
        report.key_event.keys.add(keycode=code, down=down, metastate=0, longpress=longpress)
        self.emit(input_code("INPUT_REPORT"), report, INPUT_CHANNEL)
        if down:
            self.held_keys.add(code)
        else:
            self.held_keys.discard(code)
        return True

    def release_keys(self):
        if self.held_keys and self.stage == Stage.ACTIVE:
            report = self.input_report()
            for code in sorted(self.held_keys):
                report.key_event.keys.add(keycode=code, down=False, metastate=0)
            self.emit(input_code("INPUT_REPORT"), report, INPUT_CHANNEL)
        self.held_keys.clear()

    def tap(self, x, y):
        validate_tap(x, y)
        if not self.touch_ready:
            raise ProtocolError("Touch input channel has not been bound")
        for action in ("ACTION_DOWN", "ACTION_UP"):
            self.emit_pointer(action, x, y)

    def emit_pointer(self, action, x, y):
        report = self.input_report()
        report.touch_event.action = schema.value(INPUT + "message.PointerAction", action)
        report.touch_event.action_index = 0
        report.touch_event.pointer_data.add(x=x, y=y, pointer_id=0)
        self.emit(input_code("INPUT_REPORT"), report, INPUT_CHANNEL)

    def pointer(self, action, x, y):
        validate_tap(x, y)
        if not self.touch_ready or not self.host or not self.host.visible or self.video_focus != schema.value(
                VIDEO + "VideoFocusMode", "VIDEO_FOCUS_PROJECTED"):
            return
        if (action == 'ACTION_DOWN') != (self.pointer_position is None):
            return   # Ignore moves or releases without a preceding down, and duplicate downs.
        self.emit_pointer(action, x, y)
        self.pointer_position = None if action == 'ACTION_UP' else (x, y)

    def release_pointer(self):
        if self.pointer_position is not None:
            x, y = self.pointer_position
            self.pointer_position = None
            if self.touch_ready:
                self.emit_pointer('ACTION_UP', x, y)

    def release_input(self):
        self.release_keys()
        self.release_pointer()

    def update_video_focus(self, *, unsolicited):
        if self.requested_focus is None:
            return
        native = schema.value(VIDEO + "VideoFocusMode", "VIDEO_FOCUS_NATIVE")
        allowed = self.host.available if self.host else getattr(self.sink, "wants_projection", False)
        focus = self.requested_focus if allowed else native
        if focus == native and self.host:
            self.host.hide()
            self.release_input()
        elif focus == schema.value(VIDEO + "VideoFocusMode", "VIDEO_FOCUS_PROJECTED_NO_INPUT_FOCUS"):
            self.release_input()
        if not unsolicited or focus != self.video_focus:
            self.video_focus = focus
            self.emit(media("VIDEO_FOCUS_NOTIFICATION"),
                      schema.message(VIDEO + "VideoFocusNotification")(focus=focus, unsolicited=unsolicited), 3)

    def revoke_projection(self):
        if self.stage != Stage.ACTIVE:
            return
        self.release_input()
        self.stop_microphone()
        if self.audio_focused:
            self.audio_focus(False, unsolicited=True)
        self.update_video_focus(unsolicited=True)

    def stop_microphone(self):
        channel = self.channels.get(MIC_CHANNEL)
        self.mic_pending = self.mic_window = 0
        if channel and channel.session_id is not None:
            channel.session_id = None
            self.microphone.close()

    def handle_microphone(self, number, channel, code, payload):
        if code == media("ACK"):
            ack = schema.parse(SOURCE + "Ack", payload)
            if channel.session_id is not None and ack.session_id == channel.session_id:
                self.mic_pending = max(0, self.mic_pending - max(0, ack.ack))
            return
        if code == media("STOP"):
            schema.parse(SHARED + "Stop", payload)
            self.stop_microphone()
            return
        if code != media("MICROPHONE_REQUEST"):
            self.ignore(number, code)
            return
        request = schema.parse(SOURCE + "MicrophoneRequest", payload)
        status = "STATUS_SUCCESS"
        session_id = channel.session_id
        if not request.open:
            self.stop_microphone()
        elif channel.status != "configured" or (self.host and not self.host.available):
            status = "STATUS_BUSY"
        elif session_id is None:
            try:
                self.microphone.start()
            except OSError as exc:
                self.platform.log("microphone_unavailable", message=str(exc))
                status = "STATUS_BUSY"
            else:
                self.mic_serial += 1
                session_id = channel.session_id = self.mic_serial
                self.mic_window = min(4, max(1, request.max_unacked))
                self.mic_stamp = 0
        response = schema.message(SOURCE + "MicrophoneResponse")(
            status=schema.value("aap_protobuf.shared.MessageStatus", status))
        if session_id is not None:
            response.session_id = session_id
        self.emit(media("MICROPHONE_RESPONSE"), response, number)

    def pump_microphone(self):
        channel = self.channels.get(MIC_CHANNEL)
        if self.mic_window and channel.session_id is not None:
            block = self.microphone.block(send=self.mic_pending < self.mic_window)
            if block:
                self.mic_stamp = max(self.mic_stamp + 20_000, int(self.platform.clock() * 1_000_000))
                self.emit(media("DATA"), struct.pack(">Q", self.mic_stamp) + block, MIC_CHANNEL)
                self.mic_pending += 1

    def handle_media(self, number, channel, code, payload):
        if code == media("SETUP"):
            request = schema.parse(SHARED + "Setup", payload)
            ready = request.type == channel.codec and channel.status in ("open", "configured")
            status = schema.value(SHARED + "Config.Status", "STATUS_READY" if ready else "STATUS_WAIT")
            config = schema.message(SHARED + "Config")(status=status, max_unacked=1)
            if ready:
                config.configuration_indices.append(0)
                self.channel_state(number, channel, "configured")
            self.emit(media("CONFIG"), config, number)
        elif code == media("START"):
            request = schema.parse(SHARED + "Start", payload)
            if channel.status != "configured" or request.configuration_index != 0:
                raise ProtocolError("Media start without matching setup")
            channel.session_id = request.session_id
            self.channel_state(number, channel, "receiving")
        elif code == media("STOP"):
            schema.parse(SHARED + "Stop", payload)
            channel.session_id = None
            self.channel_state(number, channel, "open")
            if channel.kind == "video" and self.host:
                self.host.hide()
                self.release_input()
        elif channel.kind == "video" and code == media("VIDEO_FOCUS_REQUEST"):
            request = schema.parse(VIDEO + "VideoFocusRequestNotification", payload)
            modes = VIDEO + "VideoFocusMode"
            projections = {schema.value(modes, "VIDEO_FOCUS_PROJECTED"),
                           schema.value(modes, "VIDEO_FOCUS_PROJECTED_NO_INPUT_FOCUS")}
            self.requested_focus = request.mode if request.mode in projections else schema.value(modes, "VIDEO_FOCUS_NATIVE")
            self.update_video_focus(unsolicited=False)
        elif code in (media("DATA"), media("CODEC_CONFIG")) and channel.session_id is not None:
            timestamp = None
            if code == media("DATA"):
                if len(payload) <= 8:
                    raise ProtocolError("Timestamped media packet is truncated")
                timestamp = struct.unpack_from(">Q", payload)[0]
                payload = payload[8:]
            if not payload:
                raise ProtocolError("Empty media packet")
            self.sink.packet(number, channel.kind, timestamp, payload)
            if channel.kind == "video" and self.host and self.video_focus in (
                    schema.value(VIDEO + "VideoFocusMode", "VIDEO_FOCUS_PROJECTED"),
                    schema.value(VIDEO + "VideoFocusMode", "VIDEO_FOCUS_PROJECTED_NO_INPUT_FOCUS")):
                if timestamp is not None:
                    self.host.show()
            if self.audio_focused and channel.kind in ("audio", "guidance") and timestamp is not None:
                self.audio.push(channel.kind, payload)
            ack = schema.message(MEDIA + "source.message.Ack")(session_id=channel.session_id, ack=1)
            self.emit(media("ACK"), ack, number)
        else:
            self.ignore(number, code)

    def tick(self):
        now = self.platform.clock()
        if self.stage not in (Stage.ACTIVE, Stage.CLOSED) and now >= self.deadline:
            if self.stage == Stage.CLOSING:
                self.stage = Stage.CLOSED
                return
            raise ProtocolError(f"{self.stage.value} deadline expired")
        if self.stage != Stage.ACTIVE:
            return
        if self.host and self.host.available and self.requested_focus != self.video_focus:
            self.update_video_focus(unsolicited=True)
        if self.audio_focused:
            self.audio.tick(now)
        self.pump_microphone()
        if self.ping_stamp is not None:
            if now >= self.deadline:
                raise ProtocolError("Keepalive response deadline expired")
        elif now >= self.next_ping:
            self.ping_stamp = int(now * 1_000_000)
            self.deadline = now + self.pong_seconds
            self.emit(ctrl("PING_REQUEST"), schema.message(CTL + "PingRequest")(timestamp=self.ping_stamp))

    def shutdown(self):
        if self.stage in (Stage.DISCOVERY, Stage.ACTIVE):
            self.release_input()
            if self.host:
                self.host.hide()
            self.stop_microphone()
            if self.audio:
                self.audio.close()
                self.audio_focused = False
            reason = schema.value(CTL + "ByeByeReason", "USER_SELECTION")
            self.emit(ctrl("BYEBYE_REQUEST"), schema.message(CTL + "ByeByeRequest")(reason=reason))
            self.stage = Stage.CLOSING
            self.deadline = self.platform.clock() + 2.0
        elif self.stage != Stage.CLOSING:
            self.stage = Stage.CLOSED

    def release_channels(self):
        with ExitStack() as cleanup:
            if self.announced:
                for number, channel in self.channels.items():
                    if channel.status != "closed":
                        cleanup.callback(self.sink.channel, number, channel.kind, "closed")
            if self.audio:
                cleanup.callback(self.audio.close)
            if self.microphone:
                cleanup.callback(self.microphone.close)
            if self.host:
                cleanup.callback(self.host.detach)
