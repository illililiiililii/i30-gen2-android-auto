"""Summarize repeated ARM AARE video benchmark JSON produced by emulate_ce_usb.py."""

import argparse
import json
from pathlib import Path
import statistics


def load(path):
    with path.open(encoding='utf-16') as stream:
        return json.load(stream)['continuous_video']


def summarize(paths):
    runs = [load(path) for path in paths]
    rows = []
    for index, run in enumerate(runs, 1):
        profile = run['arm_function_wall_profile']
        row = {
            'run': index,
            'frames': run['painted'],
            'acked': run['acked'],
            'decode_ms': statistics.median(frame['decode_ms'] for frame in profile),
            'bgra_conversion_ms': statistics.median(frame['bgra_conversion_ms'] for frame in profile),
            'rgb565_conversion_ms': statistics.median(frame['rgb565_conversion_ms'] for frame in profile),
            'video_push_ms': statistics.median(frame['video_push_ms'] for frame in profile),
            'gdi_blit_ms': statistics.median(run['gdi_blit_wall_ms']),
            'frame_gap_ms': statistics.median(run['frame_ack_wall_ms']),
            'wall_seconds': run['wall_seconds'],
            'peak_guest_bytes': run['peak_guest_requested_bytes'],
            'live_allocations': run['live_allocations_after_close'],
        }
        rows.append(row)
    summary = {'runs': rows}
    for key in ('decode_ms', 'bgra_conversion_ms', 'rgb565_conversion_ms', 'video_push_ms',
                'gdi_blit_ms', 'frame_gap_ms', 'wall_seconds', 'peak_guest_bytes'):
        summary['median_' + key] = statistics.median(row[key] for row in rows)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prefix', help='Common prefix, e.g. build/aare-bgra-bench')
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--start', type=int, default=1)
    args = parser.parse_args()
    base = Path(args.prefix)
    paths = [base.parent / f'{base.name}{index}.json'
             for index in range(args.start, args.start + args.runs)]
    print(json.dumps(summarize(paths), indent=2))


if __name__ == '__main__':
    main()
