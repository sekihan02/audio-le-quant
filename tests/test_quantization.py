import math
import unittest

from audio_le_quant.audio import AudioClip, generate_signal
from audio_le_quant.quantization import (
    calculate_metrics,
    linear_quantize,
    mu_law_decode_sample,
    mu_law_encode_sample,
    mu_law_quantize,
)


class QuantizationTests(unittest.TestCase):
    def test_linear_quantization_uses_expected_payload_size(self) -> None:
        clip = generate_signal("sine", 440.0, 0.25, 8000)
        payload = linear_quantize(clip, bit_depth=4)
        self.assertEqual(payload.payload_bytes, 1000)
        self.assertLessEqual(max(payload.codes), 15)

    def test_mulaw_roundtrip_keeps_small_signal_reasonably_close(self) -> None:
        code = mu_law_encode_sample(0.1)
        decoded = mu_law_decode_sample(code)
        self.assertLess(abs(decoded - 0.1), 0.03)

    def test_metrics_for_identical_clips_report_infinite_snr(self) -> None:
        clip = AudioClip(sample_rate=8000, channels=1, samples=[[0.0, 0.5, -0.5]])
        metrics = calculate_metrics(clip, clip)
        self.assertTrue(math.isinf(metrics.snr_db))

    def test_mulaw_quantization_changes_the_signal(self) -> None:
        clip = generate_signal("sine", 660.0, 0.1, 8000, amplitude=0.75)
        payload = mu_law_quantize(clip)
        metrics = calculate_metrics(clip, payload.processed_clip)
        self.assertGreater(metrics.rmse, 0.0)


if __name__ == "__main__":
    unittest.main()

