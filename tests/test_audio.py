import os
import tempfile
import unittest

from audio_le_quant.audio import generate_signal, read_wav, write_wav


class AudioIoTests(unittest.TestCase):
    def test_wav_roundtrip_keeps_shape(self) -> None:
        clip = generate_signal(
            waveform="sine",
            frequency=220.0,
            duration_seconds=0.2,
            sample_rate=8000,
            amplitude=0.5,
            channels=2,
        )

        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.remove(handle.name))

        write_wav(handle.name, clip, bit_depth=16)
        loaded = read_wav(handle.name)

        self.assertEqual(loaded.sample_rate, clip.sample_rate)
        self.assertEqual(loaded.channels, clip.channels)
        self.assertEqual(loaded.frame_count, clip.frame_count)


if __name__ == "__main__":
    unittest.main()

