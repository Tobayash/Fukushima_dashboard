# Fukushima Recovery Indicator App

福島県の復興関連公開資料から指標を取得し、可視化する Streamlit アプリの初期雛形です。

## 目的
- 福島県全体と双葉郡8町村の復興指標を継続的に整理する
- 復興庁・福島県・各自治体・県民健康調査の**公開集計**を利用する
- 将来的に HTML / CSV / Excel / PDF の複数取得経路に対応する

## 対象エリア
- 福島県
- 広野町
- 楢葉町
- 富岡町
- 川内村
- 大熊町
- 双葉町
- 浪江町
- 葛尾村

## 初版で実装する指標
1. 居住率
2. 現住人口
3. WBC受検者数

## データ方針
- **公開集計のみ**を使用する
- 個票データ・申請制データは扱わない
- 取得時に出典URL、取得日時、対象期間を保存する

## ディレクトリ構成
```text
fukushima_recovery_app/
  app.py
  data_model.py
  requirements.txt
  README.md
  .gitignore
  extractors/
    __init__.py
    common.py
    reconstruction.py
    fhms.py
  data/
    raw/
    processed/
  docs/
    codex_prompts.md
```

## セットアップ
```bash
py -3.10 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## 起動前の注意
- `app.py` などで `from __future__ import annotations` を使っているため、Python 3.6 では起動できません。少なくとも Python 3.10 以上で仮想環境を作成してください。

## データモデル
縦持ちの tidy 形式を基本とします。

必須列:
- `indicator_id`
- `indicator_name`
- `area_id`
- `area_name`
- `period`
- `value`
- `unit`
- `source_name`
- `source_url`
- `retrieved_at`
- `notes`

## 実装方針
### 1. 抽出器をソースごとに分ける
- `extractors/reconstruction.py` : 復興庁・福島県の行政復興指標
- `extractors/fhms.py` : 県民健康調査・WBC 系公開集計

### 2. 取得経路を分ける
- HTML から直接取得できるもの
- CSV / Excel のダウンロード
- PDF から表抽出が必要なもの
- 手確認が必要なもの

### 3. まずは手動投入と自動取得を併用する
初版では、取得が不安定な PDF 指標は CSV 化して `data/raw/` に置き、
整形だけコードで行う方式でも十分です。

## Codex への依頼のしかた
まずは以下の順で依頼すると進めやすいです。

1. この README を読み込ませる
2. `app.py` を改善して UI を作らせる
3. `reconstruction.py` に居住率取得ロジックを実装させる
4. `fhms.py` に WBC 公開集計の整形処理を実装させる
5. グラフ、期間フィルタ、CSV 出力を追加させる

## 最初に Codex へ投げる依頼文
`docs/codex_prompts.md` を参照してください。
