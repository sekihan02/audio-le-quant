from __future__ import annotations

import math
import os
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .alq_format import read_alq, write_alq
from .audio import AudioClip, generate_signal, read_wav, write_wav
from .player import WavePlayer
from .quantization import (
    QuantizedPayload,
    build_learning_summary,
    calculate_metrics,
    linear_quantize,
    mu_law_quantize,
)
from .widgets import InfoCard, WaveformView

APP_STYLE = """
QMainWindow {
    background: #f4efe6;
}
QWidget {
    color: #2f2a25;
    font-size: 13px;
}
QFrame#Hero {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #103c45, stop:0.55 #1f6a6a, stop:1 #d36b32);
    border-radius: 24px;
}
QLabel#HeroTitle {
    color: #fffaf4;
    font-size: 28px;
    font-weight: 700;
}
QLabel#HeroBody {
    color: #fff1e4;
    font-size: 13px;
}
QGroupBox {
    background: rgba(255, 251, 245, 0.9);
    border: 1px solid #d8cab8;
    border-radius: 18px;
    margin-top: 14px;
    padding: 12px;
    font-weight: 700;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #684c39;
}
QPushButton {
    background: #1f6a6a;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 12px;
    font-weight: 700;
}
QPushButton:hover {
    background: #2a8585;
}
QPushButton#SecondaryButton {
    background: #d36b32;
}
QPushButton#SecondaryButton:hover {
    background: #e27a42;
}
QComboBox, QSpinBox, QDoubleSpinBox {
    background: #fffaf4;
    border: 1px solid #d3c2af;
    border-radius: 8px;
    padding: 6px 8px;
}
QLabel#CardTitle {
    font-size: 15px;
    font-weight: 700;
    color: #684c39;
}
QLabel#CardBody {
    background: rgba(255, 250, 244, 0.94);
    border: 1px solid #d8cab8;
    border-radius: 18px;
    padding: 14px;
    line-height: 1.35em;
}
QStatusBar {
    background: #f1e7d9;
}
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("audio-le-quant")
        self.resize(1320, 860)

        self.source_clip: Optional[AudioClip] = None
        self.source_label = "生成音源"
        self.processed_payload: Optional[QuantizedPayload] = None
        self.decoded_only_mode = False
        self.player = WavePlayer()

        self._build_ui()
        self._wire_actions()
        self._refresh_codec_controls()
        self._generate_source()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.player.cleanup()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        self.setStatusBar(QStatusBar())

        about_action = QAction("About audio-le-quant", self)
        about_action.setText("audio-le-quant について")
        about_action.triggered.connect(self._show_about)
        self.menuBar().addAction(about_action)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(18)
        self.setCentralWidget(root)

        sidebar = QWidget()
        sidebar.setFixedWidth(340)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(14)

        sidebar_layout.addWidget(self._build_source_group())
        sidebar_layout.addWidget(self._build_quant_group())
        sidebar_layout.addWidget(self._build_action_group())
        sidebar_layout.addStretch(1)

        main_panel = QWidget()
        main_layout = QVBoxLayout(main_panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)
        main_layout.addWidget(self._build_hero())

        waves = QWidget()
        wave_grid = QGridLayout(waves)
        wave_grid.setContentsMargins(0, 0, 0, 0)
        wave_grid.setHorizontalSpacing(14)
        wave_grid.setVerticalSpacing(14)

        self.original_view = WaveformView("元の波形 / 基準", "#1f6a6a")
        self.processed_view = WaveformView("量子化後 / 復元波形", "#d36b32")
        self.error_view = WaveformView("誤差波形", "#9a3d2c", auto_gain=True)

        wave_grid.addWidget(self.original_view, 0, 0)
        wave_grid.addWidget(self.processed_view, 0, 1)
        wave_grid.addWidget(self.error_view, 1, 0, 1, 2)
        main_layout.addWidget(waves, 3)

        cards = QWidget()
        cards_layout = QGridLayout(cards)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setHorizontalSpacing(14)

        self.source_card = InfoCard("信号情報")
        self.metrics_card = InfoCard("評価指標")
        self.learning_card = InfoCard("学習メモ")

        cards_layout.addWidget(self.source_card, 0, 0)
        cards_layout.addWidget(self.metrics_card, 0, 1)
        cards_layout.addWidget(self.learning_card, 1, 0, 1, 2)
        main_layout.addWidget(cards, 2)

        layout.addWidget(sidebar)
        layout.addWidget(main_panel, 1)

    def _build_hero(self) -> QWidget:
        hero = QFrame()
        hero.setObjectName("Hero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(24, 22, 24, 22)
        hero_layout.setSpacing(6)

        title = QLabel("audio-le-quant")
        title.setObjectName("HeroTitle")
        body = QLabel(
            "PCM を学ぶための量子化ラボです。WAV を生成または読み込みし、"
            "線形量子化や μ-law で崩したあと、波形・誤差・保存サイズを比較できます。"
        )
        body.setWordWrap(True)
        body.setObjectName("HeroBody")
        hero_layout.addWidget(title)
        hero_layout.addWidget(body)
        return hero

    def _build_source_group(self) -> QWidget:
        group = QGroupBox("1. 音源")
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.waveform_combo = QComboBox()
        self.waveform_combo.addItems(["sine", "square", "saw", "noise"])
        self.frequency_spin = QDoubleSpinBox()
        self.frequency_spin.setRange(10.0, 8000.0)
        self.frequency_spin.setDecimals(1)
        self.frequency_spin.setSingleStep(10.0)
        self.frequency_spin.setValue(440.0)
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.1, 12.0)
        self.duration_spin.setDecimals(2)
        self.duration_spin.setSingleStep(0.1)
        self.duration_spin.setValue(1.5)
        self.sample_rate_combo = QComboBox()
        self.sample_rate_combo.addItems(["8000", "16000", "22050", "44100"])
        self.sample_rate_combo.setCurrentText("44100")
        self.amplitude_spin = QDoubleSpinBox()
        self.amplitude_spin.setRange(0.05, 1.0)
        self.amplitude_spin.setDecimals(2)
        self.amplitude_spin.setSingleStep(0.05)
        self.amplitude_spin.setValue(0.8)
        self.channels_spin = QSpinBox()
        self.channels_spin.setRange(1, 2)
        self.channels_spin.setValue(1)

        self.generate_button = QPushButton("生成する")
        self.load_button = QPushButton("WAVを開く...")
        self.load_alq_button = QPushButton("ALQを開く...")
        self.load_button.setObjectName("SecondaryButton")
        self.load_alq_button.setObjectName("SecondaryButton")

        form.addRow("波形", self.waveform_combo)
        form.addRow("周波数 (Hz)", self.frequency_spin)
        form.addRow("長さ (秒)", self.duration_spin)
        form.addRow("サンプルレート", self.sample_rate_combo)
        form.addRow("振幅", self.amplitude_spin)
        form.addRow("チャンネル数", self.channels_spin)
        form.addRow(self.generate_button)
        form.addRow(self.load_button)
        form.addRow(self.load_alq_button)
        return group

    def _build_quant_group(self) -> QWidget:
        group = QGroupBox("2. 量子化")
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self.codec_combo = QComboBox()
        self.codec_combo.addItem("線形量子化", "linear")
        self.codec_combo.addItem("μ-law 圧伸", "mulaw")
        self.bit_depth_spin = QSpinBox()
        self.bit_depth_spin.setRange(1, 16)
        self.bit_depth_spin.setValue(8)
        self.mu_spin = QSpinBox()
        self.mu_spin.setRange(2, 1024)
        self.mu_spin.setValue(255)

        form.addRow("方式", self.codec_combo)
        form.addRow("量子化ビット数", self.bit_depth_spin)
        form.addRow("μ 値", self.mu_spin)
        return group

    def _build_action_group(self) -> QWidget:
        group = QGroupBox("3. 操作")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self.apply_button = QPushButton("量子化を適用")
        self.play_source_button = QPushButton("元音声を再生")
        self.play_processed_button = QPushButton("復元音声を再生")
        self.play_processed_button.setObjectName("SecondaryButton")
        self.save_wav_button = QPushButton("復元 WAV を保存...")
        self.save_alq_button = QPushButton(".alq を保存...")
        self.save_alq_button.setObjectName("SecondaryButton")

        layout.addWidget(self.apply_button)
        layout.addWidget(self.play_source_button)
        layout.addWidget(self.play_processed_button)
        layout.addWidget(self.save_wav_button)
        layout.addWidget(self.save_alq_button)

        if not self.player.available:
            self.play_source_button.setEnabled(False)
            self.play_processed_button.setEnabled(False)
            self.play_source_button.setToolTip("この環境では QtMultimedia が使えません。")
            self.play_processed_button.setToolTip("この環境では QtMultimedia が使えません。")

        return group

    def _wire_actions(self) -> None:
        self.waveform_combo.currentTextChanged.connect(self._sync_source_controls)
        self.codec_combo.currentIndexChanged.connect(self._refresh_codec_controls)
        self.generate_button.clicked.connect(self._generate_source)
        self.load_button.clicked.connect(self._load_wav)
        self.load_alq_button.clicked.connect(self._load_alq)
        self.apply_button.clicked.connect(self._apply_quantization)
        self.play_source_button.clicked.connect(self._play_source)
        self.play_processed_button.clicked.connect(self._play_processed)
        self.save_wav_button.clicked.connect(self._save_processed_wav)
        self.save_alq_button.clicked.connect(self._save_alq)

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "audio-le-quant について",
            "audio-le-quant は、量子化が PCM 音声に何を起こすかを学ぶための小さな PySide6 ラボです。",
        )

    def _sync_source_controls(self) -> None:
        is_noise = self.waveform_combo.currentText() == "noise"
        self.frequency_spin.setEnabled(not is_noise)

    def _refresh_codec_controls(self) -> None:
        codec = self.codec_combo.currentData()
        linear_mode = codec == "linear"
        self.bit_depth_spin.setEnabled(linear_mode)
        self.mu_spin.setEnabled(not linear_mode)

    def _generate_source(self) -> None:
        waveform = self.waveform_combo.currentText()
        frequency = self.frequency_spin.value()
        duration = self.duration_spin.value()
        sample_rate = int(self.sample_rate_combo.currentText())
        amplitude = self.amplitude_spin.value()
        channels = self.channels_spin.value()

        self.source_clip = generate_signal(
            waveform=waveform,
            frequency=frequency,
            duration_seconds=duration,
            sample_rate=sample_rate,
            amplitude=amplitude,
            channels=channels,
        )
        self.decoded_only_mode = False
        self.source_label = "生成音源: {0}".format(waveform)
        self.statusBar().showMessage("新しい音源を生成しました。", 4000)
        self._apply_quantization()

    def _load_wav(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "WAV を開く",
            os.getcwd(),
            "WAV ファイル (*.wav)",
        )
        if not path:
            return

        try:
            self.source_clip = read_wav(path)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "WAV を開けませんでした", str(error))
            return

        self.source_label = os.path.basename(path)
        self.decoded_only_mode = False
        self.statusBar().showMessage("WAV を読み込みました: {0}".format(self.source_label), 5000)
        self._apply_quantization()

    def _load_alq(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "ALQ を開く",
            os.getcwd(),
            "ALQ ファイル (*.alq)",
        )
        if not path:
            return

        try:
            self.processed_payload = read_alq(path)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "ALQ を開けませんでした", str(error))
            return

        self.source_clip = None
        self.decoded_only_mode = True
        self.source_label = os.path.basename(path)
        self._refresh_visuals()
        self.statusBar().showMessage("ALQ を読み込みました: {0}".format(self.source_label), 5000)

    def _apply_quantization(self) -> None:
        if self.source_clip is None:
            return

        codec = self.codec_combo.currentData()
        if codec == "linear":
            payload = linear_quantize(self.source_clip, self.bit_depth_spin.value())
        else:
            payload = mu_law_quantize(self.source_clip, mu=self.mu_spin.value())

        self.processed_payload = payload
        self._refresh_visuals()
        self.statusBar().showMessage("量子化が完了しました。", 3000)

    def _play_source(self) -> None:
        if self.source_clip is not None:
            self.player.play(self.source_clip)

    def _play_processed(self) -> None:
        if self.processed_payload is not None:
            self.player.play(self.processed_payload.processed_clip)

    def _save_processed_wav(self) -> None:
        if self.processed_payload is None:
            QMessageBox.warning(self, "保存できません", "先に量子化を実行してください。")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "復元 WAV を保存",
            os.path.join(os.getcwd(), "quantized.wav"),
            "WAV ファイル (*.wav)",
        )
        if not path:
            return

        try:
            write_wav(path, self.processed_payload.processed_clip, bit_depth=16)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "保存に失敗しました", str(error))
            return

        self.statusBar().showMessage("復元 WAV を保存しました: {0}".format(path), 5000)

    def _save_alq(self) -> None:
        if self.processed_payload is None:
            QMessageBox.warning(self, "保存できません", "先に量子化を実行してください。")
            return

        suffix = ".alq"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "ALQ を保存",
            os.path.join(os.getcwd(), "quantized{0}".format(suffix)),
            "ALQ ファイル (*.alq)",
        )
        if not path:
            return

        if not path.endswith(suffix):
            path += suffix

        try:
            write_alq(path, self.processed_payload)
        except Exception as error:  # noqa: BLE001
            QMessageBox.critical(self, "保存に失敗しました", str(error))
            return

        self.statusBar().showMessage("ALQ を保存しました: {0}".format(path), 5000)

    def _refresh_visuals(self) -> None:
        if self.processed_payload is None:
            return

        if self.decoded_only_mode or self.source_clip is None:
            preview_limit = min(4000, self.processed_payload.processed_clip.frame_count)
            processed_preview = self.processed_payload.processed_clip.preview_samples()[:preview_limit]
            self.original_view.clear("ALQ には元の PCM 波形は保存されていません。")
            self.processed_view.set_samples(
                processed_preview,
                note="{0} を復元した波形 | 先頭 {1} フレーム".format(self.source_label, preview_limit),
            )
            self.error_view.clear("誤差を見たい場合は、WAV を生成または読み込んでください。")

            codec_name = "線形量子化 {0}bit".format(self.processed_payload.bit_depth)
            if self.processed_payload.codec == "mulaw":
                codec_name = "μ-law, μ={0}".format(self.processed_payload.mu)

            clip = self.processed_payload.processed_clip
            self.source_card.body.setText(
                "\n".join(
                    [
                        "復元元: {0}".format(self.source_label),
                        "フレーム数: {0}".format(clip.frame_count),
                        "長さ: {0:.2f} 秒".format(clip.duration_seconds),
                        "サンプルレート / ch: {0} Hz / {1}".format(clip.sample_rate, clip.channels),
                    ]
                )
            )
            self.metrics_card.body.setText(
                "\n".join(
                    [
                        "方式: {0}".format(codec_name),
                        "圧縮 payload: {0} bytes".format(self.processed_payload.payload_bytes),
                        "元の PCM: ALQ には含まれません",
                        "復元 WAV の保存: 利用可能",
                    ]
                )
            )
            self.learning_card.body.setText(
                "\n".join(
                    [
                        "ALQ は、量子化コード列を詰めて保存する学習用フォーマットです。",
                        "開くと再生可能な波形は復元できますが、元の完全な PCM は戻りません。",
                        "ここに、圧縮された payload と復元後 PCM の違いが現れます。",
                    ]
                )
            )
            return

        preview_limit = min(4000, self.source_clip.frame_count)
        source_preview = self.source_clip.preview_samples()[:preview_limit]
        processed_preview = self.processed_payload.processed_clip.preview_samples()[:preview_limit]
        error_preview = [
            source_preview[index] - processed_preview[index] for index in range(preview_limit)
        ]
        codec_name = "線形量子化 {0}bit".format(self.processed_payload.bit_depth)
        if self.processed_payload.codec == "mulaw":
            codec_name = "μ-law, μ={0}".format(self.processed_payload.mu)

        self.original_view.set_samples(
            source_preview,
            note="{0} | {1} フレーム表示".format(self.source_label, preview_limit),
        )
        self.processed_view.set_samples(
            processed_preview,
            note="{0} | 先頭 {1} フレーム".format(codec_name, preview_limit),
        )
        error_peak = max(abs(sample) for sample in error_preview) if error_preview else 0.0
        self.error_view.set_samples(
            error_preview,
            note="誤差を自動拡大表示 | peak {0:.5f}".format(error_peak),
        )

        metrics = calculate_metrics(self.source_clip, self.processed_payload.processed_clip)
        summary = build_learning_summary(self.source_clip, self.processed_payload, metrics)

        self.source_card.body.setText(
            "\n".join(
                [
                    "ラベル: {0}".format(self.source_label),
                    "フレーム数: {0}".format(self.source_clip.frame_count),
                    "長さ: {0:.2f} 秒".format(self.source_clip.duration_seconds),
                    "サンプルレート / ch: {0} Hz / {1}".format(
                        self.source_clip.sample_rate,
                        self.source_clip.channels,
                    ),
                ]
            )
        )

        snr_text = "無限大" if math.isinf(metrics.snr_db) else "{0:.2f} dB".format(metrics.snr_db)
        self.metrics_card.body.setText(
            "\n".join(
                [
                    "方式: {0}".format(codec_name),
                    "RMSE: {0:.6f}".format(metrics.rmse),
                    "MAE: {0:.6f}".format(metrics.mean_abs_error),
                    "最大誤差: {0:.6f}".format(metrics.peak_error),
                    "SNR: {0}".format(snr_text),
                    "圧縮 payload: {0} bytes".format(self.processed_payload.payload_bytes),
                ]
            )
        )
        self.learning_card.body.setText(summary)


def main() -> int:
    app = QApplication.instance() or QApplication([])
    font = QFont("DejaVu Sans", 10)
    app.setFont(font)
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    autoclose_ms = os.getenv("AUDIO_LE_QUANT_AUTOCLOSE_MS")
    if autoclose_ms:
        QTimer.singleShot(int(autoclose_ms), app.quit)
    return app.exec()
