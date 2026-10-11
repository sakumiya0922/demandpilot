# 再現手順と最終検証

## 通常の初回実行

[READMEの初回実行](../README.md#初回実行)を順番に実行する。必要なのはDocker Desktop（またはDocker Engine＋Compose）、ソースコード、初回取得時のインターネット接続。PythonやPostgreSQLをホストにインストールする必要はない。

1. `.env.example`から、既存ファイルを上書きせず`.env`を用意する。
2. イメージをビルドし、DBを起動・初期化する。
3. `prepare-data`で元ZIP・Excelを取得し、品質レポートとDBを作る。
4. `train`で固定された候補を検証データだけで選び、テスト評価・最終モデル・未来予測を保存する。
5. `predict`で保存済みモデルから予測を再生成する。
6. pytestとモデル照合を実行する。
7. アプリを起動し、商品・在庫入力を切り替える。

`init-db`は空テーブルの作成、`check-db`は接続確認で、どちらもモデルを作らない。`train`は未来予測CSVも作るが、独立した推論コマンドを確認するため`predict`も実行する。

## 既存環境を保持して初期状態を検証する

既存のDBや成果物を使い回さず、Git追跡ファイルだけを別ディレクトリへ展開する。名前付きボリューム、ネットワーク、イメージ、元データ、モデルを分離する。現在のサービスを停止する必要はない。

以下はプロジェクト直下から実行する。GitのHEADにあるコードを使用するため、未コミットのコード変更は含まれない。ポート18501が使用中なら、再現環境の`.env`だけを別の値へ変更する。

```sh
DP_REPRO_DIR=$(mktemp -d "${TMPDIR:-/tmp}/demandpilot-repro.XXXXXX")
git archive HEAD | tar -x -C "$DP_REPRO_DIR"
cd "$DP_REPRO_DIR"

cp .env.example .env
# dotenvでは後の指定が優先される。元プロジェクトの.envは変更しない
printf '\nSTREAMLIT_PORT=18501\n' >> .env

cat > compose.repro.yaml <<'YAML'
services:
  pipeline:
    image: demandpilot-stage5-repro:local
  app:
    image: demandpilot-stage5-repro:local
YAML

docker compose -p demandpilot-stage5-repro -f compose.yaml -f compose.repro.yaml build
docker compose -p demandpilot-stage5-repro -f compose.yaml -f compose.repro.yaml up -d db
docker compose -p demandpilot-stage5-repro -f compose.yaml -f compose.repro.yaml run --rm pipeline init-db
docker compose -p demandpilot-stage5-repro -f compose.yaml -f compose.repro.yaml run --rm pipeline prepare-data
docker compose -p demandpilot-stage5-repro -f compose.yaml -f compose.repro.yaml run --rm pipeline train
docker compose -p demandpilot-stage5-repro -f compose.yaml -f compose.repro.yaml run --rm pipeline predict
docker compose -p demandpilot-stage5-repro -f compose.yaml -f compose.repro.yaml run --rm --entrypoint pytest pipeline -q
docker compose -p demandpilot-stage5-repro -f compose.yaml -f compose.repro.yaml run --rm --entrypoint python pipeline scripts/verify_model.py
docker compose -p demandpilot-stage5-repro -f compose.yaml -f compose.repro.yaml up -d app
```

アクセス先は http://localhost:18501 。固定プロジェクト名`demandpilot-stage5-repro`はこの検証専用。同名環境が既にある場合、別のプロジェクト名とイメージ名を使用して空のDBから検証する。現在の標準環境は`demandpilot`であり別のボリュームを使う。

終了時は再現環境のディレクトリで以下を実行する。検証用のボリューム・ファイルも削除しない。

```sh
docker compose -p demandpilot-stage5-repro -f compose.yaml -f compose.repro.yaml down
```

## データ再実行前後の比較

以下の`prepare-data`は専用テーブルを置き換える。既存状態を保持する必要がある場合は、上記の独立環境で実行する。独立環境では各コマンドに同じ`-p`・`-f`を付ける。

```sh
docker compose run --rm --entrypoint python pipeline scripts/verify_snapshot.py before
docker compose run --rm pipeline prepare-data
docker compose run --rm --entrypoint python pipeline scripts/verify_snapshot.py after
```

3テーブルの全行を主キー順にハッシュ化し、件数・内容・品質レポートを比較する。全30商品が373日を持つこと、商品×日付の重複がないこと、全11,190行がSQLの取引再集計と一致することも確認する。品質レポートのハッシュには実行設定も含まれる。

## 保存モデルと画面の検証

`scripts/verify_model.py`は現在のDBハッシュ、評価モデルによる予測、MAE/WAPE、ラベル期間の非重複、最終モデルによる30商品の未来予測を保存成果物と照合する。読み取りだけでモデルを調整しない。

UI統合テストは実データ・モデル準備後に実行する。商品切り替え、モデル指標の一致、在庫変更による補充再計算を確認する。モデル・データ未準備ではUI関連テストがskipするため、skipなしの53件成功を完成状態の確認とする。

Chromeでの表示検証はホスト側で、標準環境のアプリが起動した状態で実行する。

```sh
python3 scripts/verify_browser.py
```

ChromeのパスはMacの標準パス。その他は`CHROME_PATH`で指定する。検証対象はlocalhost:8501、1280pxと390px。スクリーンショットは`artifacts`へ生成する。ChromeとホストPythonが必要なこの確認は補助的で、通常の実行やpytestには不要。

## よくある確認箇所

| 状況 | 確認・対応 |
| --- | --- |
| Dockerへ接続できない | Docker Desktopを起動し、`docker compose ps`を確認 |
| 未準備の案内が表示される | `prepare-data`→`train`の順で実行できたか確認 |
| ポートが使用中 | `.env`の`STREAMLIT_PORT`を変更し、アプリを再起動 |
| DB認証に失敗 | 既存DBのユーザー・パスワードと`.env`を合わせる。既存ボリュームでは環境変数変更だけでDB認証は変更されない |
| 変更が画面に出ない | コード変更は再ビルド、モデル変更はキャッシュ待ちまたは`docker compose restart app` |
| UIテストがskip | 元データとモデルを先に準備したか確認 |
| 取得に失敗 | UCIへの接続を確認し再実行。成功した元ZIPはキャッシュされる |

## 最終検証結果

2026-10-11（日本時間）、段階4コミット`1af70aa`のGit追跡ファイルだけを独立ディレクトリへ展開して確認。元データ・モデル・既存DBを持ち込まず、新規のボリューム`demandpilot-stage5-repro_postgres_data`を使用した。Dockerの既存ビルドキャッシュは再利用している。

| 確認 | 実測結果 |
| --- | --- |
| 初回ビルド・空DB初期化 | 成功 |
| UCIからの新規取得 | 541,909行、元Excelの既知SHA-256と一致 |
| DB登録 | products 30、transactions 526,107、daily_sales 11,190 |
| 再処理前後 | 3テーブル全行ハッシュ・件数・品質レポートが一致 |
| SQL再集計 | 全11,190日次行で不一致0、30商品×373日、重複0 |
| 固定済みモデルの学習再現 | 学習7,200、検証240、テスト150、最終学習10,170行 |
| テストLightGBM | MAE274.009734236019、WAPE57.40587744825674% |
| テストベースライン | MAE206.66666666666666、WAPE43.29729880722925% |
| 元の学習成果物との比較 | モデル・条件・評価・予測等10ファイルすべてバイト単位で一致 |
| 保存モデルでの独立推論 | 30商品、2011-12-09〜15の合計。照合成功 |
| 独立環境pytest | **53 passed、skipなし、2.57秒**（既存環境も53 passed、2.44秒） |
| Streamlit | 独立環境のHTTPヘルスチェック`ok`、実DB・実モデルのUI統合テスト成功 |
| Chrome表示 | 標準環境の1280px／390px幅で正常表示、横はみ出しなし |
| 既存環境の保持 | 全DB行・元の品質レポート・保存モデル・予測を読み取り照合して一致 |
| Git確認 | 実認証情報・元ZIP／Excel・生成モデル・生成予測は追跡候補外。一般的なキー形式の検出なし |

pytestの警告1件はStreamlit内部のAltair非推奨APIによるもので、失敗やskipはない。モデル設定・候補・評価期間・特徴量は変更していない。既知のテストを見た調整は実施していない。

検証専用のコンテナは停止し、検証用DBボリュームとファイルも保持する。既存アプリはlocalhost:8501で稼働を継続する。段階5は文書・画面資料・除外設定の整備で、まだコミットしない。
