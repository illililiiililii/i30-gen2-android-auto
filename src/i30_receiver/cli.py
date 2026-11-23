"""PC diagnostic entry point. USB activation requires an explicit device and trust."""

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
from threading import Event

from . import __version__
from .audio import AudioMixer, Microphone, samples
from .integration import ProjectionHost
from .mock import (MockCapture, MockPlayback, MockStockUi, MockUsb, PORT, VirtualClock,
                   mock_client, synthetic_h264, test_identity)
from .platform import DiagnosticSink, Platform
from .probe import probe
from .protocol import validate_tap
from .session import SessionManager
from .tls import client_context
from .transport import AccessoryIdentity, AoaTransport, TransportError
from .usb_pc import PyUsb
from .video import VideoPreviewSink
from .wire import ProtocolError


def libusb_path():
    local = os.environ.get("LOCALAPPDATA")
    if local is None:
        return None
    candidate = Path(local) / "i30-phase2-tools/libusb/VS2022/MS64/dll/libusb-1.0.dll"
    return candidate if candidate.is_file() else None


def openssl_path():
    found = shutil.which("openssl")
    if found:
        return Path(found)
    candidate = Path(r"C:\Program Files\Git\usr\bin\openssl.exe")
    return candidate if candidate.is_file() else None


def options():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--log", type=Path, help="Also write a new JSON Lines log file")
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="List USB VID/PID and physical ports without sending AOA requests")
    listing.add_argument("--libusb", type=Path, default=libusb_path())
    sub.add_parser("audio-devices", help="List desktop WinMM input and output devices")
    mock = sub.add_parser("mock", help="Run the local TLS and synthetic AOA integration test")
    mock.add_argument("--openssl", type=Path, default=openssl_path())
    mock.add_argument("--scenario", choices=("ok", "unplug", "silent", "no-pong", "bad-frame"), default="ok")
    mock.add_argument("--reconnect", action="store_true", help="Try a healthy peer after the first scenario")
    mock.add_argument("--tap", type=int, nargs=2, metavar=("X", "Y"), help="Verify one synthetic 800x480 tap")
    mock.add_argument("--phase3", action="store_true", help="Verify buttons, playback, microphone and stock UI recovery")
    physical = argparse.ArgumentParser(add_help=False)
    physical.add_argument("--device", required=True, metavar="BUS-PORT")
    physical.add_argument("--libusb", type=Path, default=libusb_path())
    physical.add_argument("--manufacturer", default=AccessoryIdentity.manufacturer)
    physical.add_argument("--model", default=AccessoryIdentity.model)
    sub.add_parser("probe", parents=[physical], help="Test AOA and the unencrypted version exchange")
    live = sub.add_parser("connect", parents=[physical], help="Run a verified TLS session on a selected USB port")
    live.add_argument("--ca", required=True, type=Path, help="Trusted enrolled peer CA or certificate")
    peer = live.add_mutually_exclusive_group(required=True)
    peer.add_argument("--peer-name")
    peer.add_argument("--peer-sha256")
    live.add_argument("--cert", type=Path, help="Enrolled head-unit certificate, if required")
    live.add_argument("--key", type=Path, help="Private key for the enrolled head-unit certificate")
    live.add_argument("--attempts", type=int, default=1)
    live.add_argument("--seconds", type=float, default=20)
    live.add_argument("--tap", type=int, nargs=2, metavar=("X", "Y"),
                      help="Send one 800x480 tap after TLS and touch binding")
    live.add_argument("--audio-out", type=int, metavar="DEVICE", help="Play projection PCM on this WinMM device")
    live.add_argument("--mic-in", type=int, metavar="DEVICE", help="Offer microphone capture on this WinMM device")
    live.add_argument("--volume", type=float, default=1.0, help="Projection playback gain from 0 to 1")
    live.add_argument("--display", action="store_true", help="Open a PC projection window with touch and buttons (requires PyAV and Tk)")
    for command in (mock, live):
        command.add_argument("--video-preview", type=Path, metavar="PNG",
                             help="Decode H.264 and save the first frame to a new PNG (requires PyAV)")
    return parser.parse_args()


def main():
    args = options()
    with ExitStack() as stack:
        try:
            log_file = stack.enter_context(args.log.open("x", encoding="utf-8")) if args.log else None
        except OSError as exc:
            print(json.dumps({"event": "error", "message": f"Cannot create log: {exc}"}), flush=True)
            return 1

        def log(event, **fields):
            source = {'mock': 'mock', 'audio-devices': 'pc'}.get(args.command, 'usb')
            line = json.dumps({"time": datetime.now(timezone.utc).isoformat(),
                               "source": source,
                               "event": event, **fields}, ensure_ascii=True)
            print(line, flush=True)
            if log_file:
                log_file.write(line + "\n")
                log_file.flush()

        try:
            tap = getattr(args, "tap", None)
            if tap is not None:
                validate_tap(*tap)
            if args.command == "audio-devices":
                require_windows_audio()
                from .audio_win import wave_devices
                for device in wave_devices():
                    log("audio_device", **device)
                return 0
            if args.command == "list":
                devices = PyUsb(args.libusb).devices()
                for device in devices:
                    log("usb_device", port=device.port, address=device.address,
                        vid=f"{device.vendor:04x}", pid=f"{device.product:04x}",
                        accessory=device.accessory, mass_storage_device_class=device.mass_storage)
                log("summary", mode="enumeration", devices=len(devices),
                    accessory_devices=sum(d.accessory for d in devices), sessions_attempted=0)
                return 0
            preview = getattr(args, "video_preview", None)
            display = getattr(args, "display", False)
            if preview and display:
                raise ValueError('Choose either --video-preview or --display')
            host = audio = microphone = poll_ui = None
            av = None
            sink = DiagnosticSink(log)
            if preview is not None:
                if preview.exists() or not preview.parent.is_dir():
                    raise ValueError("Choose a new PNG path in an existing directory")
                import av
                sink = VideoPreviewSink(log, av, preview)
            if args.command == "mock":
                if not args.openssl:
                    raise ValueError("OpenSSL CLI is required to generate a temporary mock certificate")
                cert, key, server = stack.enter_context(test_identity(args.openssl))
                platform = Platform(log, (clock := VirtualClock()).now, clock.pause)
                scenarios = (args.scenario, "ok") if args.reconnect else (args.scenario,)
                video_packets = ()
                if av is not None:
                    try:
                        video_packets = synthetic_h264(av)
                    except (ValueError, av.FFmpegError) as exc:
                        raise ValueError(f"Cannot prepare the mock H.264 stream: {exc}") from exc
                backend = MockUsb(server, platform, scenarios, tap=tap, video_packets=video_packets, phase3=args.phase3)
                transport = AoaTransport(backend, PORT, platform)
                tls_factory = mock_client(cert, key)
                attempts, seconds = len(scenarios), 12.0
                if args.phase3:
                    ui, output, capture = MockStockUi(), MockPlayback(), MockCapture(platform.clock)
                    host = ProjectionHost(ui)
                    audio = AudioMixer(output)
                    microphone = Microphone(capture)
                    tested = None

                    def poll_ui():
                        nonlocal tested
                        session = host.session
                        if host.visible and session.bound_keys and session is not tested:
                            tested = session
                            host.button('SEEK_NEXT', True)
                            host.button('SEEK_NEXT', False)
                            host.button('VOICE', True)
                            host.button('VOICE', False)
                        if ui.projected and backend.mic_closed and session is tested and not ui.buttons:
                            host.preempt('reverse_camera', True)
                            host.button('SEEK_NEXT', True)
                            host.button('SEEK_NEXT', False)
                            host.preempt('reverse_camera', False)
            else:
                if not re.fullmatch(r"\d+-\d+(?:\.\d+)*", args.device):
                    raise ValueError("Use a physical port as reported by the list command")
                stop = Event()
                signal.signal(signal.SIGINT, lambda *_: stop.set())
                platform = Platform(log, stop_requested=stop.is_set)
                identity = AccessoryIdentity(manufacturer=args.manufacturer, model=args.model)
                transport = AoaTransport(PyUsb(args.libusb), args.device, platform, identity)
                if args.command == "probe":
                    major, minor = probe(transport, platform)
                    log("summary", mode="version_probe", version=f"{major}.{minor}", active_sessions=0)
                    return 0
                tls_factory = client_context(args.ca, args.peer_name, args.peer_sha256, args.cert, args.key)
                attempts, seconds = args.attempts, args.seconds
                if args.audio_out is not None or args.mic_in is not None:
                    require_windows_audio()
                    from .audio_win import WaveCapture, WavePlayback
                    if args.audio_out is not None:
                        audio = AudioMixer(WavePlayback(args.audio_out), args.volume)
                    if args.mic_in is not None:
                        microphone = Microphone(WaveCapture(args.mic_in))
                if display:
                    import av
                    from tkinter import TclError
                    from .display_pc import ProjectionWindow
                    try:
                        sink = ProjectionWindow(log, av, stop.set)
                    except TclError as exc:
                        raise ValueError(f'Could not open PC projection window: {exc}') from exc
                    stack.callback(sink.root.destroy)
                    host = sink.host = ProjectionHost(sink)
                    poll_ui = sink.poll
            manager = SessionManager(transport, tls_factory, platform, sink, tap=tap,
                                     host=host, audio=audio, microphone=microphone, poll_ui=poll_ui,
                                     touch_input=display)
            result = manager.run(attempts=attempts, seconds=seconds)
            detail = result.as_dict()
            if args.command == "mock":
                detail.update(mock_links_closed=backend.closed, mock_media_acks=backend.media_acks,
                              mock_peer_pongs=backend.peer_pongs, mock_touch_reports=len(backend.touch_reports))
            phase3_complete = True
            if args.command == "mock" and args.phase3:
                mixed = bool(output.last) and all(sample == 4000 for sample in samples(output.last))
                phase3_complete = bool(backend.key_reports and backend.mic_closed and mixed and ui.restored
                                       and capture.closed and output.closed and ui.buttons and not ui.projected)
                detail.update(mock_key_reports=len(backend.key_reports), mock_mic_blocks=backend.mic_blocks,
                              mock_mic_stops=backend.mic_closed, mock_capture_releases=capture.closed,
                              mock_audio_blocks=audio.blocks_written, mock_audio_mixed=mixed,
                              mock_playback_releases=output.closed, mock_ui_restores=ui.restored,
                              mock_oem_button_events=len(ui.buttons))
                if not phase3_complete:
                    detail["errors"].append("Requested Phase 3 integration checks did not complete")
            if tap is not None and not result.taps_sent:
                detail["errors"].append("Requested tap did not complete")
            if preview is not None:
                detail.update(decoded_video_frames=sink.total_frames, video_preview_written=sink.preview_written)
                if not sink.preview_written:
                    detail["errors"].append("Requested video preview was not produced")
            log("summary", **detail)
            tap_complete = tap is None or result.taps_sent == 1
            video_complete = preview is None or sink.preview_written
            return 0 if result.active_sessions and result.graceful_shutdown and tap_complete and video_complete and phase3_complete else 1
        except (ImportError, OSError, ValueError, subprocess.SubprocessError, TransportError, ProtocolError) as exc:
            log("error", message=str(exc))
            return 1


def require_windows_audio():
    if os.name != 'nt':
        raise ValueError('Audio playback and capture require desktop Windows')


if __name__ == "__main__":
    raise SystemExit(main())
