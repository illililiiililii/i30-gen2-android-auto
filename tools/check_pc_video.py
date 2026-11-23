"""Decode a local Annex B H.264 clip and optionally save its first frame."""

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from i30_receiver.video import H264Decoder, write_preview


MAX_INPUT_BYTES = 64 * 1024 * 1024
CHUNK_SIZE = 64 * 1024


def decode_frames(av, source):
    decoder = H264Decoder(av)
    consumed = 0
    while chunk := source.read(CHUNK_SIZE):
        consumed += len(chunk)
        if consumed > MAX_INPUT_BYTES:
            raise ValueError("H.264 input exceeds 64 MiB")
        yield from decoder.push(chunk)
    yield from decoder.finish()


def inspect_clip(av, source, preview=None):
    first = None
    sizes = set()
    count = 0
    started = perf_counter()
    with source.open("rb") as stream:
        for frame in decode_frames(av, stream):
            count += 1
            sizes.add((frame.width, frame.height))
            if preview is not None and first is None:
                first = frame
    seconds = perf_counter() - started
    if not count:
        raise ValueError("H.264 input contains no decodable frames")
    if first is not None:
        write_preview(av, first, preview)
    return {
        "frames": count,
        "resolutions": [f"{w}x{h}" for w, h in sorted(sizes)],
        "decode_seconds": round(seconds, 4),
        "frames_per_second": round(count / seconds, 1),
        "preview": str(preview) if preview is not None else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clip", type=Path, help="Local H.264 elementary stream")
    parser.add_argument("--preview", type=Path, help="Write a new PNG, leaving existing files intact")
    args = parser.parse_args()
    try:
        import av
    except ImportError:
        parser.exit(1, "PyAV is required. Install with: python -m pip install av==19.0.2\n")
    try:
        if not args.clip.is_file():
            raise ValueError("Input must be an existing local file")
        print(json.dumps(inspect_clip(av, args.clip, args.preview)))
    except (OSError, ValueError, av.FFmpegError) as exc:
        parser.exit(1, f"Video check failed: {exc}\n")


if __name__ == "__main__":
    main()
