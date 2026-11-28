"""Compare a decoded AARE frame with the final LCD image.

The tool does no scaling or coordinate guessing: callers supply the crop and
shift explicitly. Inputs may be PNG/RGB24 or raw planar I420. Outputs are an
aligned source PNG and an amplified absolute-difference PNG, plus MAE/RMSE.
"""

import argparse
from collections import OrderedDict
import json
import math
from pathlib import Path
import sys

import av

from gd13my_display import png

DEFAULT_SIZE = (800, 480)


def parse_size(value):
    try:
        width, height = (int(part) for part in value.lower().split('x'))
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError('Expected WIDTHxHEIGHT') from error
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError('Dimensions must be positive')
    return width, height


def parse_rect(value):
    try:
        left, top, width, height = (int(part) for part in value.split(','))
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError('Expected LEFT,TOP,WIDTH,HEIGHT') from error
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError('Rectangle dimensions must be positive')
    return left, top, width, height


def _detect(path, explicit, raw_suffixes):
    if explicit and explicit != 'auto':
        return explicit
    suffix = path.suffix.lower().lstrip('.')
    if suffix in raw_suffixes:
        return raw_suffixes[suffix]
    return 'png'


def packed_rgb(frame):
    """Copy a decoded frame into tightly packed top-down RGB888 bytes."""
    plane = frame.reformat(format='rgb24').planes[0]
    raw = memoryview(plane)
    row_bytes = frame.width * 3
    pitch = plane.line_size
    return b''.join(bytes(raw[row * pitch:row * pitch + row_bytes]) for row in range(frame.height))


def decode_image(path):
    with av.open(str(path)) as container:
        frame = next(container.decode(video=0), None)
    if frame is None:
        raise ValueError(f'No decodable image in {path}')
    return frame


def load_rgb(path, size, file_format='auto', raw_formats=('rgb24',)):
    """Return (width, height, packed RGB888) from a PNG or raw RGB/I420 file."""
    path = Path(path)
    kind = _detect(path, file_format, {'rgb': 'rgb24', 'rgb24': 'rgb24', 'raw': 'rgb24'})
    if kind == 'rgb24':
        width, height = size
        data = path.read_bytes()
        expected = width * height * 3
        if len(data) != expected:
            raise ValueError(f'{path}: expected {expected} RGB24 bytes, got {len(data)}')
        return width, height, data
    if kind in ('i420', 'yuv420p'):
        width, height = size
        if width % 2 or height % 2:
            raise ValueError('I420 requires even dimensions')
        data = path.read_bytes()
        expected = width * height * 3 // 2
        if len(data) != expected:
            raise ValueError(f'{path}: expected {expected} I420 bytes, got {len(data)}')
        frame = av.VideoFrame(width, height, 'yuv420p')
        luma = width * height
        chroma = luma // 4

        def padded(plane, bytes_per_row, rows, payload):
            pitch = plane.line_size
            if pitch < bytes_per_row:
                raise ValueError('PyAV plane pitch is smaller than the I420 row')
            return b''.join(payload[row * bytes_per_row:(row + 1) * bytes_per_row] +
                            bytes(pitch - bytes_per_row) for row in range(rows))

        frame.planes[0].update(padded(frame.planes[0], width, height, data[:luma]))
        frame.planes[1].update(padded(frame.planes[1], width // 2, height // 2,
                                      data[luma:luma + chroma]))
        frame.planes[2].update(padded(frame.planes[2], width // 2, height // 2,
                                      data[luma + chroma:]))
        return width, height, packed_rgb(frame)
    if kind != 'png':
        raise ValueError(f'Unsupported image format: {kind}')
    frame = decode_image(path)
    return frame.width, frame.height, packed_rgb(frame)


def _rect_within(rect, size, name):
    left, top, width, height = rect
    limit_w, limit_h = size
    if left < 0 or top < 0 or width <= 0 or height <= 0 or \
            left + width > limit_w or top + height > limit_h:
        raise ValueError(f'{name} {rect} is outside {limit_w}x{limit_h}')
    return rect


def _roi(rgb, size, rect):
    left, top, width, height = rect
    limit_w, _ = size
    output = bytearray()
    for row in range(top, top + height):
        start = (row * limit_w + left) * 3
        output.extend(rgb[start:start + width * 3])
    return bytes(output)


def compare(source_rgb, display_rgb, source_size, display_size, source_rect, display_rect, gain=4):
    """Return full-frame ROI metrics and amplified RGB888 diff rows."""
    if source_rect[2:] != display_rect[2:]:
        raise ValueError('Source and display rectangles must have the same dimensions')
    left, top, width, height = source_rect
    source = _roi(source_rgb, source_size, source_rect)
    display = _roi(display_rgb, display_size, display_rect)
    count = width * height * 3
    absolute = 0
    squared = 0
    maximum = 0
    differing = 0
    per_channel = [[0, 0] for _ in range(3)]
    diff = bytearray()
    for index in range(0, count, 3):
        pixel_diff = 0
        for channel in range(3):
            delta = abs(source[index + channel] - display[index + channel])
            absolute += delta
            squared += delta * delta
            maximum = max(maximum, delta)
            per_channel[channel][0] += delta
            per_channel[channel][1] += delta * delta
            pixel_diff |= delta
            diff.append(min(255, delta * gain))
        differing += bool(pixel_diff)
    return {
        'source_rect': list(source_rect),
        'display_rect': list(display_rect),
        'pixels': width * height,
        'channels': count,
        'mae': absolute / count,
        'rmse': math.sqrt(squared / count),
        'max_absolute_error': maximum,
        'differing_pixels': differing,
        'mae_rgb': [total / (width * height) for total, _ in per_channel],
        'rmse_rgb': [math.sqrt(total / (width * height)) for _, total in per_channel],
        'diff_rgb': bytes(diff),
        'aligned_rgb': source,
        'diff_size': (width, height),
    }


def analyze(source, display, *, source_format='auto', display_format='auto',
            source_size=DEFAULT_SIZE, display_size=DEFAULT_SIZE,
            crop=None, display_crop=None, shift=(0, 0), gain=4, output=None):
    """Load both images, align them, and return a JSON-serializable report."""
    source_w, source_h, source_rgb = load_rgb(source, source_size, source_format,
                                              {'i420': 'i420', 'yuv420p': 'i420', 'png': 'png',
                                               'rgb24': 'rgb24'})
    display_w, display_h, display_rgb = load_rgb(display, display_size, display_format)
    source_rect = _rect_within(crop or (0, 0, source_w, source_h), (source_w, source_h), 'crop')
    if display_crop:
        display_rect = _rect_within(display_crop, (display_w, display_h), 'display crop')
        if display_rect[2:] != source_rect[2:]:
            raise ValueError('Explicit display crop must match the source crop size')
    else:
        display_rect = _rect_within((source_rect[0] + shift[0], source_rect[1] + shift[1],
                                     source_rect[2], source_rect[3]),
                                    (display_w, display_h), 'shifted crop')
    result = compare(source_rgb, display_rgb, (source_w, source_h), (display_w, display_h),
                     source_rect, display_rect, gain)
    report = OrderedDict((
        ('source', str(source)), ('source_format', source_format),
        ('source_size', [source_w, source_h]),
        ('display', str(display)), ('display_format', display_format),
        ('display_size', [display_w, display_h]),
        ('shift', list(shift)), ('gain', gain),
        ('mae', result['mae']), ('rmse', result['rmse']),
        ('max_absolute_error', result['max_absolute_error']),
        ('differing_pixels', result['differing_pixels']),
        ('mae_rgb', result['mae_rgb']), ('rmse_rgb', result['rmse_rgb']),
        ('source_rect', result['source_rect']), ('display_rect', result['display_rect']),
    ))
    if output:
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)
        width, height = result['diff_size']
        aligned = output / 'source-aligned.png'
        difference = output / 'frame-diff.png'
        aligned.write_bytes(png(width, height,
                                b''.join(b'\0' + result['aligned_rgb'][row * width * 3:
                                                                       (row + 1) * width * 3]
                                         for row in range(height))))
        difference.write_bytes(png(width, height,
                                   b''.join(b'\0' + result['diff_rgb'][row * width * 3:
                                                                       (row + 1) * width * 3]
                                            for row in range(height))))
        report['source_aligned_png'] = str(aligned)
        report['diff_png'] = str(difference)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Original decoded frame (PNG or raw I420)')
    parser.add_argument('--display', type=Path, required=True, help='Final LCD image (PNG or raw RGB24)')
    parser.add_argument('--source-format', choices=('auto', 'i420', 'png', 'rgb24'), default='auto')
    parser.add_argument('--display-format', choices=('auto', 'png', 'rgb24'), default='auto')
    parser.add_argument('--source-size', type=parse_size, default=DEFAULT_SIZE, help='WIDTHxHEIGHT for raw input')
    parser.add_argument('--display-size', type=parse_size, default=DEFAULT_SIZE, help='WIDTHxHEIGHT for raw input')
    parser.add_argument('--crop', type=parse_rect, help='LEFT,TOP,WIDTH,HEIGHT in source coordinates')
    parser.add_argument('--display-crop', type=parse_rect, help='Explicit LEFT,TOP,WIDTH,HEIGHT in display coordinates')
    parser.add_argument('--shift', type=lambda value: tuple(int(part) for part in value.split(',')),
                        default=(0, 0), help='DX,DY added to the source crop in display coordinates')
    parser.add_argument('--gain', type=int, default=4, help='Absolute diff amplification (default: 4)')
    parser.add_argument('--output', type=Path, help='Directory for source-aligned.png and frame-diff.png')
    parser.add_argument('--report', type=Path, help='Write the JSON report to this path')
    args = parser.parse_args(argv)
    if len(args.shift) != 2 or args.gain < 1:
        parser.error('--shift needs DX,DY and --gain must be positive')
    if args.display_crop and args.shift != (0, 0):
        parser.error('Use either --display-crop or --shift, not both')
    try:
        report = analyze(args.source, args.display, source_format=args.source_format,
                         display_format=args.display_format, source_size=args.source_size,
                         display_size=args.display_size, crop=args.crop, display_crop=args.display_crop,
                         shift=args.shift, gain=args.gain, output=args.output)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    text = json.dumps(report, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding='utf-8')
    print(text, end='')
    return 0


if __name__ == '__main__':
    sys.exit(main())
