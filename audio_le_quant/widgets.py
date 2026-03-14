from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget


class WaveformView(QWidget):
    def __init__(self, title: str, accent: str, auto_gain: bool = False, parent: QWidget = None):
        super().__init__(parent)
        self._title = title
        self._accent = QColor(accent)
        self._auto_gain = auto_gain
        self._samples = []
        self._note = "まだ信号が読み込まれていません。"
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_samples(self, samples: List[float], note: str = "") -> None:
        self._samples = list(samples)
        self._note = note or "先頭チャンネルのプレビューを表示しています。"
        self.update()

    def clear(self, note: str) -> None:
        self._samples = []
        self._note = note
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        background = QLinearGradient(rect.topLeft(), rect.bottomRight())
        background.setColorAt(0.0, QColor("#fff7ed"))
        background.setColorAt(1.0, QColor("#f4efe6"))
        painter.setBrush(background)
        painter.setPen(QPen(QColor("#d7c8b6"), 1))
        painter.drawRoundedRect(rect, 18, 18)

        title_rect = rect.adjusted(14, 10, -14, -10)
        painter.setPen(QColor("#5f4735"))
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignTop, self._title)

        content = rect.adjusted(14, 34, -14, -16)
        mid_y = content.center().y()
        painter.setPen(QPen(QColor("#e4d6c3"), 1))
        for step in range(5):
            ratio = step / 4.0
            y = content.top() + int(content.height() * ratio)
            painter.drawLine(content.left(), y, content.right(), y)
        painter.drawLine(content.left(), mid_y, content.right(), mid_y)

        painter.setPen(QColor("#8e7b68"))
        painter.drawText(content.adjusted(0, 0, 0, -4), Qt.AlignLeft | Qt.AlignBottom, self._note)

        if not self._samples:
            return

        peak = max(abs(sample) for sample in self._samples)
        scale = peak if self._auto_gain and peak > 1e-6 else 1.0
        if scale <= 0.0:
            scale = 1.0

        width = max(1, content.width())
        height = max(1, content.height())
        path = QPainterPath()

        # 画面幅に合わせてサンプルを間引き、軽い描画で波形を見せる。
        for x in range(width):
            index = int((x / float(width - 1 or 1)) * (len(self._samples) - 1))
            sample = self._samples[index] / scale
            y = mid_y - (sample * ((height / 2.0) - 6))
            point_x = content.left() + x
            if x == 0:
                path.moveTo(point_x, y)
            else:
                path.lineTo(point_x, y)

        glow = QColor(self._accent)
        glow.setAlpha(70)
        painter.setPen(QPen(glow, 6))
        painter.drawPath(path)
        painter.setPen(QPen(self._accent, 2))
        painter.drawPath(path)


class InfoCard(QWidget):
    def __init__(self, title: str, parent: QWidget = None):
        super().__init__(parent)
        self.title = QLabel(title)
        self.title.setObjectName("CardTitle")
        self.body = QLabel("")
        self.body.setWordWrap(True)
        self.body.setObjectName("CardBody")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.body)
