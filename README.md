# DemandPilot — 需要予測を題材としたデータ基盤・機械学習システムの開発

> **職務経歴書との対応**：個人開発でデータベース構築・Dockerによる開発環境の構築・機械学習モデルの管理／運用に関する技術を学ぶことが目的です。需要予測は、これらを一連の流れで実装するための題材として選びました。**モデルの高精度化を達成したプロジェクトではありません。**

## まず知ってほしいこと

- **何を作った？** 公開小売データをPostgreSQLに保存し、LightGBMで翌7日間の販売数量を予測してStreamlitで表示するローカルWebアプリです。仮の現在庫・安全在庫を入力すると簡易的な補充数も表示します。
- **何を学んだ？** PythonからDBを作成・利用すること、Docker ComposeでDBとアプリを動かすこと、モデルの学習・保存・推論を分けることです。
- **現在の範囲は？** コードと実行手順、評価・テストは公開。実在庫連携、クラウド公開、自動発注はしていません。MLflowによる実験管理は別PRで検証中で、`main`の完成機能ではありません。

![DemandPilotの画面](docs/images/dashboard-desktop.png)

## 処理の流れ（4段階）

1. **データを用意する**：公開取引データを取得・整形し、PostgreSQLに登録する。
2. **予測する**：過去の売上から特徴量を作り、LightGBMを学習・評価する。
3. **画面で見る**：保存したモデルの予測と、過去の売上をStreamlitに表示する。
4. **動作を確かめる**：pytestでデータ処理・モデル・画面の基本動作を確認する。

| やりたいこと | 主な技術 | コードを見る場所 |
| --- | --- | --- |
| データ保存 | Python・PostgreSQL | [データ処理](src/demandpilot/data/pipeline.py)・[DB操作](src/demandpilot/db.py) |
| 学習・評価 | LightGBM | [学習コード](src/demandpilot/modeling/train.py) |
| Web画面 | Streamlit | [画面コード](app/streamlit_app.py) |
| コンテナ起動 | Docker Compose | [compose.yaml](compose.yaml) |

詳しい技術をすべて読む必要はありません。[理解のための簡単な解説](docs/learning_guide.md)から順に説明しています。

## 評価結果（公表済みのテスト）

| 指標 | LightGBM | 直近7日と同じとする単純予測 |
| --- | ---: | ---: |
| MAE（翌7日間の販売数量、個） | 274.01 | **206.67** |
| WAPE | 57.41% | **43.30%** |

**LightGBMの方が悪い結果でした。** データ処理から学習・評価、Web表示までを連携させることが主目的であり、予測精度が高いと主張するものではありません。詳細は[評価記録](docs/evaluation.md)を参照してください。

## 初回実行

Docker Desktopとインターネット接続が必要です。初回はデータ取得とモデル学習を実施します。ホストPCにPythonやPostgreSQLを入れる必要はありません。

```bash
git clone https://github.com/sakumiya0922/demandpilot.git
cd demandpilot
cp .env.example .env
docker compose build
docker compose up -d db
docker compose run --rm pipeline init-db
docker compose run --rm pipeline prepare-data
docker compose run --rm pipeline train
docker compose run --rm --entrypoint pytest pipeline -q
docker compose up -d app
```

ブラウザで **http://localhost:8501** にアクセスしてください。データは2010〜2011年の公開データで、現在日の予測ではありません。終了時は`docker compose down`で停止できます。

## 詳細・制約

- [もう少し技術的な解説](docs/learning_guide.md)
- [元の詳細README（検証時の記録）](docs/technical_reference.md)
- [データの前処理](docs/data_preparation.md)／[評価の詳細](docs/evaluation.md)／[機能の制約](docs/limitations.md)／[再現手順](docs/reproducibility.md)
- [公開前チェックリスト](docs/publication_checklist.md)

**データ出典：** UCI Machine Learning Repository, [Online Retail](https://archive.ics.uci.edu/dataset/352/online%2Bretail)（CC BY 4.0）。元データ・モデル成果物・秘密情報はこのリポジトリには含みません。
