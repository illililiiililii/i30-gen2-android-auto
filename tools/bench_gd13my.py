"""Run the stock GD13MY windowed boot headlessly and report stage timings.

This keeps the exact WindowedRun/boot path used by view_gd13my.py (stock DiskA
overlay, touch calibration, software OpenGL map renderer) but drives it without
Tk so boot benchmarks and automated retries do not need a desktop window.
"""

import argparse
from contextlib import closing as close_file
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime
import json
from math import isfinite
from pathlib import Path
from queue import Empty, SimpleQueue
import sqlite3
import sys
from threading import Event, Thread
from time import monotonic

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from view_gd13my import boot  # noqa: E402

SERIAL_MARKERS = (
    (b'Windows CE Kernel for ARM', 'kernel_entry'),
    (b'Run Touch_Calib.EXE', 'touch_calibration_start'),
    (b'Calib file write BuffLen', 'touch_calibration_done'),
    (b'Complete register process -- PATH_Av', 'av_registered'),
    (b'MAIN mode ACK', 'navigation_ack'),
    (b'i30 USB attach ready', 'usb_attach_ready'),
)
SERIAL_OVERLAP = max(len(marker) for marker, _ in SERIAL_MARKERS) - 1


class ProcessIoCounters(C.Structure):
    _fields_ = [(name, C.c_ulonglong) for name in
                ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]


class ProcessMemoryCounters(C.Structure):
    _fields_ = [('cb', W.DWORD), ('PageFaultCount', W.DWORD),
                ('PeakWorkingSetSize', C.c_size_t), ('WorkingSetSize', C.c_size_t),
                ('QuotaPeakPagedPoolUsage', C.c_size_t), ('QuotaPagedPoolUsage', C.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', C.c_size_t), ('QuotaNonPagedPoolUsage', C.c_size_t),
                ('PagefileUsage', C.c_size_t), ('PeakPagefileUsage', C.c_size_t)]


class ProcessSampler:
    """Read this process's CPU, working set and I/O counters through Win32."""

    def __init__(self):
        self.kernel32 = C.WinDLL('kernel32', use_last_error=True)
        self.psapi = C.WinDLL('psapi', use_last_error=True)
        self.kernel32.GetCurrentProcess.restype = W.HANDLE
        self.handle = self.kernel32.GetCurrentProcess()
        self.kernel32.GetProcessTimes.argtypes = (W.HANDLE, C.POINTER(W.FILETIME), C.POINTER(W.FILETIME),
                                                  C.POINTER(W.FILETIME), C.POINTER(W.FILETIME))
        self.kernel32.GetProcessIoCounters.argtypes = (W.HANDLE, C.POINTER(ProcessIoCounters))
        self.psapi.GetProcessMemoryInfo.argtypes = (W.HANDLE, C.POINTER(ProcessMemoryCounters), W.DWORD)
        self.last = self.sample()

    def sample(self):
        creation, exit_, kernel, user = (W.FILETIME() for _ in range(4))
        if not self.kernel32.GetProcessTimes(self.handle, C.byref(creation), C.byref(exit_),
                                             C.byref(kernel), C.byref(user)):
            raise C.WinError(C.get_last_error())
        cpu = ((kernel.dwHighDateTime << 32) | kernel.dwLowDateTime) / 1e7
        cpu += ((user.dwHighDateTime << 32) | user.dwLowDateTime) / 1e7
        counters = ProcessIoCounters()
        if not self.kernel32.GetProcessIoCounters(self.handle, C.byref(counters)):
            raise C.WinError(C.get_last_error())
        memory = ProcessMemoryCounters()
        memory.cb = C.sizeof(ProcessMemoryCounters)
        if not self.psapi.GetProcessMemoryInfo(self.handle, C.byref(memory), C.sizeof(memory)):
            raise C.WinError(C.get_last_error())
        return {'cpu_seconds': cpu, 'read_bytes': counters.ReadTransferCount,
                'write_bytes': counters.WriteTransferCount,
                'working_set': memory.WorkingSetSize, 'peak_working_set': memory.PeakWorkingSetSize}


def tail_markers(path, offset, found):
    """Return newly completed serial markers and the new scan offset."""
    try:
        with path.open('rb') as serial:
            start = max(0, offset - SERIAL_OVERLAP)
            serial.seek(start)
            data = serial.read()
    except FileNotFoundError:
        return offset
    if start + len(data) <= offset:
        return offset
    for marker, name in SERIAL_MARKERS:
        if name not in found and marker in data:
            found[name] = monotonic()
    return start + len(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True, help='Extracted GD13MY kernel BIN')
    parser.add_argument('--disk', type=Path, required=True, help='Full media image')
    parser.add_argument('--app-volume', type=Path, required=True, help='Compact DiskA overlay image')
    parser.add_argument('--software-gl-app', type=Path, required=True, help='Extracted GDdNavi.exe')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--state', type=Path, help='DiskA state database to copy for this run')
    parser.add_argument('--route-input', type=Path,
                        help='JSON array of [seconds after navigation ready, x, y, pressed] pointer events')
    parser.add_argument('--host-utc-offset', type=int)
    parser.add_argument('--guest-clock-mhz', type=float, default=4.5)
    parser.add_argument('--usb-clock-mhz', type=float, default=12.0)
    parser.add_argument('--seconds', type=int, default=1800)
    parser.add_argument('--stop-after-ready', type=float, default=2.0,
                        help='Wall seconds to keep running after navigation_ready')
    parser.add_argument('--ready-timeout', type=float, default=1800.0,
                        help='Wall seconds before the benchmark gives up waiting for navigation_ready')
    parser.add_argument('--micom-display', choices=('av', 'navi'), default='navi')
    parser.add_argument('--boot-trace', action='store_true')
    parser.add_argument('--no-auto-calibrate', action='store_true')
    parser.add_argument('--save-output', action='store_true', help='Keep the emulator JSON and logs')
    parser.add_argument('--sustain', action='store_true',
                        help='Record 10-second windows at ready and at 1, 3 and 5 minutes')
    args = parser.parse_args()
    if args.sustain:
        args.stop_after_ready = max(args.stop_after_ready, 305)
    route_input = []
    if args.route_input is not None:
        try:
            route_input = json.loads(args.route_input.read_text(encoding='utf-8'))
            if not isinstance(route_input, list):
                raise ValueError('expected an array')
            last_at = 0
            for at, x, y, pressed in route_input:
                if (type(at) not in (int, float) or not isfinite(at)
                        or not last_at <= at < args.stop_after_ready
                        or type(x) is not int or not 0 <= x < 800
                        or type(y) is not int or not 0 <= y < 480 or type(pressed) is not bool):
                    raise ValueError('invalid timing, coordinates or pressed state')
                last_at = at
        except (OSError, OverflowError, TypeError, ValueError) as error:
            parser.error(f'--route-input: {error}')

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    output = args.output_dir / f'bench-{stamp}-guest'
    state = args.output_dir / f'bench-{stamp}.sqlite3'
    if args.state is not None:
        source_uri = args.state.resolve().as_uri() + '?mode=ro'
        with close_file(sqlite3.connect(source_uri, uri=True)) as source, close_file(sqlite3.connect(state)) as copy:
            source.backup(copy)

    messages, pointer, panel = SimpleQueue(), SimpleQueue(), SimpleQueue()
    menu_button, closing = Event(), Event()
    boot_clock_units = round(args.guest_clock_mhz * 1_000_000)
    usb_clock_units = round(args.usb_clock_mhz * 1_000_000)
    thread = Thread(target=boot, args=(
        args.image, args.disk, args.seconds, messages, pointer, menu_button, closing, output,
        None, 2 if args.micom_display == 'navi' else 3, args.software_gl_app, True, True,
        args.app_volume, None, None, panel), kwargs={
            'state_path': state, 'usb_on_test': False, 'projection': None,
            'auto_calibrate': not args.no_auto_calibrate, 'boot_trace': args.boot_trace,
            'show_map_preview': False, 'host_utc_offset': args.host_utc_offset,
            'boot_clock_units': boot_clock_units, 'usb_clock_units': usb_clock_units,
            'sample_performance': args.sustain},
        daemon=True)
    started = monotonic()
    sampler = ProcessSampler()
    events = {}
    serial_path = output.with_suffix('.serial.log')
    serial_offset = 0
    markers = {}
    ready_at = None
    route_event = 0
    lcd_frames = 0
    first_lcd_after_ready = previous_lcd = None
    longest_lcd_gap = 0.0
    stop_reason = None
    shutdown_at = None
    samples = []
    checkpoints = iter((10, 60, 180, 300))
    checkpoint = next(checkpoints)
    sustained = []
    thread.start()
    while True:
        try:
            kind, payload = messages.get(timeout=0.1)
        except Empty:
            kind = payload = None
        now = monotonic()
        if kind is not None:
            events.setdefault(kind, round(now - started, 3))
            if kind == 'error' or (kind == 'stopped' and payload != 'guest_stopped'):
                stop_reason = f'{kind}:{payload}'
            elif kind == 'navigation_ready' and ready_at is None:
                ready_at = now
            elif kind == 'performance' and ready_at is not None and checkpoint is not None:
                at = now - ready_at
                samples.append((at, payload | sampler.sample()))
                while len(samples) > 1 and samples[1][0] <= at - 10:
                    samples.pop(0)
                if at >= checkpoint:
                    first_at, first = samples[0]
                    last_at, last = samples[-1]
                    record = {'checkpoint_seconds': checkpoint, 'window_seconds': round(last_at - first_at, 3),
                              'working_set_mb': round(last['working_set'] / 1048576, 2),
                              'queued_events': messages.qsize(),
                              'delta': {k: round(last[k] - first[k], 4)
                                        for k in last if k not in ('working_set', 'peak_working_set')}}
                    sustained.append(record)
                    with output.with_suffix('.sustain.jsonl').open('a', encoding='utf-8') as log:
                        print(json.dumps(record), file=log)
                    checkpoint = next(checkpoints, None)
            elif kind == 'frame' and ready_at is not None:
                lcd_frames += 1
                if first_lcd_after_ready is None:
                    first_lcd_after_ready = now
                if previous_lcd is not None:
                    longest_lcd_gap = max(longest_lcd_gap, now - previous_lcd)
                previous_lcd = now
        serial_offset = tail_markers(serial_path, serial_offset, markers)
        elapsed = now - started
        while ready_at is not None and route_event < len(route_input) and not closing.is_set():
            at, x, y, pressed = route_input[route_event]
            if now - ready_at < at:
                break
            pointer.put((x, y, pressed))
            route_event += 1
        if ready_at is not None and now - ready_at >= args.stop_after_ready and not closing.is_set():
            closing.set()
        if not thread.is_alive():
            break
        if elapsed >= args.ready_timeout and ready_at is None and not closing.is_set():
            stop_reason = stop_reason or 'ready_timeout'
            closing.set()
        if elapsed >= args.seconds + 5 and not closing.is_set():
            stop_reason = stop_reason or 'harness_limit'
            closing.set()
        if closing.is_set():
            shutdown_at = now if shutdown_at is None else shutdown_at
            if now - shutdown_at >= 30:
                stop_reason = stop_reason or 'worker_shutdown_timeout'
                break
    wall = monotonic() - started
    final = sampler.sample()

    report = {}
    try:
        report = json.loads(output.with_suffix('.json').read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError) as error:
        stop_reason = stop_reason or f'missing_report:{error}'
    boot_timings = report.get('wall_seconds_from_guest_init') or {}
    stop_context = report.get('stop_context') or {}
    ticks = stop_context.get('clock_ticks') or 0
    guest_seconds = ticks / 32768
    ready_ticks = report.get('ready_clock_ticks')
    ready_guest_seconds = (ticks - ready_ticks) / 32768 if ready_ticks is not None else None
    ready_wall_seconds = started + wall - ready_at if ready_at is not None else None
    summary = {
        'wall_seconds': round(wall, 3),
        'first_lcd_frame': boot_timings.get('first_lcd_frame'),
        'navigation_ready': boot_timings.get('navigation_ready'),
        'navigation_ready_wall': round(ready_at - started, 3) if ready_at else None,
        'guest_seconds': round(guest_seconds, 1),
        'guest_clock_munits_per_wall_second': round(guest_seconds * boot_clock_units / wall / 1e6, 2),
        'timer': report.get('timer'),
        'stock_map': report.get('stock_map'),
        'sustained_navigation': sustained,
        'lcd_capture': report.get('lcd_capture'),
        'lcd_blits': report.get('lcd_blits'),
        'ready_guest_seconds': round(ready_guest_seconds, 3) if ready_guest_seconds is not None else None,
        'ready_guest_seconds_per_wall_second': (round(ready_guest_seconds / ready_wall_seconds, 3)
                                                if ready_guest_seconds is not None and ready_wall_seconds else None),
        'route_inputs_sent': route_event,
        'lcd_after_ready': {
            'changed_frames': lcd_frames,
            'changed_frames_per_wall_second': round(lcd_frames / ready_wall_seconds, 3) if ready_wall_seconds else None,
            'first_to_last_seconds': (round(previous_lcd - first_lcd_after_ready, 4)
                                      if lcd_frames else None),
            'longest_gap_seconds': round(longest_lcd_gap, 4) if lcd_frames > 1 else None,
        },
        'cpu_seconds': round(final['cpu_seconds'] - sampler.last['cpu_seconds'], 2),
        'cpu_percent': round((final['cpu_seconds'] - sampler.last['cpu_seconds']) / wall * 100, 1),
        'peak_working_set_mb': round(final['peak_working_set'] / 1048576, 1),
        'read_mb': round((final['read_bytes'] - sampler.last['read_bytes']) / 1048576, 1),
        'write_mb': round((final['write_bytes'] - sampler.last['write_bytes']) / 1048576, 1),
        'stop': report.get('stop'),
        'stop_reason': stop_reason,
        'events': events,
        'serial_markers': {name: round(at - started, 3) for name, at in markers.items()},
        'timer_irqs': report.get('timer_irqs'),
        'idle_wakes': report.get('idle_wakes'),
        'mmio': {name: values for name, values in (report.get('mmio_devices') or {}).items()
                 if values['reads'] + values['writes'] > 1000},
        'output': str(output),
    }
    (args.output_dir / f'bench-{stamp}.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    if not args.save_output and not thread.is_alive():
        for suffix in ('.serial.log', '.png', '.gles.log', '.mode.log', '.recalibration.log'):
            path = output.with_suffix(suffix)
            if path.exists():
                path.unlink()
    return 0 if ready_at is not None and report.get('stop') == 'guest_stopped' else 1


if __name__ == '__main__':
    sys.exit(main())
