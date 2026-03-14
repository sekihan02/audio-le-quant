from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import List


def clamp_sample(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _read_u16_le(buffer: bytes, offset: int) -> int:
    return buffer[offset] | (buffer[offset + 1] << 8)


def _read_u32_le(buffer: bytes, offset: int) -> int:
    return (
        buffer[offset]
        | (buffer[offset + 1] << 8)
        | (buffer[offset + 2] << 16)
        | (buffer[offset + 3] << 24)
    )


def _append_u16_le(buffer: bytearray, value: int) -> None:
    buffer.append(value & 0xFF)
    buffer.append((value >> 8) & 0xFF)


def _append_u32_le(buffer: bytearray, value: int) -> None:
    buffer.append(value & 0xFF)
    buffer.append((value >> 8) & 0xFF)
    buffer.append((value >> 16) & 0xFF)
    buffer.append((value >> 24) & 0xFF)


def _read_i16_le(buffer: bytes, offset: int) -> int:
    value = _read_u16_le(buffer, offset)
    if value >= 0x8000:
        value -= 0x10000
    return value


def _append_i16_le(buffer: bytearray, value: int) -> None:
    if value < 0:
        value += 0x10000
    _append_u16_le(buffer, value)


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
    with open(path, "rb") as input_file:
        raw = input_file.read()

    if len(raw) < 12:
        raise ValueError("WAV ファイルとして短すぎます")
    if raw[0:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise ValueError("RIFF/WAVE ヘッダが見つかりません")

    fmt_chunk = None
    data_chunk = None
    offset = 12

    while offset + 8 <= len(raw):
        chunk_id = raw[offset : offset + 4]
        chunk_size = _read_u32_le(raw, offset + 4)
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_size
        if chunk_end > len(raw):
            raise ValueError("チャンクサイズがファイル末尾を超えています")

        chunk_payload = raw[chunk_start:chunk_end]
        if chunk_id == b"fmt " and fmt_chunk is None:
            fmt_chunk = chunk_payload
        elif chunk_id == b"data" and data_chunk is None:
            data_chunk = chunk_payload

        offset = chunk_end + (chunk_size % 2)

    if fmt_chunk is None or data_chunk is None:
        raise ValueError("fmt または data チャンクが見つかりません")
    if len(fmt_chunk) < 16:
        raise ValueError("fmt チャンクが短すぎます")

    audio_format = _read_u16_le(fmt_chunk, 0)
    channels = _read_u16_le(fmt_chunk, 2)
    sample_rate = _read_u32_le(fmt_chunk, 4)
    block_align = _read_u16_le(fmt_chunk, 12)
    bit_depth = _read_u16_le(fmt_chunk, 14)

    if audio_format != 1:
        raise ValueError("PCM 以外の WAV には対応していません")
    if bit_depth not in (8, 16):
        raise ValueError("対応している WAV は 8bit / 16bit PCM のみです")
    if channels <= 0 or sample_rate <= 0:
        raise ValueError("WAV ヘッダのチャンネル数またはサンプルレートが不正です")

    bytes_per_sample = bit_depth // 8
    expected_block_align = channels * bytes_per_sample
    if block_align != expected_block_align:
        raise ValueError("block_align が PCM 情報と一致しません")
    if len(data_chunk) % block_align != 0:
        raise ValueError("data チャンク長がフレーム境界に揃っていません")

    frame_count = len(data_chunk) // block_align
    channel_data = [[] for _ in range(channels)]

    if bit_depth == 8:
        for index, byte_value in enumerate(data_chunk):
            channel = index % channels
            channel_data[channel].append(clamp_sample((byte_value / 127.5) - 1.0))
    else:
        sample_total = frame_count * channels
        for sample_index in range(sample_total):
            byte_offset = sample_index * 2
            sample = _read_i16_le(data_chunk, byte_offset)
            channel = sample_index % channels
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
        pcm = bytearray()
        for frame_index in range(clip.frame_count):
            for channel_index in range(clip.channels):
                sample = clamp_sample(clip.samples[channel_index][frame_index])
                if sample <= -1.0:
                    value = -32768
                else:
                    value = int(round(sample * 32767.0))
                _append_i16_le(pcm, value)
        payload = bytes(pcm)

    bytes_per_sample = 1 if bit_depth == 8 else 2
    block_align = clip.channels * bytes_per_sample
    byte_rate = clip.sample_rate * block_align
    payload_padding = len(payload) % 2
    riff_size = 4 + (8 + 16) + (8 + len(payload)) + payload_padding

    output = bytearray()
    output.extend(b"RIFF")
    _append_u32_le(output, riff_size)
    output.extend(b"WAVE")

    output.extend(b"fmt ")
    _append_u32_le(output, 16)
    _append_u16_le(output, 1)
    _append_u16_le(output, clip.channels)
    _append_u32_le(output, clip.sample_rate)
    _append_u32_le(output, byte_rate)
    _append_u16_le(output, block_align)
    _append_u16_le(output, bit_depth)

    output.extend(b"data")
    _append_u32_le(output, len(payload))
    output.extend(payload)
    if payload_padding:
        output.append(0)

    with open(path, "wb") as output_file:
        output_file.write(output)
