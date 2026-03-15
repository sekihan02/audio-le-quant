# audio-le-quant

[![CI](https://github.com/sekihan02/audio-le-quant/actions/workflows/ci.yml/badge.svg)](https://github.com/sekihan02/audio-le-quant/actions/workflows/ci.yml)

`audio-le-quant` は、量子化を体感的に学ぶための PySide6 アプリです。
単純な PCM 波形を生成するか WAV を読み込み、線形量子化や μ-law を適用して、元の波形、復元後の波形、誤差波形、保存サイズの違いを見比べられます。さらに、学習用の独自形式 `.alq` に保存し、あとから復元し直すこともできます。

このプロジェクトでは、量子化処理だけでなく、WAV の RIFF ヘッダ処理と `.alq` のヘッダ処理もライブラリ任せにせず手書きで実装しています。GUI は PySide6 を使いますが、音声フォーマットの中核ロジックはスクラッチ実装です。

## このプロジェクトで学べること

- 16bit PCM がなぜ大きいのか
- 振幅の段数を減らすとはどういうことか
- μ-law が小さい音に細かい精度を回す仕組み
- 圧縮して保存するデータと、復元後の PCM が別物であること

## 主な機能

- `sine` / `square` / `saw` / `noise` 波形の生成
- 8bit / 16bit PCM WAV の読み込み
- 1〜16bit の線形量子化
- `mu` を調整できる μ-law 圧伸
- PySide6 画面上での波形比較と誤差表示
- 復元 WAV の書き出し
- `.alq` の保存と再読み込み
- QtMultimedia が利用可能なら簡易再生

## 必要環境

- Python 3.11 以上を推奨
- `PySide6`

## 起動方法

依存関係を入れてからアプリを起動します。

```bash
python3 -m pip install --user -r requirements.txt
python3 main.py
```

オフスクリーンの簡易起動確認もできます。

```bash
QT_QPA_PLATFORM=offscreen AUDIO_LE_QUANT_AUTOCLOSE_MS=200 python3 main.py
```

## テスト

コアロジックは `unittest` で確認できます。画面を立ち上げなくても、WAV の入出力と `.alq` の往復を検証できます。

```bash
python3 -m unittest discover -s tests
```

## GitHub Actions

このリポジトリには次のワークフローを入れています。

- `CI`: `push` / `pull_request` / 手動実行で、`unittest` とオフスクリーン起動確認を実行
- `Release`: `v*` タグの push で GitHub Release を自動作成し、ソース ZIP を添付

リリースを作るときは、たとえば次のようにタグを push します。

```bash
git tag v0.1.0
git push origin v0.1.0
```

## 構成

- `audio_le_quant/audio.py`: PCM 波形の生成と WAV の入出力
- `audio_le_quant/quantization.py`: 線形量子化、μ-law、誤差評価
- `audio_le_quant/alq_format.py`: 独自 `.alq` 形式の保存と復元
- `audio_le_quant/widgets.py`: 波形表示用ウィジェット
- `audio_le_quant/app.py`: PySide6 デスクトップアプリ本体
- `main.py`: 起動用エントリーポイント。必要なら同梱の共有ライブラリを先読み

## 補足

- 画面表示には `PySide6` が必要です。
- コア処理はあえて `numpy`、`math`、`random`、`wave`、`struct` に頼らず、生のサンプル列やバイト列を自前で処理しています。
- `.alq` は学習用の独自形式であり、実用コーデックではありません。
