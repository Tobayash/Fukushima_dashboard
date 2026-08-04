# Codex に投げる依頼文例

## 1. 最初の依頼

```text
このリポジトリは福島県復興指標アプリの初期雛形です。
README.md を読んで要件を理解したうえで、以下を実装してください。

- Streamlit アプリ app.py の改善
- 居住率、現住人口、WBC受検者数の3指標を表示できるようにする
- extractors/reconstruction.py に居住率取得関数を実装する
- extractors/fhms.py に WBC受検者数の取得または整形処理を実装する
- 取得失敗時の例外処理とログ出力を追加する
- data/processed/master_indicators.csv に統合保存する関数を追加する

注意:
- 公開集計のみを使う
- 個票データや申請制データは扱わない
- source_url, retrieved_at, period を必ず保存する
```

## 2. 次の依頼

```text
居住率について、復興庁または福島県の公開ページから市町村別の表を取得してください。
もし PDF しかない場合は、PDF から表を抽出する補助関数を別ファイルに分けて作成してください。
そのうえで indicator_id='resident_rate' として tidy 形式に整形してください。
```

## 3. UI 改善依頼

```text
app.py を改善して、以下を追加してください。
- 期間フィルタ
- 指標ごとの折れ線グラフまたは棒グラフ
- CSV ダウンロードボタン
- 出典URLを表示する expander
```
