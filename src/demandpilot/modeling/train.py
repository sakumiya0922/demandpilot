"""Validation-only model selection, sealed test evaluation, then final refit."""

import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from demandpilot.config import load_settings
from demandpilot.features import build_features, feature_columns, feature_matrix
from demandpilot.modeling.baseline import predict_baseline
from demandpilot.modeling.data import load_daily_sales
from demandpilot.modeling.evaluate import chronological_split, compare_predictions, metrics, split_summary
from demandpilot.modeling.mlflow_tracking import log_training_experiment
from demandpilot.modeling.predict import predict_latest


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def train_models(settings_path="config/settings.yaml", output_dir=Path("artifacts/ml")) -> dict:
    settings = load_settings(settings_path)
    config = settings["model"]
    daily, products = load_daily_sales()
    product_codes = products["stock_code"].tolist()
    if len(products) != settings["target_product_count"]:
        raise ValueError("Unexpected selected product count")
    preparation = json.loads(Path("artifacts/data_quality.json").read_text())
    if {p["StockCode"] for p in preparation["selected_products"]} != set(product_codes):
        raise ValueError("DB cohort differs from stage-2 selection")
    for key in ["training_start", "training_end", "observation_start", "observation_end"]:
        if preparation["settings"]["data"][key] != settings["data"][key]:
            raise ValueError("Stage-2 selection and model dates differ")
    windows, horizon = settings["feature_windows"], settings["forecast_horizon_days"]
    if horizon != 7 or 7 not in windows or config["evaluation_stride_days"] < horizon:
        raise ValueError("Seven-day target and nonoverlapping evaluation required")
    origin = pd.Timestamp(config["forecast_origin"])
    if daily["sales_date"].max() != origin or origin != pd.Timestamp(settings["data"]["observation_end"]):
        raise ValueError("Forecast origin must match the last observed date")
    features = build_features(daily, windows, horizon)
    columns = feature_columns(windows)
    splits = chronological_split(features, columns, settings["data"]["training_start"], settings["data"]["training_end"],
                                 config["validation_start"], config["validation_end"], config["test_start"], config["test_end"],
                                 config["evaluation_stride_days"])
    train, validation = splits["train"], splits["validation"]
    matrices = {name: feature_matrix(part, columns, product_codes) for name, part in splits.items()}
    common = {"objective": "regression_l1", "learning_rate": config["learning_rate"],
              "random_state": settings["random_seed"], "n_jobs": 2, "verbosity": -1,
              "deterministic": True, "force_col_wise": True}
    candidates = []
    best_model, best_score, best_params = None, float("inf"), None
    for parameters in config["candidates"]:
        model = lgb.LGBMRegressor(**common, **parameters, n_estimators=config["max_estimators"])
        model.fit(matrices["train"], train["target"], categorical_feature=["stock_code"],
                  eval_set=[(matrices["validation"], validation["target"])], eval_metric="l1",
                  callbacks=[lgb.early_stopping(config["early_stopping_rounds"], verbose=False)])
        prediction = np.maximum(0, model.predict(matrices["validation"]))
        score = metrics(validation["target"], prediction)
        candidates.append({"parameters": parameters, "best_iteration": model.best_iteration_, "validation": score})
        if score["mae"] < best_score:
            best_model, best_score, best_params = model, score["mae"], parameters.copy()
    output_dir.mkdir(parents=True, exist_ok=True)
    best_model.booster_.save_model(str(output_dir / "evaluation_model.txt"))
    evaluation = {"selection_metric": "validation_mae", "candidates": candidates,
                  "splits": {name: split_summary(part) for name, part in splits.items()}, "results": {}}
    for name, part in splits.items():
        prediction = np.maximum(0, best_model.predict(matrices[name]))
        summary, per_product, rows = compare_predictions(part, prediction, predict_baseline(part))
        evaluation["results"][name] = {"overall": summary, "per_product": per_product}
        rows.to_csv(output_dir / f"{name}_predictions.csv", index=False)
    test = evaluation["results"]["test"]["overall"]
    evaluation["test_model_beats_baseline"] = test["lightgbm"]["mae"] < test["baseline"]["mae"]
    write_json(output_dir / "evaluation.json", evaluation)
    product_rows = []
    for row in evaluation["results"]["test"]["per_product"]:
        product_rows.append({"stock_code": row["stock_code"],
                             **{f"{name}_{metric}": row[name][metric] for name in ["lightgbm", "baseline"] for metric in ["mae", "wape", "rows"]}})
    pd.DataFrame(product_rows).merge(products, on="stock_code").to_csv(output_dir / "product_metrics.csv", index=False)
    # All complete labels available at origin, including the former test period.
    # This model is for future inference only; its scores are never called test scores.
    final_rows = features.dropna(subset=columns + ["target"])
    final_rows = final_rows.loc[final_rows["target_end"].le(origin)]
    final_model = lgb.LGBMRegressor(**common, **best_params, n_estimators=best_model.best_iteration_)
    final_model.fit(feature_matrix(final_rows, columns, product_codes), final_rows["target"], categorical_feature=["stock_code"])
    final_model.booster_.save_model(str(output_dir / "final_model.txt"))
    conditions = {"settings": settings, "feature_windows": windows, "horizon_days": horizon, "feature_columns": columns,
                  "product_codes": product_codes, "forecast_origin": config["forecast_origin"],
                  "future_actuals_available": False, "prediction_clip_min": 0,
                  "selected_parameters": {**common, **best_params, "n_estimators": best_model.best_iteration_},
                  "final_training": split_summary(final_rows), "evaluation_splits": evaluation["splits"],
                  "daily_sales_sha256": hashlib.sha256(daily.to_csv(index=False).encode()).hexdigest(),
                  "source_workbook_sha256": preparation["source"]["sha256"],
                  "versions": {name: version(name) for name in ["lightgbm", "pandas", "numpy", "scikit-learn"]}}
    write_json(output_dir / "training_conditions.json", conditions)
    importance = pd.DataFrame({"feature": columns, "gain": final_model.booster_.feature_importance(importance_type="gain")})
    importance.to_csv(output_dir / "feature_importance.csv", index=False)
    predict_latest(output_dir)
    log_training_experiment(evaluation, conditions, output_dir)
    print(json.dumps({"splits": evaluation["splits"], "test": test, "final_training": conditions["final_training"]}, indent=2))
    return evaluation
