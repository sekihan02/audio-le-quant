from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List

from .audio import AudioClip, clamp_sample


@dataclass
class AudioMetrics:
    mse: float
    rmse: float
    mean_abs_error: float
    peak_error: float
    snr_db: float


@dataclass
class QuantizedPayload:
    codec: str
    bit_depth: int
    sample_rate: int
    channels: int
    frame_count: int
    codes: List[int]
    processed_clip: AudioClip
    mu: int = 255

    @property
    def sample_count(self) -> int:
        return self.channels * self.frame_count

    @property
    def payload_bytes(self) -> int:
        return int(math.ceil((self.sample_count * self.bit_depth) / 8.0))


def linear_quantize(clip: AudioClip, bit_depth: int) -> QuantizedPayload:
    if bit_depth < 1 or bit_depth > 16:
        raise ValueError("bit_depth must be between 1 and 16")

    levels = 1 << bit_depth
    processed = [[] for _ in range(clip.channels)]
    codes = []

    for frame_index in range(clip.frame_count):
        for channel_index in range(clip.channels):
            sample = clamp_sample(clip.samples[channel_index][frame_index])
            scaled = (sample + 1.0) * 0.5 * (levels - 1)
            code = int(round(scaled))
            code = max(0, min(levels - 1, code))
            decoded = (code / float(levels - 1)) * 2.0 - 1.0 if levels > 1 else 0.0
            codes.append(code)
            processed[channel_index].append(clamp_sample(decoded))

    return QuantizedPayload(
        codec="linear",
        bit_depth=bit_depth,
        sample_rate=clip.sample_rate,
        channels=clip.channels,
        frame_count=clip.frame_count,
        codes=codes,
        processed_clip=AudioClip(
            sample_rate=clip.sample_rate,
            channels=clip.channels,
            samples=processed,
        ),
    )


def decode_linear_codes(
    sample_rate: int,
    channels: int,
    frame_count: int,
    bit_depth: int,
    codes: List[int],
) -> QuantizedPayload:
    levels = 1 << bit_depth
    expected = channels * frame_count
    if len(codes) != expected:
        raise ValueError("linear code count does not match header information")

    processed = [[] for _ in range(channels)]
    for index, code in enumerate(codes):
        channel_index = index % channels
        decoded = (code / float(levels - 1)) * 2.0 - 1.0 if levels > 1 else 0.0
        processed[channel_index].append(clamp_sample(decoded))

    return QuantizedPayload(
        codec="linear",
        bit_depth=bit_depth,
        sample_rate=sample_rate,
        channels=channels,
        frame_count=frame_count,
        codes=list(codes),
        processed_clip=AudioClip(sample_rate=sample_rate, channels=channels, samples=processed),
    )


def mu_law_encode_sample(sample: float, mu: int = 255) -> int:
    sample = clamp_sample(sample)
    if mu <= 0:
        raise ValueError("mu must be positive")
    magnitude = math.log1p(mu * abs(sample)) / math.log1p(mu)
    companded = math.copysign(magnitude, sample)
    code = int(round((companded + 1.0) * 127.5))
    return max(0, min(255, code))


def mu_law_decode_sample(code: int, mu: int = 255) -> float:
    if mu <= 0:
        raise ValueError("mu must be positive")
    companded = (code / 127.5) - 1.0
    magnitude = ((1.0 + mu) ** abs(companded) - 1.0) / float(mu)
    return clamp_sample(math.copysign(magnitude, companded))


def mu_law_quantize(clip: AudioClip, mu: int = 255) -> QuantizedPayload:
    processed = [[] for _ in range(clip.channels)]
    codes = []

    for frame_index in range(clip.frame_count):
        for channel_index in range(clip.channels):
            code = mu_law_encode_sample(clip.samples[channel_index][frame_index], mu=mu)
            decoded = mu_law_decode_sample(code, mu=mu)
            codes.append(code)
            processed[channel_index].append(decoded)

    return QuantizedPayload(
        codec="mulaw",
        bit_depth=8,
        sample_rate=clip.sample_rate,
        channels=clip.channels,
        frame_count=clip.frame_count,
        codes=codes,
        processed_clip=AudioClip(
            sample_rate=clip.sample_rate,
            channels=clip.channels,
            samples=processed,
        ),
        mu=mu,
    )


def decode_mu_law_codes(
    sample_rate: int,
    channels: int,
    frame_count: int,
    codes: List[int],
    mu: int = 255,
) -> QuantizedPayload:
    expected = channels * frame_count
    if len(codes) != expected:
        raise ValueError("mu-law code count does not match header information")

    processed = [[] for _ in range(channels)]
    for index, code in enumerate(codes):
        channel_index = index % channels
        processed[channel_index].append(mu_law_decode_sample(code, mu=mu))

    return QuantizedPayload(
        codec="mulaw",
        bit_depth=8,
        sample_rate=sample_rate,
        channels=channels,
        frame_count=frame_count,
        codes=list(codes),
        processed_clip=AudioClip(sample_rate=sample_rate, channels=channels, samples=processed),
        mu=mu,
    )


def estimate_pcm_bytes(clip: AudioClip, bit_depth: int = 16) -> int:
    return int(math.ceil((clip.frame_count * clip.channels * bit_depth) / 8.0))


def calculate_metrics(original: AudioClip, processed: AudioClip) -> AudioMetrics:
    if original.sample_rate != processed.sample_rate:
        raise ValueError("sample rate mismatch")
    if original.channels != processed.channels:
        raise ValueError("channel count mismatch")
    if original.frame_count != processed.frame_count:
        raise ValueError("frame count mismatch")

    sample_total = original.channels * original.frame_count
    signal_power = 0.0
    noise_power = 0.0
    sum_abs_error = 0.0
    peak_error = 0.0

    for channel_index in range(original.channels):
        for frame_index in range(original.frame_count):
            source = original.samples[channel_index][frame_index]
            target = processed.samples[channel_index][frame_index]
            error = source - target
            signal_power += source * source
            noise_power += error * error
            sum_abs_error += abs(error)
            peak_error = max(peak_error, abs(error))

    mse = noise_power / float(sample_total)
    rmse = math.sqrt(mse)
    mean_abs_error = sum_abs_error / float(sample_total)
    if noise_power == 0.0:
        snr_db = float("inf")
    elif signal_power == 0.0:
        snr_db = 0.0
    else:
        snr_db = 10.0 * math.log10(signal_power / noise_power)

    return AudioMetrics(
        mse=mse,
        rmse=rmse,
        mean_abs_error=mean_abs_error,
        peak_error=peak_error,
        snr_db=snr_db,
    )


def build_learning_summary(
    source: AudioClip,
    payload: QuantizedPayload,
    metrics: AudioMetrics,
) -> str:
    original_bytes = estimate_pcm_bytes(source, bit_depth=16)
    ratio = 0.0
    if original_bytes:
        ratio = 100.0 * (1.0 - (payload.payload_bytes / float(original_bytes)))

    if payload.codec == "linear":
        mode_line = (
            "線形量子化では、各サンプルを {0} 段階の振幅に丸め込みます。".format(
                1 << payload.bit_depth
            )
        )
    else:
        mode_line = "μ-law は小さい音の近くに細かい精度を残し、大きい音は粗く表します。"

    snr_line = "無限大" if math.isinf(metrics.snr_db) else "{0:.2f} dB".format(metrics.snr_db)

    return "\n".join(
        [
            "音源: {0:.2f} 秒, {1} Hz, {2} ch".format(
                source.duration_seconds, source.sample_rate, source.channels
            ),
            "方式: {0}".format("線形量子化" if payload.codec == "linear" else "μ-law"),
            "payload: {0} bytes / 16-bit PCM {1} bytes ({2:.1f}% 小さい)".format(
                payload.payload_bytes,
                original_bytes,
                ratio,
            ),
            "誤差: RMSE {0:.5f}, MAE {1:.5f}, 最大誤差 {2:.5f}, SNR {3}".format(
                metrics.rmse,
                metrics.mean_abs_error,
                metrics.peak_error,
                snr_line,
            ),
            mode_line,
        ]
    )


def metrics_to_dict(metrics: AudioMetrics) -> Dict[str, float]:
    return {
        "mse": metrics.mse,
        "rmse": metrics.rmse,
        "mean_abs_error": metrics.mean_abs_error,
        "peak_error": metrics.peak_error,
        "snr_db": metrics.snr_db,
    }
