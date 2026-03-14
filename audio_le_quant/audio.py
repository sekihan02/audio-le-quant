from __future__ import annotations

import math
import random
import struct
import wave
from dataclasses import dataclass
from typing import List


def clamp_sample(value: float) -> float:
    return max(-1.0, min(1.0, value))


@dataclass
class AudioClip:
    sample_rate: int
    channels: int
    samples: List[List[float]]

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if self.channels <= 0:
            raise ValueError("channels must be positive")
        if len(self.samples) != self.channels:
            raise ValueError("channel count does not match samples")
        lengths = {len(channel) for channel in self.samples}
        if len(lengths) > 1:
            raise ValueError("all channels must have the same frame count")
        self.samples = [
            [clamp_sample(sample) for sample in channel] for channel in self.samples
        ]

    @property
    def frame_count(self) -> int:
        if not self.samples:
            return 0
        return len(self.samples[0])

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / float(self.sample_rate)

    def preview_samples(self) -> List[float]:
        if self.channels == 1:
            return list(self.samples[0])
        return [
            sum(channel[index] for channel in self.samples) / float(self.channels)
            for index in range(self.frame_count)
        ]


def generate_signal(
    waveform: str,
    frequency: float,
    duration_seconds: float,
    sample_rate: int,
    amplitude: float = 0.8,
    channels: int = 1,
    seed: int = 7,
) -> AudioClip:
    frame_count = max(1, int(duration_seconds * sample_rate))
    amplitude = clamp_sample(amplitude)
    rng = random.Random(seed)
    channel_data = [[] for _ in range(channels)]

    for frame_index in range(frame_count):
        time_position = frame_index / float(sample_rate)
        if waveform == "sine":
            value = math.sin(2.0 * math.pi * frequency * time_position)
        elif waveform == "square":
            value = 1.0 if math.sin(2.0 * math.pi * frequency * time_position) >= 0.0 else -1.0
        elif waveform == "saw":
            cycle = (time_position * frequency) % 1.0
            value = (2.0 * cycle) - 1.0
        elif waveform == "noise":
            value = rng.uniform(-1.0, 1.0)
        else:
            raise ValueError("unsupported waveform: {0}".format(waveform))

        value *= amplitude
        for channel in channel_data:
            channel.append(value)

    return AudioClip(sample_rate=sample_rate, channels=channels, samples=channel_data)


def read_wav(path: str) -> AudioClip:
    with wave.open(path, "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()
        frame_count = wav_file.getnframes()
        raw = wav_file.readframes(frame_count)

    if sample_width not in (1, 2):
        raise ValueError("対応している WAV は 8bit / 16bit PCM のみです")

    channel_data = [[] for _ in range(channels)]

    if sample_width == 1:
        for index, byte_value in enumerate(raw):
            channel = index % channels
            channel_data[channel].append(clamp_sample((byte_value / 127.5) - 1.0))
    else:
        sample_total = frame_count * channels
        values = struct.unpack("<{0}h".format(sample_total), raw)
        for index, sample in enumerate(values):
            channel = index % channels
            channel_data[channel].append(clamp_sample(sample / 32768.0))

    return AudioClip(sample_rate=sample_rate, channels=channels, samples=channel_data)


def write_wav(path: str, clip: AudioClip, bit_depth: int = 16) -> None:
    if bit_depth not in (8, 16):
        raise ValueError("bit_depth must be 8 or 16 for WAV export")

    if bit_depth == 8:
        pcm = bytearray()
        for frame_index in range(clip.frame_count):
            for channel_index in range(clip.channels):
                sample = clamp_sample(clip.samples[channel_index][frame_index])
                code = int(round((sample + 1.0) * 127.5))
                pcm.append(max(0, min(255, code)))
        payload = bytes(pcm)
    else:
        values = []
        for frame_index in range(clip.frame_count):
            for channel_index in range(clip.channels):
                sample = clamp_sample(clip.samples[channel_index][frame_index])
                if sample <= -1.0:
                    values.append(-32768)
                else:
                    values.append(int(round(sample * 32767.0)))
        payload = struct.pack("<{0}h".format(len(values)), *values)

    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(clip.channels)
        wav_file.setsampwidth(1 if bit_depth == 8 else 2)
        wav_file.setframerate(clip.sample_rate)
        wav_file.writeframes(payload)
