from __future__ import annotations

import ctypes
import os
from pathlib import Path


def _preload_linux_runtime_libs() -> None:
    """PySide6 が必要とする共有ライブラリを、同梱済みなら先に読み込む。"""

    if os.name != "posix":
        return

    lib_dir = Path(__file__).resolve().parent / "vendor" / "sysroot" / "usr" / "lib" / "x86_64-linux-gnu"
    if not lib_dir.exists():
        return

    for lib_name in ("libxkbcommon.so.0", "libEGL.so.1"):
        lib_path = lib_dir / lib_name
        if lib_path.exists():
            ctypes.CDLL(str(lib_path), mode=ctypes.RTLD_GLOBAL)


_preload_linux_runtime_libs()

from audio_le_quant.app import main


if __name__ == "__main__":
    raise SystemExit(main())
