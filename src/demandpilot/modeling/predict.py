"""Inference from the native LightGBM model and saved feature contract."""

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from demandpilot.features import build_features, feature_matrix
from demandpilot.modeling.data import load_daily_sales


def infer(daily: pd.DataFrame, model_path: Path, metadata: dict) -> pd.DataFrame:
    origin = pd.Timestamp(metadata["forecast_origin"])
    # Truncate input explicitly, so later DB updates cannot affect this prediction.
    observed = daily.loc[pd.to_datetime(daily["sales_date"]).le(origin)]
    features = build_features(observed, metadata["feature_windows"], metadata["horizon_days"])
    latest = features.loc[features["sales_date"].eq(origin)].sort_values("stock_code")
    if set(latest["stock_code"]) != set(metadata["product_codes"]):
        raise ValueError("Missing product observations at the forecast origin")
    model = lgb.Booster(model_file=str(model_path))
    predictions = np.maximum(0, model.predict(feature_matrix(latest, metadata["feature_columns"], metadata["product_codes"])))
    result = latest[["stock_code", "sales_date", "target_start", "target_end"]].copy()
    result["predicted_quantity"] = predictions
    result["baseline_quantity"] = latest["sales_sum_7"].to_numpy()
    result["actual_available"] = False
    return result.reset_index(drop=True)


def predict_latest(output_dir: Path = Path("artifacts/ml")) -> pd.DataFrame:
    metadata = json.loads((output_dir / "training_conditions.json").read_text())
    daily, products = load_daily_sales()
    forecast = infer(daily, output_dir / "final_model.txt", metadata)
    forecast = forecast.merge(products, on="stock_code", validate="one_to_one")
    forecast.to_csv(output_dir / "forecast.csv", index=False)
    print(f"Saved {len(forecast)} forecasts to {output_dir / 'forecast.csv'}; future actuals unavailable.")
    return forecast
