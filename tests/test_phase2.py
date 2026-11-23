"""PC receiver tests. The adversarial inputs remain entirely local."""

from contextlib import ExitStack
import gc
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tracemalloc
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from i30_receiver import schema
from i30_receiver.mock import MockUsb, PORT, VirtualClock, mock_client, test_identity
from i30_receiver.platform import DiagnosticSink, Platform, quiet
from i30_receiver.probe import probe
from i30_receiver.protocol import ProtocolSession, Stage, ctrl, version_request
from i30_receiver.session import SessionManager, State
from i30_receiver.tls import client_context
from i30_receiver.transport import AoaTransport, InterfaceNotReady, Timeout
from i30_receiver.wire import (BULK, ENCRYPTED, FIRST, LAST, Frame, FrameReader, Message,
                               ProtocolError, Reassembler, encode)


class WireTests(unittest.TestCase):
    def test_real_request_wire_vector(self):
        self.assertEqual(list(encode(version_request())), [bytes.fromhex("00 03 00 06 00 01 00 01 00 06")])

    def test_interleaved_channels_and_one_byte_reads(self):
        a = Message(3, 0, 0x8000, b"abcdef")
        b = Message(4, 0, 0x8001, b"wxyz")
        chunks = list(encode(a, fragment_size=4))
        wire = b"".join([chunks[0], *encode(b), *chunks[1:]])
        reader, assembler = FrameReader(), Reassembler()
        output = []
        for byte in wire:
            for frame in reader.feed(bytes([byte])):
                message = assembler.push(frame, frame.payload)
                if message:
                    output.append(message)
        self.assertEqual(output, [b, a])
        self.assertEqual(assembler.reserved, 0)
        self.assertEqual(len(reader.buffer), 0)

    def test_zero_oversize_unrecognized_flags_and_total(self):
        for wire in ("00 03 00 00", "00 03 ff ff", "00 83 00 02", "00 01 00 02 ff ff ff ff 00 01"):
            with self.subTest(wire=wire), self.assertRaises(ProtocolError):
                list(FrameReader().feed(bytes.fromhex(wire)))

    def test_orphan_last_and_truncated_declared_message(self):
        assembler = Reassembler()
        with self.assertRaises(ProtocolError):
            assembler.push(Frame(2, LAST, b"x"), b"x")
        assembler.push(Frame(2, FIRST, b"ab", 8), b"ab")
        with self.assertRaises(ProtocolError):
            assembler.push(Frame(2, LAST, b"x"), b"x")

    def test_reservation_cap(self):
        assembler = Reassembler()
        for channel in range(2):
            assembler.push(Frame(channel, FIRST, b"ab", 2 * 1024 * 1024), b"ab")
        with self.assertRaisesRegex(ProtocolError, "budget"):
            assembler.push(Frame(2, FIRST, b"ab", 8), b"ab")

    def test_corrupt_protobuf_and_missing_required_field(self):
        for wire in (b"\xff", b""):
            with self.subTest(wire=wire), self.assertRaises(ProtocolError):
                schema.parse(schema.CTL + "PingRequest", wire)
        self.assertEqual(schema.parse(schema.CTL + "PingRequest", b"\x08\x2a").timestamp, 42)

    def test_bad_handshake_messages_never_activate(self):
        for flags, code, payload in ((0, ctrl("AUTH_COMPLETE"), b"\x08\x00"),
                                     (0, ctrl("VERSION_RESPONSE"), b"\x00"),
                                     (0, ctrl("VERSION_RESPONSE"), bytes.fromhex("00 01 00 06 ff ff"))):
            receiver = ProtocolSession(lambda *_: None, lambda: self.fail("unexpected TLS start"),
                                       Platform(), DiagnosticSink(quiet), lambda *_: None)
            with self.assertRaises(ProtocolError):
                receiver.handle(Message(0, flags, code, payload))
            self.assertEqual(receiver.stage, Stage.VERSION)
        receiver = ProtocolSession(lambda *_: None, lambda: None,
                                   Platform(), DiagnosticSink(quiet), lambda *_: None)
        with self.assertRaisesRegex(ProtocolError, "before TLS"):
            receiver.feed(bytes((0, BULK | ENCRYPTED, 0, 2, 0, 5)))


class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        openssl = shutil.which("openssl") or r"C:\Program Files\Git\usr\bin\openssl.exe"
        if not Path(openssl).is_file():
            raise RuntimeError("OpenSSL CLI required to generate isolated test identity")
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        cls.cert, cls.key, cls.server = cls.stack.enter_context(test_identity(Path(openssl)))

    def simulate(self, scenarios=("ok",), events=None, client=None, seconds=8, tap=None):
        timer = VirtualClock()
        logger = quiet if events is None else lambda event, **attrs: events.append((event, attrs))
        platform = Platform(logger, timer.now, timer.pause)
        backend = MockUsb(self.server, platform, scenarios, tap=tap)
        transport = AoaTransport(backend, PORT, platform)
        manager = SessionManager(transport, client or mock_client(self.cert, self.key), platform,
                                 DiagnosticSink(logger), timeout_seconds=0.7,
                                 ping_seconds=0.5, pong_seconds=0.4, tap=tap)
        result = manager.run(len(scenarios), seconds)
        self.assertEqual(manager.state, State.DISCONNECTED)
        self.assertEqual(backend.claimed, backend.closed)
        self.assertFalse(backend.scenarios)
        return result, backend

    def test_encrypted_tap_is_sent_once_and_survives_reconnect(self):
        events = []
        result, backend = self.simulate(("unplug", "ok"), events, seconds=1.2, tap=(44, 440))
        self.assertEqual(result.taps_sent, 1)
        self.assertTrue(result.graceful_shutdown)
        self.assertEqual([kind for kind, _ in backend.touch_reports], ["ACTION_DOWN", "ACTION_UP"])
        self.assertEqual([details for event, details in events if event == "touch_sent"], [{"x": 44, "y": 440}])

    def test_touch_waits_for_authenticated_session(self):
        client = client_context(self.cert, "wrong.local", None, self.cert, self.key)
        result, backend = self.simulate(client=client, tap=(44, 440))
        self.assertEqual(result.taps_sent, 0)
        self.assertEqual(backend.touch_reports, [])

    def test_rejects_out_of_bounds_tap(self):
        with self.assertRaisesRegex(ValueError, "inside 800x480"):
            self.simulate(tap=(800, 0))

    def test_tap_at_center_and_all_four_corners(self):
        for point in ((400, 240), (0, 0), (799, 0), (0, 479), (799, 479)):
            with self.subTest(point=point):
                result, backend = self.simulate(tap=point, seconds=1)
                self.assertEqual(result.errors, [])
                self.assertEqual(result.taps_sent, 1)
                self.assertEqual(len(backend.touch_reports), 2)

    def test_active_session_and_both_media_channels(self):
        events = []
        result, backend = self.simulate(events=events, seconds=1.2)
        states = [row["state"] for event, row in events if event == "state"]
        self.assertEqual(states, ["Disconnected", "DeviceDetected", "Negotiating", "Connected",
                                  "SessionActive", "Disconnected"])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.active_sessions, 1)
        self.assertTrue(result.graceful_shutdown)
        tls, = [fields for event, fields in events if event == "tls_authenticated"]
        self.assertEqual(tls["version"], "TLSv1.2")
        self.assertTrue(tls["cipher"])
        self.assertEqual(backend.media_acks, 2)
        self.assertEqual(backend.peer_pongs, 1)
        self.assertEqual([item[0] for item in backend.requests], [51, 52, 52, 52, 52, 53])
        self.assertEqual(backend.released, 1)
        self.assertTrue(any(a.get("code") == ctrl("PING_REQUEST") and a["direction"] == "out" for _, a in events))

    def test_usb_unplug_and_reconnect(self):
        events = []
        result, backend = self.simulate(("unplug", "ok"), events, seconds=1.2)
        self.assertEqual(result.active_sessions, 2)
        self.assertTrue(result.graceful_shutdown)
        self.assertIn("unplugged", result.errors[0])
        states = [row["state"] for event, row in events if event == "state"]
        self.assertIn("Reconnecting", states)
        self.assertEqual(backend.closed, 2)

    def test_negotiation_and_keepalive_timeouts(self):
        for scenario, match in (("silent", "version deadline"), ("no-pong", "Keepalive response")):
            with self.subTest(scenario=scenario):
                result, _ = self.simulate((scenario,), seconds=2)
                self.assertIn(match, result.errors[0])
                self.assertFalse(result.graceful_shutdown)

    def test_malformed_frame_reconnects_cleanly(self):
        result, _ = self.simulate(("bad-frame", "ok"), seconds=1.2)
        self.assertIn("Invalid frame flags", result.errors[0])
        self.assertTrue(result.graceful_shutdown)

    def test_aoa_reenumeration_timeout_releases_control_handle(self):
        timer = VirtualClock()
        platform = Platform(clock=timer.now, pause=timer.pause)
        backend = MockUsb(self.server, platform, never_reenumerate=True)
        transport = AoaTransport(backend, PORT, platform, reenumerate_seconds=0.5)
        with self.assertRaisesRegex(Timeout, "reenumerate"):
            transport.connect(transport.detect())
        self.assertEqual((backend.released, backend.claimed), (1, 0))

    def test_no_device_on_selected_port_sends_nothing(self):
        clock = VirtualClock()
        platform = Platform(clock=clock.now, pause=clock.pause)
        backend = MockUsb(self.server, platform)
        transport = AoaTransport(backend, "1-99", platform)
        with self.assertRaises(Timeout):
            probe(transport, platform)
        self.assertEqual((backend.requests, backend.claimed), ([], 0))

    def test_aoa_waits_for_driver_after_reenumeration(self):
        class SlowInterfaceUsb(MockUsb):
            open_attempts = 0

            def open_accessory(self, device):
                self.open_attempts += 1
                if self.open_attempts == 1:
                    raise InterfaceNotReady("WinUSB is still starting")
                return super().open_accessory(device)

        timer = VirtualClock()
        platform = Platform(clock=timer.now, pause=timer.pause)
        backend = SlowInterfaceUsb(self.server, platform)
        transport = AoaTransport(backend, PORT, platform)
        self.assertEqual(probe(transport, platform), (1, 7))
        self.assertEqual((backend.open_attempts, backend.released, backend.closed), (2, 1, 1))

    def test_probe_is_not_a_tls_session(self):
        clock = VirtualClock()
        platform = Platform(clock=clock.now, pause=clock.pause)
        backend = MockUsb(self.server, platform)
        version = probe(AoaTransport(backend, PORT, platform), platform)
        self.assertEqual(version, (1, 7))
        self.assertEqual((backend.claimed, backend.closed, backend.media_acks), (1, 1, 0))

    def test_bad_certificate_pin_and_name_fail_closed(self):
        for client, message in (
                (client_context(self.cert, None, "00" * 32, self.cert, self.key), "fingerprint does not match"),
                (client_context(self.cert, "wrong.local", None, self.cert, self.key),
                 r"peer certificate verification failed \(\d+\): .*mismatch")):
            result, _ = self.simulate(client=client)
            self.assertEqual(result.active_sessions, 0)
            self.assertRegex(result.errors[0], message)

    def test_repeated_sessions_release_python_allocations(self):
        identity = mock_client(self.cert, self.key)
        for _ in range(3):
            self.simulate(client=identity, seconds=1)
        tracemalloc.start()
        try:
            for _ in range(5):
                self.simulate(client=identity, seconds=1)
            gc.collect()
            baseline = tracemalloc.get_traced_memory()[0]
            for _ in range(35):
                self.simulate(client=identity, seconds=1)
            gc.collect()
            retained, peak = tracemalloc.get_traced_memory()
            self.assertLess(retained - baseline, 128 * 1024)
            self.assertLess(peak, 4 * 1024 * 1024)
        finally:
            tracemalloc.stop()

    def test_packaged_cli_timeout_exit_code(self):
        build = Path(__file__).resolve().parents[1] / "build/i30-receiver.pyz"
        if not build.is_file():
            self.skipTest("Build the zipapp first to test its entry point")
        run = subprocess.run([sys.executable, str(build), "mock", "--scenario", "no-pong"],
                             capture_output=True, text=True, timeout=25)
        self.assertEqual(run.returncode, 1, run.stderr)
        report = json.loads(run.stdout.splitlines()[-1])
        self.assertEqual(report["source"], "mock")
        self.assertEqual(report["errors"], ["Keepalive response deadline expired"])


if __name__ == "__main__":
    unittest.main()
