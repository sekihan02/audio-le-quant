# audio-le-quant

`audio-le-quant` は、量子化を体感的に学ぶための PySide6 アプリです。  
単純な PCM 波形を生成するか WAV を読み込み、線形量子化や μ-law を適用して、元波形・復元波形・誤差波形・保存サイズを見比べられます。さらに、学習用の独自形式 `.alq` に保存して、あとから復元し直すこともできます。

## このプロジェクトで学べること

- 16bit PCM がなぜ大きいのか
- 振幅の段数を減らすとはどういうことか
- μ-law が小さい音に細かい精度を回す仕組み
- 圧縮用 payload と復元後 PCM が別物であること

## 主な機能

- `sine` / `square` / `saw` / `noise` の生成
- 8bit / 16bit PCM WAV の読み込み
- 1〜16bit の線形量子化
- `mu` を調整できる μ-law 圧伸
- PySide6 GUI での波形比較と誤差表示
- 復元 WAV の書き出し
- `.alq` の保存と再読み込み
- QtMultimedia が利用可能なら簡易再生

## 起動方法

1. 依存関係を入れます。

```bash
python3 -m pip install --user -r requirements.txt
```

2. アプリを起動します。

```bash
python3 main.py
```

## テスト

コアロジックは `unittest` で確認できます。GUI を立ち上げなくても、WAV 入出力と `.alq` の往復を検証できます。

```bash
python3 -m unittest discover -s tests
```

オフスクリーンの簡易起動確認もできます。

```bash
QT_QPA_PLATFORM=offscreen AUDIO_LE_QUANT_AUTOCLOSE_MS=200 python3 main.py
```

## 構成

- `audio_le_quant/audio.py`: PCM 波形生成と WAV 入出力
- `audio_le_quant/quantization.py`: 線形量子化、μ-law、誤差評価
- `audio_le_quant/alq_format.py`: 独自 `.alq` 形式の保存と復元
- `audio_le_quant/widgets.py`: 波形表示ウィジェット
- `audio_le_quant/app.py`: PySide6 デスクトップアプリ本体
- `main.py`: 起動入口。必要なら同梱共有ライブラリを先読み

## 補足

- GUI には `PySide6` が必要です。
- コア処理はあえて `numpy` を使わず、生のサンプル列に近い形で実装しています。
- `.alq` は学習用の独自形式であり、実用コーデックではありません。
