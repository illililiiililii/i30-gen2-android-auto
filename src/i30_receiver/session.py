"""Timed connection lifecycle, shared by USB and mock transports."""

from dataclasses import asdict, dataclass, field
from enum import Enum
from math import isfinite

from .protocol import ProtocolSession, Stage, validate_tap
from .transport import Timeout, TransportError
from .wire import ProtocolError


class State(str, Enum):
    DISCONNECTED = "Disconnected"
    DEVICE_DETECTED = "DeviceDetected"
    NEGOTIATING = "Negotiating"
    CONNECTED = "Connected"
    ACTIVE = "SessionActive"
    ERROR = "Error"
    RECONNECTING = "Reconnecting"


@dataclass
class Result:
    attempts: int = 0
    active_sessions: int = 0
    graceful_shutdown: bool = False
    taps_sent: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self):
        return asdict(self)


class SessionManager:
    def __init__(self, transport, tls_factory, platform, sink, *, detect_seconds=8.0,
                 retry_seconds=0.5, timeout_seconds=10.0, ping_seconds=5.0, pong_seconds=4.0,
                 tap=None, host=None, audio=None, microphone=None, poll_ui=None, touch_input=False):
        self.transport = transport
        self.tls_factory = tls_factory
        self.platform = platform
        self.sink = sink
        self.detect_seconds = detect_seconds
        self.retry_seconds = retry_seconds
        self.timeout_seconds = timeout_seconds
        self.ping_seconds = ping_seconds
        self.pong_seconds = pong_seconds
        if tap is not None:
            validate_tap(*tap)
        self.tap = tap
        self.host, self.audio, self.microphone = host, audio, microphone
        self.poll_ui = poll_ui
        self.touch_input = touch_input
        self.state = State.DISCONNECTED

    def change(self, state, detail):
        self.state = State(state)
        self.platform.log("state", state=self.state.value, detail=detail)

    def wait_device(self):
        deadline = self.platform.clock() + self.detect_seconds
        while not self.platform.stop_requested() and self.platform.clock() < deadline:
            device = self.transport.detect()
            if device is not None:
                return device
            self.platform.pause(0.1)
            if self.poll_ui:
                self.poll_ui()
        if self.platform.stop_requested():
            return None
        raise Timeout("No USB device appeared on the selected port")

    def run_connected(self, link, version_packet, seconds=None):
        """Take ownership of a USB link whose version request was sent by the guest."""
        return self._run(1, seconds, connected=(link, version_packet))

    def run(self, attempts=1, seconds=None):
        return self._run(attempts, seconds)

    def _run(self, attempts, seconds, connected=None):
        if not 1 <= attempts <= 20 or (seconds is not None and (not isfinite(seconds) or seconds <= 0)):
            if connected is not None:
                connected[0].close()
            raise ValueError("Invalid attempt count or session duration")
        result = Result()
        tap_attempted = False
        self.change(State.DISCONNECTED, "ready")
        for index in range(attempts):
            if connected is None and self.platform.stop_requested():
                break
            if index:
                self.change(State.RECONNECTING, f"attempt {index + 1}")
                self.platform.pause(self.retry_seconds)
            link, session = None, None
            result.attempts += 1
            try:
                if connected is None:
                    device = self.wait_device()
                    if device is None:
                        break
                    self.change(State.DEVICE_DETECTED, f"{device.vendor:04x}:{device.product:04x} on {device.port}")
                    self.change(State.NEGOTIATING, "opening accessory transport")
                    link = self.transport.connect(device)
                else:
                    link, version_packet = connected
                    if self.platform.stop_requested():
                        break
                    self.change(State.NEGOTIATING, "continuing after guest version exchange")
                session = ProtocolSession(link.write, self.tls_factory, self.platform, self.sink,
                                          self.change, negotiation_seconds=self.timeout_seconds,
                                          ping_seconds=self.ping_seconds, pong_seconds=self.pong_seconds,
                                          touch=self.touch_input or (self.tap is not None and not tap_attempted),
                                          host=self.host, audio=self.audio, microphone=self.microphone)
                if self.host:
                    self.host.attach(session)
                if connected is None:
                    session.start()
                else:
                    session.feed(version_packet)
                    if session.stage != Stage.TLS:
                        raise ProtocolError("Guest did not provide a complete version response")
                active_until = None
                while session.stage != Stage.CLOSED:
                    if self.poll_ui:
                        self.poll_ui()
                    now = self.platform.clock()
                    if seconds is not None and session.announced and active_until is None:
                        active_until = now + seconds
                    if self.platform.stop_requested() or (active_until is not None and now >= active_until):
                        if session.stage != Stage.CLOSING:
                            session.shutdown()
                    session.tick()
                    if session.stage == Stage.CLOSED:
                        break
                    try:
                        packet = link.read(20 if self.audio or self.microphone or self.poll_ui else 150)
                    except Timeout:
                        continue  # USB read polls may time out even while the session is healthy.
                    if packet:
                        session.feed(packet)
                    if self.tap is not None and session.touch_ready and not tap_attempted:
                        tap_attempted = True
                        session.tap(*self.tap)
                        result.taps_sent += 1
                        self.platform.log("touch_sent", x=self.tap[0], y=self.tap[1])
                result.graceful_shutdown = session.graceful
                if not session.graceful and not self.platform.stop_requested():
                    raise ProtocolError("Peer did not acknowledge shutdown")
                break
            except (OSError, TransportError, ProtocolError) as exc:
                result.errors.append(str(exc))
                self.change(State.ERROR, str(exc))
            finally:
                try:
                    if session is not None:
                        result.active_sessions += int(session.announced)
                        session.release_channels()
                finally:
                    try:
                        if link is not None:
                            link.close()
                    finally:
                        self.change(State.DISCONNECTED, "resources released")
        return result
