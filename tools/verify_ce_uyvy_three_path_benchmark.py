"""Compare BGRA/GDI, UYVY staging + GDI, and UYVY DirectDraw in ARM fixture.

All timings are ARM Unicorn wall-clock milliseconds with Python API doubles and
one identical H.264 frame per run. They are not real head-unit surface timings,
LCD output, FPS, ACK gaps, or camera-priority evidence.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from statistics import median

try:
    from emulate_ce_usb import DdrawDoubleMixin
    from verify_ce_uyvy_staging import PITCH, PADDING, StagingProbe, sample
except ModuleNotFoundError:  # Imported as tools.verify_ce_uyvy_three_path_benchmark.
    from tools.emulate_ce_usb import DdrawDoubleMixin
    from tools.verify_ce_uyvy_staging import PITCH, PADDING, StagingProbe, sample


class DdrawProbe(DdrawDoubleMixin, StagingProbe):
    """Run the opt-in ARM probe against a CE6 DirectDraw COM double."""

    def __init__(self, path, stream, *, mode=None, flip=False, capture=True):
        super().__init__(path, stream)
        self.install_ddraw_double(flip=flip, mode=mode, capture=capture)


def describe(path):
    data = path.read_bytes()
    report = json.loads(path.with_name('abi.json').read_text(encoding='utf-8'))
    return {
        'path': str(path),
        'sha256': sha256(data).hexdigest(),
        'abi': {key: report.get(key) for key in
                ('video_probe_format', 'ddraw_flip', 'video_probe_rvas')},
    }


def check_ddraw_bytes(probe, width, height):
    row = bytes((90, 81, 240, 81)) * (width // 2)
    expected = row + bytes([PADDING]) * (PITCH - len(row))
    assert probe.ddraw['frame'] is not None
    assert probe.ddraw['frame'] == expected * 2, 'packed UYVY rows differ from fixture expectation'
    assert not probe.blits, 'DirectDraw success must not use the GDI blit fallback'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bgra', type=Path, required=True)
    parser.add_argument('--staging', type=Path, required=True)
    parser.add_argument('--ddraw', type=Path, required=True)
    parser.add_argument('--ddraw-flip', type=Path, help='Optional flip-enabled ddraw probe')
    parser.add_argument('--runs', type=int, default=5)
    parser.add_argument('--output', type=Path, help='Write the JSON report here')
    args = parser.parse_args()
    if args.runs < 1:
        parser.error('--runs must be positive')

    stream = sample(800, 480)
    modes = {
        'bgra_gdi': (args.bgra, ('i30_video_push', 'h264bsdConvertToBGRA')),
        'uyvy_staging_bgra_gdi': (args.staging, ('i30_video_push', 'stage_uyvy')),
        'uyvy_ddraw': (args.ddraw, ('i30_video_push', 'i30_ddraw_present')),
    }
    if args.ddraw_flip:
        modes['uyvy_ddraw_flip'] = (args.ddraw_flip, ('i30_video_push', 'i30_ddraw_present'))

    results = {name: [] for name in modes}
    for _ in range(args.runs):
        for name, (path, functions) in modes.items():
            if name == 'uyvy_ddraw_flip':
                probe = DdrawProbe(path, stream, flip=True)
            elif name == 'uyvy_ddraw':
                probe = DdrawProbe(path, stream)
            else:
                probe = StagingProbe(path, stream)
            sample_result = probe.measure(path, functions)
            assert probe.status == 0 and not probe.allocations and probe.live_bytes == 0
            if name == 'bgra_gdi':
                assert len(probe.blits) == 1 and probe.blits[0][0] == (40, 800, -480, 1, 32)
            elif name == 'uyvy_staging_bgra_gdi':
                assert not probe.blits and probe.surface is not None
                row = bytes((90, 81, 240, 81)) * 400
                expected = row + bytes([PADDING]) * (PITCH - len(row))
                assert probe.surface == expected * 480
            else:
                check_ddraw_bytes(probe, 800, 480)
                assert probe.ddraw['shows'] == 1
                assert probe.ddraw['locks'] == probe.ddraw['unlocks'] == 1
                assert probe.ddraw['cooperative'] == [(1, 0)]
                assert probe.ddraw['overlay_caps'] == (0x80000005 if name == 'uyvy_ddraw_flip' else 0x80000004)
                assert all(count == 0 for count in probe.ddraw['refs'].values()), probe.ddraw['refs']
                assert probe.ddraw['loads'] == ['DDRAW.dll']
                assert probe.ddraw['frees'] == 1
                if name == 'uyvy_ddraw_flip':
                    assert probe.ddraw['flips'] == 1 and probe.ddraw['flip_status'] == 1
            results[name].append(sample_result)

    medians = {name: {key: round(median(row[key] for row in runs), 3) for key in runs[0]}
               for name, runs in results.items()}
    report = {
        'scope': 'ARM Unicorn fixture wall milliseconds; API/COM doubles; one identical 800x480 H.264 frame per run',
        'fixture': {'codec': 'libx264 yuv420p ultrafast zerolatency baseline',
                    'pixel_values': {'Y': 81, 'U': 90, 'V': 240}, 'pitch': PITCH,
                    'runs': args.runs},
        'artifacts': {name: describe(path) for name, (path, _) in modes.items()},
        'median': medians,
        'runs': results,
        'labels': {
            'VERIFIED': 'Local fixture bytes, Unicorn wall-clock timings and mock call counts.',
            'INFERRED': 'The three candidate code paths are selectable at build time and share the same decoder.',
            'UNKNOWN': 'Real DDRAW caps, UYVY surface support, LCD output, flip completion, camera priority, FPS and USB ACK gaps.',
        },
    }
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(text + '\n', encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
