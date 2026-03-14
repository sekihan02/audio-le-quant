from __future__ import annotations

import os
import tempfile
from typing import Optional

from .audio import AudioClip, write_wav

AVAILABLE = False

try:
    from PySide6.QtCore import QUrl
    from PySide6.QtMultimedia import QSoundEffect

    AVAILABLE = True
except ImportError:  # pragma: no cover
    QSoundEffect = None
    QUrl = None


class WavePlayer:
    def __init__(self) -> None:
        self.available = AVAILABLE
        self._temp_path: Optional[str] = None
        self._effect = QSoundEffect() if AVAILABLE else None
        if self._effect is not None:
            self._effect.setLoopCount(1)
            self._effect.setVolume(0.85)

    def play(self, clip: AudioClip) -> None:
        if not self.available or self._effect is None or QUrl is None:
            return

        if self._temp_path is None:
            handle = tempfile.NamedTemporaryFile(prefix="audio_le_quant_", suffix=".wav", delete=False)
            handle.close()
            self._temp_path = handle.name

        write_wav(self._temp_path, clip, bit_depth=16)
        self._effect.stop()
        self._effect.setSource(QUrl.fromLocalFile(self._temp_path))
        self._effect.play()

    def cleanup(self) -> None:
        if self._temp_path and os.path.exists(self._temp_path):
            try:
                os.remove(self._temp_path)
            except OSError:
                pass
