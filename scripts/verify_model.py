"""Recompute saved evaluation and inference against the current DB snapshot."""

import hashlib
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from demandpilot.features import build_features, feature_matrix
from demandpilot.modeling.data import load_daily_sales
from demandpilot.modeling.evaluate import metrics
from demandpilot.modeling.predict import infer


def main():
    directory = Path("artifacts/ml")
    metadata = json.loads((directory / "training_conditions.json").read_text())
    evaluation = json.loads((directory / "evaluation.json").read_text())
    daily, products = load_daily_sales()
    assert hashlib.sha256(daily.to_csv(index=False).encode()).hexdigest() == metadata["daily_sales_sha256"]
    features = build_features(daily, metadata["feature_windows"], metadata["horizon_days"])
    booster = lgb.Booster(model_file=str(directory / "evaluation_model.txt"))
    for name in ["train", "validation", "test"]:
        saved = pd.read_csv(directory / f"{name}_predictions.csv", dtype={"stock_code": str},
                            parse_dates=["sales_date", "target_start", "target_end"])
        joined = saved.merge(features, on=["stock_code", "sales_date"], suffixes=("_saved", ""), validate="one_to_one")
        assert len(joined) == evaluation["splits"][name]["rows"]
        np.testing.assert_allclose(joined["target_saved"], joined["target"])
        assert joined["target_start_saved"].equals(joined["target_start"])
        assert joined["target_end_saved"].equals(joined["target_end"])
        expected = np.maximum(0, booster.predict(feature_matrix(joined, metadata["feature_columns"], metadata["product_codes"])))
        np.testing.assert_allclose(saved["lightgbm"], expected, rtol=1e-12)
        np.testing.assert_allclose(saved["baseline"], joined["sales_sum_7"])
        for method in ["lightgbm", "baseline"]:
            recomputed = metrics(saved["target"], saved[method])
            recorded = evaluation["results"][name]["overall"][method]
            for key in ["mae", "wape"]:
                np.testing.assert_allclose(recomputed[key], recorded[key], rtol=1e-12)
        if name != "train":
            for _, group in saved.groupby("stock_code"):
                assert (group["target_start"].iloc[1:].to_numpy() > group["target_end"].iloc[:-1].to_numpy()).all()
    saved_forecast = pd.read_csv(directory / "forecast.csv", dtype={"stock_code": str})
    recomputed_forecast = infer(daily, directory / "final_model.txt", metadata)
    assert len(saved_forecast) == len(products) == 30
    assert not saved_forecast["actual_available"].any()
    assert saved_forecast["stock_code"].tolist() == recomputed_forecast["stock_code"].tolist()
    np.testing.assert_allclose(saved_forecast["predicted_quantity"], recomputed_forecast["predicted_quantity"], rtol=1e-12)
    print("Saved evaluation model, metrics, nonoverlapping targets, data hash and 30 future forecasts verified.")


if __name__ == "__main__":
    main()
