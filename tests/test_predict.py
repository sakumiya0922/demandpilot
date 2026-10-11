import lightgbm as lgb
import numpy as np
import pandas as pd

from demandpilot.features import build_features, feature_columns, feature_matrix
from demandpilot.modeling.predict import infer


def test_saved_model_inference_is_causal_and_matches_original(tmp_path):
    daily = pd.DataFrame({"stock_code": ["A"] * 60, "sales_date": pd.date_range("2011-01-01", periods=60),
                         "quantity": np.arange(60) % 10})
    frame = build_features(daily).dropna(subset=feature_columns() + ["target"])
    model = lgb.LGBMRegressor(n_estimators=3, num_leaves=3, min_child_samples=2, verbosity=-1, n_jobs=1)
    model.fit(feature_matrix(frame, feature_columns(), ["A"]), frame["target"])
    path = tmp_path / "model.txt"
    model.booster_.save_model(str(path))
    metadata = {"forecast_origin": "2011-02-20", "feature_windows": [7, 14, 28], "horizon_days": 7,
                "feature_columns": feature_columns(), "product_codes": ["A"]}
    result = infer(daily, path, metadata)
    changed = daily.copy()
    changed.loc[changed.sales_date.gt(metadata["forecast_origin"]), "quantity"] = 1000000
    pd.testing.assert_frame_equal(result, infer(changed, path, metadata))
    assert result.target_start.iloc[0] == pd.Timestamp("2011-02-21")
    assert result.target_end.iloc[0] == pd.Timestamp("2011-02-27")
    assert not result.actual_available.any()
    origin = build_features(daily).loc[lambda f: f.sales_date.eq(metadata["forecast_origin"])]
    np.testing.assert_allclose(result.predicted_quantity, np.maximum(0, model.predict(feature_matrix(origin, feature_columns(), ["A"]))))
