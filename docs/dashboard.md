# 段階4: Streamlit Webアプリの検証

実行日: 2026-10-11（日本時間）。アクセス: http://localhost:8501 。

## 実装

商品コードと商品名を表示する30商品の選択、直近7日実績、LightGBM・ベースラインの翌7日合計予測、過去90日の日次販売実績グラフを実装。

PostgreSQLから2011-09-10〜2011-12-08の2,700行（30商品×90日）を読み、保存済み`final_model.txt`で実際に推論。未来の日別予測を作らない。Web画面から学習・発注・データ更新は行わない。

下段は全体／選択商品のテストMAE・WAPEと、仮定の現在庫・安全在庫による補充シミュレーション。全体のLightGBMがベースラインを下回った事実を、商品別評価を表示した場合も記載。未来予測には完全な実績がないこと、評価モデルと再学習済み最終モデルの違いを明示。

## 検証結果

- Docker Composeでアプリを起動。HTTP `/_stcore/health` は `ok`。
- pytest: **53 passed、skipなし（2.74秒）**。StreamlitとAltair間の非推奨APIによる警告1件があるが、グラフ表示・操作テストは成功。
- AppTestで全30商品の切り替えを実行。商品コード・商品名の選択とKPIの実績・予測が保存モデルの予測結果と一致。
- 全体MAE 274.01 / 206.67、WAPE 57.41% / 43.30%が段階3の実測評価と一致。商品別への切り替えでも指標が保存評価と一致。
- 現在庫の変更、安全在庫の変更、LightGBM／ベースラインの切り替えで推奨補充数を再計算。十分な現在庫で0となることと端数切り上げを検証。
- 学習成果物がない場合の案内表示も検証。
- 実Chromeで1280px幅・390px幅を確認。横方向にはみ出しなし。PCの3つのKPIは横並び、390pxでは縦並び。グラフと下段パネルも表示を確認。
- アプリ検証後に`verify_model.py`で評価用モデルの予測・指標と最終モデルの未来予測を再計算し、成果物との一致を確認。再学習やテストによる調整は行っていない。

初期表示の商品20724の実例: 直近7日749個、LightGBM予測552.7個、ベースライン749個。現在庫300個、安全在庫100個、LightGBMを使用すると補充数353個（未丸め予測から計算）。

## 再確認

```sh
docker compose build
docker compose up -d app
docker compose run --rm --entrypoint pytest pipeline -q
docker compose run --rm --entrypoint python pipeline scripts/verify_model.py
```

データとモデルの準備手順は[README](../README.md)を参照。実データ未準備時は該当UI統合テストをskipする。

ブラウザの表示検証はホスト側でGoogle Chromeを使用する（Macでは標準のインストールパス、その他は`CHROME_PATH`で指定）。一時プロファイルで起動し、ユーザーの既存プロファイルは使用しない。

```sh
python3 scripts/verify_browser.py
```

生成スクリーンショットは`artifacts/desktop_dashboard.png`、`artifacts/mobile_dashboard.png`（Git対象外）。テスト成果物・モデル・元データ・認証情報をGitに含めない。
