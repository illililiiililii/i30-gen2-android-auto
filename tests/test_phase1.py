import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from phase1_rom import collect, expand
from phase1_scan import scan
from projection_frames import mock_exchange, read_frame


class ProjectionFrameTests(unittest.TestCase):
    def test_complete_request(self):
        data = io.BytesIO(bytes.fromhex("00 03 00 06 00 01 00 01 00 07"))
        frame = read_frame(data)
        self.assertEqual((frame.channel, frame.message_id, frame.version_words_be), (0, 1, (1, 7)))
        self.assertIsNone(read_frame(data))

    def test_fragment_and_ciphertext_are_not_read_as_message_id(self):
        stream = io.BytesIO(bytes.fromhex(
            "01 01 00 02 00 00 00 04 12 34 "
            "01 02 00 02 56 78 "
            "00 0b 00 02 00 01"
        ))
        first, last, encrypted = (read_frame(stream) for _ in range(3))
        self.assertEqual(first.announced_message_bytes, 4)
        self.assertIsNone(last.message_id)
        self.assertIsNone(encrypted.message_id)
        self.assertIsNone(read_frame(stream))

    def test_truncated_and_inconsistent_inputs(self):
        for binary in ("00", "00 03 00 05 00 01", "00 03 00 02 00 01", "01 01 00 00 ff ff ff ff"):
            with self.subTest(binary=binary), self.assertRaises(ValueError):
                read_frame(io.BytesIO(bytes.fromhex(binary)))

    def test_socket_pair_round_trip(self):
        self.assertEqual(mock_exchange()["response"]["version_words_be"], (1, 7, 0))


class WindowsCETests(unittest.TestCase):
    def test_reject_bad_lzx_block_table(self):
        with self.assertRaisesRegex(ValueError, "Invalid CE block boundaries"):
            expand(bytes.fromhex("00 10 00 03 00 00 00"), 4096)

    def test_actual_rom_and_library_edges(self):
        from tempfile import TemporaryDirectory
        rom_path = ROOT / "firmware/extracted/GD13MY/BSP/0002dfc7_kernel"
        source = ROOT / "firmware/extracted/GD13MY/APP/002c98d9_LibMMCodec.dll"
        if not (rom_path.is_file() and source.is_file()):
            self.skipTest("Phase 0 extracts missing")
        if not (ROOT / "tools/vendor/wince-decompr/wincedecompr.py").is_file():
            self.skipTest("Pinned CE decompressor missing")
        with TemporaryDirectory() as directory:
            output = Path(directory)
            rom = collect(rom_path.read_bytes(), output)
            self.assertEqual(rom["modules"]["nk.exe"]["subsystem_version"], [6, 0])
            self.assertEqual((output / "default.hv").read_bytes()[8:12], b"EKIM")
            vid = (output / "videodev.dll").read_bytes()
            self.assertEqual(len(vid), 60928)
            self.assertEqual(hashlib.sha256(vid).hexdigest(), rom["files"]["videodev.dll"]["sha256"])
            self.assertIn("VID_IOControl", {e["name"] for e in rom["files"]["videodev.dll"]["interfaces"]["exports"]})
            info = next(iter(scan([source], rom).values()))
            self.assertEqual(info["format"], "Windows CE PE ARM Thumb")
            imports = {x["raw"]: x["name"] for x in info["resolved_imports"]["COREDLL.dll"]}
            self.assertEqual(imports["ordinal:168"], "CreateFileW")
            self.assertIn({"raw": "DirectDrawCreate", "name": "DirectDrawCreate"}, info["resolved_imports"]["DDRAW.dll"])


if __name__ == "__main__":
    unittest.main()
