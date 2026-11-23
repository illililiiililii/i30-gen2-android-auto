import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from i30_receiver.audio import AudioMixer, GUIDANCE, MIC, MUSIC, Microphone, PcmConverter, pcm_bytes, samples
from i30_receiver.integration import ProjectionHost
from i30_receiver.mock import MockPlayback, MockStockUi, VirtualClock, synthetic_h264
from i30_receiver.platform import Platform, quiet
from i30_receiver.protocol import INPUT_CHANNEL, VIDEO, ProtocolSession, Stage, keycode
from i30_receiver import schema
from i30_receiver.wire import ProtocolError


class Phase3Tests(unittest.TestCase):
    def test_pcm_conversion_keeps_phase_and_bounds_queued_audio(self):
        data = pcm_bytes([1000, 3000, 3000, 6000, -2000, 0] * 200)
        converter = PcmConverter(MUSIC, MIC)
        converted = converter.convert(data[:20]) + converter.convert(data[20:])
        self.assertEqual(converted, PcmConverter(MUSIC, MIC).convert(data))
        self.assertEqual(len(converted), len(data) // 6)
        with self.assertRaises(ProtocolError):
            converter.convert(b'\0')

        output = MockPlayback()
        mix = AudioMixer(output, volume=0.5)
        mix.push('audio', pcm_bytes([8000]) * (MUSIC.block_bytes(200) // 2))
        mix.push('guidance', pcm_bytes([2000]) * (GUIDANCE.block_bytes() // 2))
        self.assertEqual(len(mix.queues['audio']), MUSIC.block_bytes(120))
        self.assertGreater(mix.dropped, 0)
        mix.tick(0)
        self.assertFalse(output.active)
        mix.tick(0.02)
        self.assertEqual(set(samples(output.last)), {2000})
        mix.close()
        self.assertFalse(any(mix.queues.values()))
        self.assertEqual(output.closed, 1)

    def test_microphone_drops_stale_blocks_while_credit_is_exhausted(self):
        class Capture:
            format = MIC
            value = 0
            closed = False

            def start(self):
                pass

            def read(self):
                self.value += 1
                return pcm_bytes([self.value]) * (MIC.rate // 50)

            def close(self):
                self.closed = True

        capture = Capture()
        microphone = Microphone(capture)
        microphone.start()
        for _ in range(10):
            self.assertEqual(microphone.block(send=False), b'')
        self.assertLessEqual(len(microphone.pending), MIC.block_bytes(40))
        self.assertEqual(set(samples(microphone.block(send=True))), {10})
        microphone.close()
        self.assertTrue(capture.closed)
        self.assertEqual(microphone.block(send=True), b'')

    def test_preemption_releases_keys_and_touch_and_preserves_oem_input(self):
        clock = VirtualClock()
        ui = MockStockUi()
        host = ProjectionHost(ui)
        session = ProtocolSession(None, None, Platform(clock=clock.now), None, quiet, touch=True, host=host)
        sent = []
        session.emit = lambda code, body, channel=0, **_: sent.append((channel, body))
        session.stage = Stage.ACTIVE
        session.channels[INPUT_CHANNEL].status = 'bound'
        session.bound_keys = {keycode('MEDIA_NEXT')}
        session.requested_focus = session.video_focus = schema.value(VIDEO + 'VideoFocusMode', 'VIDEO_FOCUS_PROJECTED')
        host.attach(session)
        host.show()
        host.button('VOLUME_UP', True)
        host.button('SEEK_NEXT', True)
        session.pointer('ACTION_DOWN', 30, 30)
        session.pointer('ACTION_MOVED', 40, 40)
        host.preempt('reverse_camera', True)
        host.preempt('vehicle_warning', True)
        host.button('SEEK_NEXT', False)
        host.button('VOLUME_UP', False)
        host.preempt('reverse_camera', False)
        self.assertFalse(host.show())
        host.preempt('vehicle_warning', False)
        session.tick()
        self.assertTrue(host.show())
        self.assertEqual(ui.buttons, [('VOLUME_UP', True, False), ('VOLUME_UP', False, False)])
        reports = [report for channel, report in sent if channel == INPUT_CHANNEL]
        self.assertEqual([key.down for report in reports for key in report.key_event.keys], [True, False])
        self.assertEqual([report.touch_event.action for report in reports if report.HasField('touch_event')], [0, 2, 1])
        self.assertEqual(sorted(set(report.timestamp for report in reports)), [report.timestamp for report in reports])

    def test_packaged_mock_reconnect_restores_resources_then_captures_again(self):
        result = subprocess.run([sys.executable, str(ROOT / 'build/i30-receiver.pyz'), 'mock', '--phase3',
                                 '--scenario', 'unplug', '--reconnect', '--tap', '300', '230'],
                                capture_output=True, text=True, timeout=25)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(summary['active_sessions'], 2)
        self.assertEqual(summary['mock_links_closed'], 2)
        self.assertEqual(summary['mock_capture_releases'], 2)
        self.assertEqual(summary['mock_mic_blocks'], 3)
        self.assertEqual(summary['mock_ui_restores'], 3)
        self.assertEqual(summary['mock_oem_button_events'], 2)
        self.assertTrue(summary['mock_audio_mixed'])

    def test_pc_window_decodes_and_restores_stock(self):
        try:
            import av
            from tkinter import TclError
            from i30_receiver.display_pc import ProjectionWindow
        except ImportError as exc:
            self.skipTest(str(exc))
        try:
            window = ProjectionWindow(quiet, av, lambda: None)
        except TclError as exc:
            self.skipTest(str(exc))
        self.addCleanup(window.root.destroy)
        window.root.withdraw()
        host = window.host = ProjectionHost(window)
        self.assertFalse(host.show())
        window.channel(3, 'video', 'receiving')
        for packet in synthetic_h264(av):
            window.packet(3, 'video', 1, packet)
        self.assertTrue(host.show())
        self.assertEqual((window.image.width(), window.image.height()), (800, 480))
        window.queue('select', False)
        window.poll()
        self.assertFalse(host.visible)
        self.assertIsNone(window.image)


if __name__ == '__main__':
    unittest.main()
