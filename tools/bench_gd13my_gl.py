"""Compare GD13MY host OpenGL backends with a deterministic 800x480 scene."""

import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
from statistics import median
from time import perf_counter

from gd13my_software_gl import BitmapGL, GLES_HEIGHT, GLES_WIDTH


def scene_vertices(columns, rows):
    values = []
    for row in range(rows):
        y0 = -1.0 + 2.0 * row / rows
        y1 = -1.0 + 2.0 * (row + 1) / rows
        for column in range(columns):
            x0 = -1.0 + 2.0 * column / columns
            x1 = -1.0 + 2.0 * (column + 1) / columns
            values.extend((x0, y0, x1, y0, x1, y1, x0, y0, x1, y1, x0, y1))
    return (C.c_float * len(values))(*values)


def summarize(values):
    return {"median_ms": round(median(values) * 1000, 3),
            "p95_ms": round(sorted(values)[min(len(values) - 1, int(len(values) * .95))] * 1000, 3)}


def run_backend(name, frames, warmup, columns, rows):
    os.environ["GD13MY_GL_BACKEND"] = name
    created = perf_counter()
    gl = BitmapGL()
    init_seconds = perf_counter() - created
    vertices = scene_vertices(columns, rows)
    try:
        gl.call("glViewport", None, "iiii", 0, 0, GLES_WIDTH, GLES_HEIGHT)
        gl.call("glMatrixMode", None, "u", 0x1701)
        gl.call("glLoadIdentity", None, "")
        gl.call("glOrtho", None, "dddddd", -1.0, 1.0, -1.0, 1.0, -1.0, 1.0)
        gl.call("glMatrixMode", None, "u", 0x1700)
        gl.call("glLoadIdentity", None, "")
        gl.call("glColor4f", None, "ffff", 0.15, 0.72, 0.38, 1.0)
        gl.call("glVertexPointer", None, "iuip", 2, 0x1406, 0, vertices)
        gl.call("glEnableClientState", None, "u", 0x8074)

        def render():
            gl.call("glClearColor", None, "ffff", 0.04, 0.08, 0.12, 1.0)
            gl.call("glClear", None, "u", 0x4000)
            gl.call("glDrawArrays", None, "uii", 0x0004, 0, len(vertices) // 2)
            gl.call("glFinish", None, "")

        for _ in range(warmup):
            render()
            gl.read_pixels(0, 0, GLES_WIDTH, GLES_HEIGHT, 0x1907)
        draw_times, read_times, hashes = [], [], []
        for _ in range(frames):
            start = perf_counter()
            render()
            draw_times.append(perf_counter() - start)
            start = perf_counter()
            pixels = gl.read_pixels(0, 0, GLES_WIDTH, GLES_HEIGHT, 0x1907)
            read_times.append(perf_counter() - start)
            hashes.append(hashlib.sha256(pixels).hexdigest())
        return {
            "requested_backend": name,
            "backend": gl.backend,
            "vendor": gl.vendor,
            "renderer": gl.renderer,
            "version": gl.version,
            "init_ms": round(init_seconds * 1000, 3),
            "scene": {"width": GLES_WIDTH, "height": GLES_HEIGHT,
                      "triangles": len(vertices) // 6,
                      "frame_bytes": GLES_WIDTH * GLES_HEIGHT * 3},
            "draw_and_finish": summarize(draw_times),
            "frame_readback": summarize(read_times),
            "total_frame": summarize([draw + read for draw, read in zip(draw_times, read_times)]),
            "pixel_sha256": hashes,
            "_pixel_frame": pixels,
        }
    finally:
        gl.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--columns", type=int, default=40)
    parser.add_argument("--rows", type=int, default=25)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if min(args.frames, args.columns, args.rows) < 1 or args.warmup < 0:
        parser.error("frames, columns and rows must be positive; warmup cannot be negative")
    results = []
    for name in ("software", "hardware"):
        try:
            results.append(run_backend(name, args.frames, args.warmup, args.columns, args.rows))
        except (AttributeError, OSError, RuntimeError) as exc:
            results.append({"requested_backend": name, "unavailable": str(exc)})
    software, hardware = results
    if "pixel_sha256" in software and "pixel_sha256" in hardware:
        software_hashes = set(software["pixel_sha256"])
        hardware_hashes = set(hardware["pixel_sha256"])
        software["stable_frames"] = len(software_hashes) == 1
        hardware["stable_frames"] = len(hardware_hashes) == 1
        sw_frame, hw_frame = software.pop("_pixel_frame"), hardware.pop("_pixel_frame")
        differences = [abs(a - b) for a, b in zip(sw_frame, hw_frame)]
        software["cross_backend_pixels_match"] = sw_frame == hw_frame
        software["cross_backend_differing_channels"] = sum(value != 0 for value in differences)
        software["cross_backend_max_channel_delta"] = max(differences, default=0)
    else:
        for result in results:
            result.pop("_pixel_frame", None)
    report = {"frames": args.frames, "warmup": args.warmup, "results": results}
    serialized = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()
