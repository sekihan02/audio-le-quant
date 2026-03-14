from __future__ import annotations

import struct
from typing import List

from .quantization import (
    QuantizedPayload,
    decode_linear_codes,
    decode_mu_law_codes,
)

MAGIC = b"ALQ1"
VERSION = 1
CODEC_LINEAR = 1
CODEC_MULAW = 2
HEADER = struct.Struct("<4sBBBBIII")


def pack_bits(codes: List[int], bit_depth: int) -> bytes:
    if bit_depth < 1 or bit_depth > 16:
        raise ValueError("bit_depth must be between 1 and 16")

    mask = (1 << bit_depth) - 1
    buffer = 0
    buffered_bits = 0
    output = bytearray()

    # 可変ビット長のコード列を左詰めで順に詰め込む。
    for code in codes:
        if code < 0 or code > mask:
            raise ValueError("code out of range for bit depth")
        buffer = (buffer << bit_depth) | code
        buffered_bits += bit_depth
        while buffered_bits >= 8:
            buffered_bits -= 8
            output.append((buffer >> buffered_bits) & 0xFF)
            buffer &= (1 << buffered_bits) - 1 if buffered_bits else 0

    if buffered_bits:
        output.append((buffer << (8 - buffered_bits)) & 0xFF)

    return bytes(output)


def unpack_bits(data: bytes, bit_depth: int, count: int) -> List[int]:
    if bit_depth < 1 or bit_depth > 16:
        raise ValueError("bit_depth must be between 1 and 16")

    buffer = 0
    buffered_bits = 0
    mask = (1 << bit_depth) - 1
    codes = []

    # 8bit 単位の生データから、元の量子化コード列を取り出す。
    for byte_value in data:
        buffer = (buffer << 8) | byte_value
        buffered_bits += 8
        while buffered_bits >= bit_depth and len(codes) < count:
            buffered_bits -= bit_depth
            codes.append((buffer >> buffered_bits) & mask)
            buffer &= (1 << buffered_bits) - 1 if buffered_bits else 0

    if len(codes) != count:
        raise ValueError("payload ended before the expected number of samples")
    return codes


def write_alq(path: str, payload: QuantizedPayload) -> None:
    if payload.channels > 255:
        raise ValueError("channel count exceeds file format limit")
    if payload.bit_depth > 255:
        raise ValueError("bit depth exceeds file format limit")

    if payload.codec == "linear":
        codec_id = CODEC_LINEAR
        body = pack_bits(payload.codes, payload.bit_depth)
    elif payload.codec == "mulaw":
        codec_id = CODEC_MULAW
        body = bytes(payload.codes)
    else:
        raise ValueError("unsupported codec: {0}".format(payload.codec))

    header = HEADER.pack(
        MAGIC,
        VERSION,
        codec_id,
        payload.channels,
        payload.bit_depth,
        payload.sample_rate,
        payload.frame_count,
        payload.mu if payload.codec == "mulaw" else 0,
    )

    with open(path, "wb") as output_file:
        output_file.write(header)
        output_file.write(body)


def read_alq(path: str) -> QuantizedPayload:
    with open(path, "rb") as input_file:
        raw = input_file.read()

    if len(raw) < HEADER.size:
        raise ValueError("ALQ ファイルとしては短すぎます")

    magic, version, codec_id, channels, bit_depth, sample_rate, frame_count, parameter = HEADER.unpack(
        raw[: HEADER.size]
    )
    if magic != MAGIC:
        raise ValueError("invalid ALQ magic header")
    if version != VERSION:
        raise ValueError("unsupported ALQ version")

    sample_count = channels * frame_count
    body = raw[HEADER.size :]

    if codec_id == CODEC_LINEAR:
        codes = unpack_bits(body, bit_depth, sample_count)
        return decode_linear_codes(
            sample_rate=sample_rate,
            channels=channels,
            frame_count=frame_count,
            bit_depth=bit_depth,
            codes=codes,
        )
    if codec_id == CODEC_MULAW:
        if len(body) != sample_count:
            raise ValueError("mu-law payload length does not match header")
        return decode_mu_law_codes(
            sample_rate=sample_rate,
            channels=channels,
            frame_count=frame_count,
            codes=list(body),
            mu=parameter or 255,
        )

    raise ValueError("unsupported ALQ codec identifier")
