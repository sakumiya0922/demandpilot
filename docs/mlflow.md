# MLflow（ローカル実験管理）

この機能は、DemandPilotの既存モデル・評価処理を変更せずに、
MLflow上で学習条件・検証指標・テスト指標・成果物を確認するためのものです。
MLflowはポート5000で **ローカルPCにのみ公開** します。

## 起動・確認

```sh
docker compose up -d mlflow
docker compose run --rm pipeline train
```

ブラウザで http://localhost:5000 を開き、`DemandPilot` の実験を表示します。

- `candidate-N`: LightGBMの各候補のパラメータと**検証データ**のMAE/WAPE。テスト結果は記録しません。
- `selected-model-and-final-refit`: 選択済み設定、LightGBMと直近7日ベースラインの検証・テストMAE/WAPE、および生成済みファイル。
- Artifacts > `training_outputs`: `evaluation_model.txt`（テスト評価した学習モデル）、`final_model.txt`（将来予測用に再学習したモデル）、`evaluation.json`、`training_conditions.json`、各種CSV。

**MLflow追加によって予測精度は変わりません。** 既存のテストではLightGBMがベースラインに劣る結果もそのまま記録します。テストをチューニングには使用しません。

- 学習記録はDockerの`mlflow_data`ボリューム（SQLiteメタデータとアーティファクト）に永続化します。
- `docker compose down`では保存データは残ります。`docker compose down -v`は他のDBデータも消すため通常は使いません。
- Pythonから直接学習する場合、`MLFLOW_TRACKING_URI`を設定しない限りMLflow記録は行われません。
- Docker Compose経由では`MLFLOW_TRACKING_URI=http://mlflow:5000`が設定されます。MLflowが利用できなければ学習結果の記録工程でエラーとなります。
- `artifacts/ml`への従来のファイル保存は引き続き行われます。MLflowは結果・履歴を比較するための追加機能です。

## 今後の発展

モデルをMLflow Model Registryへ登録したり、MLflowのモデルURIから推論する機能は未実装です。現段階のUIは従来の`final_model.txt`を参照します。
