from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_pc_video import inspect_clip

try:
    import av
except ImportError:
    av = None


@unittest.skipUnless(av is not None, "optional PyAV dependency is absent")
class PcVideoTests(unittest.TestCase):
    def test_packaged_session_decodes_video_and_sends_encrypted_tap(self):
        build = Path(__file__).resolve().parents[1] / "build/i30-receiver.pyz"
        if not build.is_file():
            self.skipTest("Build the zipapp first to test its entry point")
        with tempfile.TemporaryDirectory() as directory:
            preview = Path(directory) / "session.png"
            run = subprocess.run([sys.executable, str(build), "mock", "--tap", "44", "440",
                                  "--video-preview", str(preview)], capture_output=True, text=True, timeout=25)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            summary = json.loads(run.stdout.splitlines()[-1])
            self.assertEqual((summary["decoded_video_frames"], summary["mock_touch_reports"]), (3, 2))
            self.assertTrue(summary["graceful_shutdown"])
            with av.open(str(preview)) as png:
                frame = next(png.decode(video=0))
                self.assertEqual((frame.width, frame.height), (800, 480))

    def test_decodes_and_flushes_annex_b_without_overwriting_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            clip = Path(directory) / "test.h264"
            preview = Path(directory) / "first.png"
            encoder = av.CodecContext.create("libx264", "w")
            encoder.width, encoder.height = 64, 48
            encoder.pix_fmt = "yuv420p"
            encoder.time_base = Fraction(1, 30)
            with clip.open("wb") as stream:
                for index in range(6):
                    frame = av.VideoFrame(64, 48, "yuv420p")
                    frame.pts = index
                    for plane, value in zip(frame.planes, (32 + index * 20, 128, 128)):
                        plane.update(bytes([value]) * plane.buffer_size)
                    for packet in encoder.encode(frame):
                        stream.write(bytes(packet))
                for packet in encoder.encode():
                    stream.write(bytes(packet))

            result = inspect_clip(av, clip, preview)
            self.assertEqual((result["frames"], result["resolutions"]), (6, ["64x48"]))
            self.assertEqual(preview.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            with self.assertRaises(FileExistsError):
                inspect_clip(av, clip, preview)

    def test_empty_stream_has_no_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            clip = Path(directory) / "empty.h264"
            clip.touch()
            preview = Path(directory) / "unused.png"
            with self.assertRaisesRegex(ValueError, "no decodable frames"):
                inspect_clip(av, clip, preview)
            self.assertFalse(preview.exists())
