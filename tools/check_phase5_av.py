"""Pace synthetic H.264 and PCM through the PC receiver after the TLS boundary."""

import argparse
from contextlib import ExitStack
import ctypes
from fractions import Fraction
import json
import os
from statistics import mean
import struct
import sys
from time import perf_counter, process_time, sleep

import av

from inspect_firmware import ROOT

sys.path.insert(0, str(ROOT / 'src'))

from i30_receiver import schema
from i30_receiver.audio import AudioMixer, GUIDANCE, MUSIC, pcm_bytes
from i30_receiver.mock import MockPlayback
from i30_receiver.platform import DiagnosticSink, Platform, quiet
from i30_receiver.protocol import CTL, GUIDANCE_CHANNEL, SHARED, ProtocolSession, Stage, codec, ctrl, media
from i30_receiver.video import H264Decoder
from i30_receiver.wire import CONTROL, ENCRYPTED, Message


def source_video():
    encoder = av.CodecContext.create('libx264', 'w')
    encoder.width, encoder.height = 800, 480
    encoder.pix_fmt = 'yuv420p'
    encoder.framerate = Fraction(30, 1)
    encoder.time_base = Fraction(1, 30)
    encoder.options = {'preset': 'ultrafast', 'tune': 'zerolatency', 'profile': 'baseline',
                       'x264-params': 'keyint=30:min-keyint=30:scenecut=0:repeat-headers=1'}
    packets = []
    for index in range(30):
        frame = av.VideoFrame(800, 480, 'yuv420p')
        frame.pts = index
        for plane, color in zip(frame.planes, (48 + index * 5, 105, 160)):
            plane.update(bytes([color]) * plane.buffer_size)
        packets.extend(bytes(packet) for packet in encoder.encode(frame))
    packets.extend(bytes(packet) for packet in encoder.encode())
    if len(packets) != 30:
        raise ValueError('Expected one H.264 access unit per synthetic frame')
    return packets


class MeasureVideo(DiagnosticSink):
    def __init__(self):
        super().__init__(quiet)
        self.decoder = H264Decoder(av)
        self.sent = []
        self.decode_latency = []
        self.paced_latency = []
        self.latest = None
        self.start = 0

    def packet(self, channel, kind, timestamp, data):
        if kind == 'video':
            self.sent.append(perf_counter())
            self.consume(self.decoder.push(data))

    def consume(self, frames):
        for frame in frames:
            index = len(self.decode_latency)
            if frame.width != 800 or frame.height != 480 or index >= len(self.sent):
                raise ValueError('Unexpected frame size or sequence')
            self.latest = bytes(frame.reformat(format='rgb24').planes[0])
            rendered = perf_counter()
            self.decode_latency.append((rendered - self.sent[index]) * 1000)
            self.paced_latency.append((rendered - (self.start + index / 30)) * 1000)


def memory_sampler():
    if os.name != 'nt':
        return lambda: None

    class Counters(ctypes.Structure):
        _fields_ = [('size', ctypes.c_uint32), ('faults', ctypes.c_uint32)] + [
            (name, ctypes.c_size_t) for name in ('peak', 'working_set', 'peak_paged_pool', 'paged_pool',
                                                'peak_nonpaged_pool', 'nonpaged_pool', 'pagefile', 'peak_pagefile')]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    process = kernel.GetCurrentProcess()
    query = ctypes.WinDLL('psapi', use_last_error=True).GetProcessMemoryInfo
    query.argtypes = (ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_uint32)
    counters = Counters(size=ctypes.sizeof(Counters))

    def sample():
        if not query(process, ctypes.byref(counters), counters.size):
            raise ctypes.WinError(ctypes.get_last_error())
        return counters.working_set

    return sample


def latency(values):
    ordered = sorted(values)
    rank = max(0, (95 * len(values) + 99) // 100 - 1)
    return {'mean_ms': round(mean(values), 2), 'p95_ms': round(ordered[rank], 2), 'max_ms': round(ordered[-1], 2)}


def check_wave_device(device):
    from i30_receiver.audio_win import WavePlayback

    first, second = WavePlayback(device), WavePlayback(device)
    denial = None
    with ExitStack() as cleanup:
        cleanup.callback(first.close)
        cleanup.callback(second.close)
        first.start()
        try:
            second.start()
        except OSError as error:
            denial = str(error)
        for player in (first,) if denial else (first, second):
            player.write(bytes(player.format.block_bytes()))
        sleep(0.08)
    if first.handle or second.handle:
        raise ValueError('WinMM handles remained open')
    return {'device': device, 'shared_playback': denial is None, 'second_open_error': denial, 'handles_released': True}


def run(seconds):
    clips = source_video()
    expected_video = round(seconds * 30)
    expected_pcm = round(seconds * 50)
    video = MeasureVideo()
    output = MockPlayback()
    audio = AudioMixer(output)
    platform = Platform(clock=perf_counter)
    session = ProtocolSession(None, None, platform, video, quiet, audio=audio)
    session.stage = Stage.ACTIVE
    session.next_ping = float('inf')
    ack_counts = {3: 0, 4: 0, GUIDANCE_CHANNEL: 0}

    def emit(code, payload, channel=0, **_):
        if channel in ack_counts and code == media('ACK'):
            if payload.session_id != 100 + channel or payload.ack != 1:
                raise ValueError('Invalid PCM or video transport acknowledgment')
            ack_counts[channel] += 1

    session.emit = emit

    def message(channel, code, payload, flags=0):
        data = payload if isinstance(payload, bytes) else payload.SerializeToString()
        session.handle(Message(channel, ENCRYPTED | flags, code, data))

    for number in ack_counts:
        message(number, ctrl('CHANNEL_OPEN_REQUEST'), schema.message(CTL + 'ChannelOpenRequest')(
            priority=0, service_id=number), CONTROL)
        name = 'VIDEO_H264_BP' if number == 3 else 'AUDIO_PCM'
        message(number, media('SETUP'), schema.message(SHARED + 'Setup')(type=codec(name)))
        message(number, media('START'), schema.message(SHARED + 'Start')(configuration_index=0, session_id=100 + number))
    message(0, ctrl('AUDIO_FOCUS_REQUEST'), schema.message(CTL + 'AudioFocusRequest')(audio_focus_type=1))

    music = pcm_bytes([8000]) * (MUSIC.block_bytes() // 2)
    guidance = pcm_bytes([2000]) * (GUIDANCE.block_bytes() // 2)
    sample = memory_sampler()
    starting_memory = peak = sample()
    cpu_start = process_time()
    video.start = start = perf_counter()
    next_video = next_pcm = 0
    mixed = 0
    previous_audio = 0
    while (next_video < expected_video or next_pcm < expected_pcm or any(audio.queues.values())):
        now = perf_counter()
        if now - start > seconds + 5:
            raise TimeoutError('Timed A/V fixture did not drain')
        if next_video < expected_video and now >= start + next_video / 30:
            message(3, media('DATA'), struct.pack('>Q', next_video * 1_000_000 // 30) + clips[next_video % 30])
            next_video += 1
        if next_pcm < expected_pcm and now >= start + next_pcm / 50:
            prefix = struct.pack('>Q', next_pcm * 20_000)
            message(4, media('DATA'), prefix + music)
            if next_pcm % 50 in range(15, 27):
                message(GUIDANCE_CHANNEL, media('DATA'), prefix + guidance)
            next_pcm += 1
        session.tick()
        if audio.blocks_written != previous_audio:
            mixed += int(output.last.startswith(pcm_bytes([4000])))
            previous_audio = audio.blocks_written
        reading = sample()
        if reading is not None:
            peak = max(peak, reading)
        sleep(0.001)
    video.consume(video.decoder.finish())
    elapsed = perf_counter() - start
    cpu = process_time() - cpu_start
    session.release_channels()
    received = len(video.decode_latency)
    return {'seconds_requested': seconds, 'wall_seconds': round(elapsed, 3), 'video_frames_sent': next_video,
            'video_frames_decoded': received, 'video_frames_missing': next_video - received,
            'decode_to_rgb_after_ingress': latency(video.decode_latency),
            'scheduled_frame_to_rgb': latency(video.paced_latency), 'channel_acks': ack_counts,
            'music_blocks_out': audio.blocks_written, 'guidance_mixed_blocks': mixed, 'audio_samples_dropped': audio.dropped,
            'process_cpu_seconds': round(cpu, 4), 'cpu_percent_of_one_core': round(100 * cpu / elapsed, 1),
            'working_set_start_mib': round(starting_memory / 2**20, 2) if starting_memory is not None else None,
            'peak_sampled_working_set_mib': round(peak / 2**20, 2) if peak is not None else None,
            'passed': received == expected_video and ack_counts[3] == expected_video
            and ack_counts[4] == expected_pcm and audio.blocks_written == expected_pcm and mixed > 0 and not audio.dropped}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=int, default=2)
    parser.add_argument('--wave-device', type=int, metavar='DEVICE', help='Also test two WinMM handles with silent PCM')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 1800:
        parser.error('Choose 1 to 1800 seconds')
    if args.wave_device is not None and os.name != 'nt':
        parser.error('WinMM requires desktop Windows')
    result = run(args.seconds)
    if args.wave_device is not None:
        result['winmm'] = check_wave_device(args.wave_device)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
