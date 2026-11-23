"""Host-side Android Auto session and video surface for the GD13MY viewer."""

from collections import deque
from contextlib import nullcontext
import json
from pathlib import Path
import subprocess
import sys
from threading import Event, Lock, Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from i30_receiver.audio import AudioMixer, Microphone
from i30_receiver.integration import ProjectionHost
from i30_receiver.platform import DiagnosticSink, Platform
from i30_receiver.protocol import TOUCH_SIZE
from i30_receiver.session import SessionManager
from i30_receiver.transport import AoaTransport, TransportError
from i30_receiver.video import H264Decoder, frame_ppm
from i30_receiver.wire import ProtocolError


class ProjectionSurface(DiagnosticSink):
    """Decode video on the receiver thread and publish only the newest full frame."""

    wants_projection = True

    def __init__(self, av, log, publish):
        super().__init__(log)
        self.av, self.publish = av, publish
        self.decoder = self.pending = None
        self.host = ProjectionHost(self)
        self.frame_count = 0

    def show_projection(self):
        if self.pending is None:
            return False
        self.publish(self.pending)
        return True

    def restore_stock(self):
        self.pending = None
        self.publish(None)

    def stock_button(self, button, down, longpress):
        # The viewer sends its own stock keys directly to the guest.
        pass

    def channel(self, channel, kind, state):
        super().channel(channel, kind, state)
        if kind != 'video':
            return
        self.pending = None
        try:
            self.decoder = H264Decoder(self.av) if state == 'receiving' else None
        except (ValueError, self.av.FFmpegError) as exc:
            raise ProtocolError(f'GD13MY projection decoder setup failed: {exc}') from exc
        if state in ('open', 'closed'):
            self.publish(None)

    def packet(self, channel, kind, timestamp, data):
        super().packet(channel, kind, timestamp, data)
        if kind != 'video' or self.decoder is None:
            return
        try:
            for frame in self.decoder.push(data):
                self.frame_count += 1
                if self.host.available:
                    self.pending = frame_ppm(frame, *TOUCH_SIZE)
            if self.host.visible and self.pending is not None:
                self.publish(self.pending)
        except (ValueError, self.av.FFmpegError) as exc:
            raise ProtocolError(f'GD13MY projection decode failed: {exc}') from exc


class Projection:
    """Own one receiver only, with a bounded input queue and a single latest frame."""

    def __init__(self, av, messages, output, *, tls_factory=None, mock=False, audio_out=None, mic_in=None):
        self.av, self.messages = av, messages
        self.log_path = output.with_suffix('.projection.jsonl')
        self.tls_factory, self.mock = tls_factory, mock
        self.audio_out, self.mic_in = audio_out, mic_in
        self.ready = Event()
        self.stock_priority = Event()
        self.stop = Event()
        self.worker = None
        self.latest = None
        self.events = deque()
        self.lock = Lock()

    @property
    def running(self):
        return self.worker is not None and self.worker.is_alive()

    def publish(self, frame):
        self.latest = frame

    def frame(self):
        if not self.ready.is_set() or self.stock_priority.is_set() or self.stop.is_set():
            return None
        return self.latest

    def queue(self, event, *args):
        if self.running:
            with self.lock:
                if len(self.events) >= 128:
                    self.events.clear()
                    self.events.append(('reset', ()))
                    return
                if event == 'pointer' and args[0] == 'ACTION_MOVED' and self.events:
                    last_event, last_args = self.events[-1]
                    if last_event == 'pointer' and last_args[0] == 'ACTION_MOVED':
                        self.events.pop()
                self.events.append((event, args))

    def poll_input(self, host):
        blocked = not self.ready.is_set() or self.stock_priority.is_set() or self.stop.is_set()
        if blocked != ('stock' in host.blockers):
            host.preempt('stock', blocked)
        with self.lock:
            events = tuple(self.events)
            self.events.clear()
        session = host.session
        if session is None:
            return
        for event, args in events:
            if event == 'reset':
                session.release_input()
            elif not blocked and event == 'pointer':
                session.pointer(*args)
            elif not blocked and event == 'key':
                host.button(*args)

    def start(self, claimed=None):
        if self.running:
            if claimed:
                claimed[0].close()
            return
        if claimed is None and not self.mock:
            return
        self.stop.clear()
        self.publish(None)
        with self.lock:
            self.events.clear()
        self.worker = Thread(target=self.receive, args=(claimed,), name='GD13MY projection')
        try:
            self.worker.start()
        except RuntimeError:
            if claimed:
                claimed[0].close()
            raise

    def close(self):
        self.stop.set()
        if self.running:
            self.worker.join()

    def receive(self, claimed):
        from i30_receiver.cli import openssl_path
        from i30_receiver.mock import MockCapture, MockPlayback, MockUsb, PORT, mock_client, synthetic_h264, test_identity

        mode = '모의 투사' if self.mock else 'Android Auto'
        self.messages.put(('projection', f'{mode} · 연결 중'))
        ownership = claimed
        try:
            identity = test_identity(openssl_path()) if self.mock else nullcontext()
            with self.log_path.open('a', encoding='utf-8', buffering=1) as out, identity as mock_identity:
                def log(event, **detail):
                    print(json.dumps({'event': event, **detail}, ensure_ascii=False), file=out)
                    if event == 'state' and detail['state'] in ('Connected', 'SessionActive', 'Error'):
                        labels = {'Connected': 'TLS 인증 완료', 'SessionActive': '서비스 연결 완료', 'Error': detail['detail']}
                        self.messages.put(('projection', f'{mode} · {labels[detail["state"]]}'))

                platform = Platform(log=log, stop_requested=self.stop.is_set)
                sink = ProjectionSurface(self.av, log, self.publish)
                transport, audio, microphone = None, None, None
                tls_factory = self.tls_factory
                if self.mock:
                    cert, key, server = mock_identity
                    tls_factory = mock_client(cert, key)
                    backend = MockUsb(server, platform, phase3=True, interactive=True,
                                      video_packets=synthetic_h264(self.av))
                    transport = AoaTransport(backend, PORT, platform)
                    audio = AudioMixer(MockPlayback())
                    microphone = Microphone(MockCapture(platform.clock))
                elif self.audio_out is not None or self.mic_in is not None:
                    from i30_receiver.audio_win import WaveCapture, WavePlayback
                    if self.audio_out is not None:
                        audio = AudioMixer(WavePlayback(self.audio_out))
                    if self.mic_in is not None:
                        microphone = Microphone(WaveCapture(self.mic_in))
                manager = SessionManager(transport, tls_factory, platform, sink, host=sink.host,
                                         audio=audio, microphone=microphone, touch_input=True,
                                         poll_ui=lambda: self.poll_input(sink.host))
                if claimed:
                    ownership = None
                    result = manager.run_connected(*claimed)
                else:
                    result = manager.run()
                log('summary', decoded_frames=sink.frame_count, **result.as_dict())
                if result.errors:
                    self.messages.put(('projection', f'{mode} 종료 · {result.errors[-1]}'))
                else:
                    self.messages.put(('projection', f'{mode} 종료 · 순정 화면'))
        except (ImportError, OSError, ValueError, TransportError, ProtocolError,
                subprocess.SubprocessError, self.av.FFmpegError) as exc:
            self.messages.put(('projection', f'{mode} 종료 · {exc}'))
        finally:
            try:
                if ownership:
                    ownership[0].close()
            finally:
                self.publish(None)
