import os
import tempfile
import unittest

from audio_le_quant.alq_format import pack_bits, read_alq, unpack_bits, write_alq
from audio_le_quant.audio import generate_signal
from audio_le_quant.quantization import linear_quantize, mu_law_quantize


class AlqFormatTests(unittest.TestCase):
    def test_pack_unpack_roundtrip(self) -> None:
        codes = [0, 3, 5, 7, 1, 2, 6, 4, 7]
        packed = pack_bits(codes, bit_depth=3)
        unpacked = unpack_bits(packed, bit_depth=3, count=len(codes))
        self.assertEqual(unpacked, codes)

    def test_linear_file_roundtrip(self) -> None:
        clip = generate_signal("sine", 440.0, 0.1, 8000)
        payload = linear_quantize(clip, bit_depth=5)
        handle = tempfile.NamedTemporaryFile(suffix=".alq", delete=False)
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.remove(handle.name))

        write_alq(handle.name, payload)
        loaded = read_alq(handle.name)

        self.assertEqual(loaded.codec, "linear")
        self.assertEqual(loaded.bit_depth, 5)
        self.assertEqual(loaded.codes, payload.codes)

    def test_mulaw_file_roundtrip(self) -> None:
        clip = generate_signal("square", 220.0, 0.1, 8000)
        payload = mu_law_quantize(clip, mu=100)
        handle = tempfile.NamedTemporaryFile(suffix=".alq", delete=False)
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.remove(handle.name))

        write_alq(handle.name, payload)
        loaded = read_alq(handle.name)

        self.assertEqual(loaded.codec, "mulaw")
        self.assertEqual(loaded.codes, payload.codes)
        self.assertEqual(loaded.mu, 100)

    def test_written_alq_header_has_expected_fields(self) -> None:
        clip = generate_signal("sine", 440.0, 0.05, 8000)
        payload = linear_quantize(clip, bit_depth=4)
        handle = tempfile.NamedTemporaryFile(suffix=".alq", delete=False)
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.remove(handle.name))

        write_alq(handle.name, payload)
        with open(handle.name, "rb") as input_file:
            raw = input_file.read(20)

        self.assertEqual(raw[0:4], b"ALQ1")
        self.assertEqual(raw[4], 1)
        self.assertEqual(raw[5], 1)
        self.assertEqual(raw[6], 1)
        self.assertEqual(raw[7], 4)


if __name__ == "__main__":
    unittest.main()
