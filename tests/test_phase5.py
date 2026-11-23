import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from i30_receiver import schema
from i30_receiver.audio import AudioMixer, Microphone, MUSIC
from i30_receiver.cli import openssl_path
from i30_receiver.integration import ProjectionHost
from i30_receiver.mock import MockCapture, MockPlayback, MockStockUi, MockUsb, PORT, VirtualClock, mock_client, test_identity
from i30_receiver.platform import DiagnosticSink, Platform, quiet
from i30_receiver.protocol import MIC_CHANNEL, SOURCE, ProtocolSession, Stage, media
from i30_receiver.session import SessionManager
from i30_receiver.transport import AoaTransport


class Phase5Tests(unittest.TestCase):
    def test_microphone_credit_stays_closed_until_current_ack(self):
        timer = VirtualClock()
        capture = MockCapture(timer.now)
        session = ProtocolSession(None, None, Platform(clock=timer.now), None, quiet, microphone=Microphone(capture))
        session.stage = Stage.ACTIVE
        mic = session.channels[MIC_CHANNEL]
        mic.status = 'configured'
        sent = []
        session.emit = lambda code, payload, *_: sent.append((code, payload))
        start = schema.message(SOURCE + 'MicrophoneRequest')(open=True, max_unacked=2)
        session.handle_microphone(MIC_CHANNEL, mic, media('MICROPHONE_REQUEST'), start.SerializeToString())
        for _ in range(10):
            timer.pause(0.021)
            session.pump_microphone()
        self.assertEqual([code for code, _ in sent].count(media('DATA')), 2)
        self.assertLessEqual(len(session.microphone.pending), 1280)
        ack = schema.message(SOURCE + 'Ack')(session_id=mic.session_id + 1, ack=1)
        session.handle_microphone(MIC_CHANNEL, mic, media('ACK'), ack.SerializeToString())
        session.pump_microphone()
        self.assertEqual(session.mic_pending, 2)
        self.assertEqual(len(sent), 3)
        ack.session_id = mic.session_id
        session.handle_microphone(MIC_CHANNEL, mic, media('ACK'), ack.SerializeToString())
        session.pump_microphone()
        self.assertEqual(len(sent), 4)
        self.assertEqual(sent[-1][0], media('DATA'))
        session.stop_microphone()
        self.assertEqual(capture.closed, 1)

    def test_playback_error_after_device_acquisition_releases_device(self):
        class FailingOutput(MockPlayback):
            def start(self):
                super().start()
                raise OSError('mock playback device busy after first buffer')

        output = FailingOutput()
        mix = AudioMixer(output)
        mix.push('audio', bytes(MUSIC.block_bytes()))
        mix.tick(0)
        with self.assertRaisesRegex(OSError, 'device busy'):
            mix.tick(0.03)
        self.assertTrue(output.active)
        ProtocolSession(None, None, Platform(), None, quiet, audio=mix).release_channels()
        self.assertFalse(output.active)
        self.assertFalse(any(mix.queues.values()))
        self.assertEqual(output.closed, 1)

    def test_camera_preemption_survives_reconnect_until_oem_releases_it(self):
        timer = VirtualClock()
        ui = MockStockUi()
        host = ProjectionHost(ui)
        messages = []
        platform = Platform(clock=timer.now, pause=timer.pause)
        capture = Microphone(MockCapture(timer.now))
        output = AudioMixer(MockPlayback())

        def events():
            if host.session is None:
                return
            if not messages and host.visible:
                host.preempt('camera', True)
                messages.append(('camera', host.visible))
            elif messages == [('camera', False)] and backend.claimed == 2 and host.session.requested_focus is not None:
                messages.append(('reconnected', host.visible))
                host.preempt('camera', False)
            elif len(messages) == 2 and host.visible:
                messages.append(('oem_released', host.visible))

        with test_identity(openssl_path()) as (cert, key, server):
            backend = MockUsb(server, platform, ('unplug', 'ok'), phase3=True)
            manager = SessionManager(AoaTransport(backend, PORT, platform), mock_client(cert, key), platform,
                                     DiagnosticSink(quiet), host=host, audio=output, microphone=capture, poll_ui=events)
            result = manager.run(attempts=2, seconds=1)
        self.assertEqual(messages, [('camera', False), ('reconnected', False), ('oem_released', True)])
        self.assertFalse(host.visible)
        self.assertEqual(backend.closed, 2)
        self.assertTrue(result.graceful_shutdown)

    def test_built_arm_probe_releases_resources_on_success_and_startup_failures(self):
        probe = ROOT / 'build/ce-minimal/i30-ce-probe.exe'
        if not probe.is_file():
            self.skipTest('Build the optional CE probe first')
        try:
            import pefile, unicorn  # noqa: F401
        except ImportError as exc:
            self.skipTest(str(exc))
        for option, exit_status in ((None, 0), ('--deny-file', 1), ('--deny-thread', 2)):
            with self.subTest(option=option):
                args = [sys.executable, str(ROOT / 'tools/emulate_ce_probe.py'), str(probe)]
                if option:
                    args.append(option)
                result = subprocess.run(args, capture_output=True, text=True, timeout=8, check=True)
                record = json.loads(result.stdout)
                self.assertEqual(record['exit_status'], exit_status)
                self.assertEqual(record['thread_callback_exit'], None if exit_status == 2 else 17)
                self.assertEqual('ReadFile' in record['calls'], exit_status != 1)
                self.assertIn('HeapFree', record['calls'])
                self.assertGreater(record['stack_write_depth_bytes']['main'], 0)
                self.assertEqual(record['peak_probe_heap_bytes'], 4)


if __name__ == '__main__':
    unittest.main()
