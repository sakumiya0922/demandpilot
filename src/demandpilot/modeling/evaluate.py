"""Metrics and strictly chronological splits with full-label containment."""

import numpy as np
import pandas as pd


def metrics(actual, predicted) -> dict:
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    if actual.ndim != 1 or actual.shape != predicted.shape or actual.size == 0:
        raise ValueError("Nonempty matching vectors required")
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all() or (actual < 0).any():
        raise ValueError("Finite values and nonnegative actual quantities required")
    errors = np.abs(actual - predicted)
    denominator = float(actual.sum())
    return {"mae": float(errors.mean()), "wape": float(errors.sum() / denominator) if denominator else None,
            "rows": int(actual.size), "actual_sum": denominator}


def chronological_split(frame, columns, training_start, training_end, validation_start, validation_end,
                        test_start, test_end, stride=7):
    boundaries = [pd.Timestamp(value) for value in [training_start, training_end, validation_start, validation_end, test_start, test_end]]
    a, b, c, d, e, f = boundaries
    if not (a <= b < c <= d < e <= f) or stride < 1:
        raise ValueError("Disjoint ordered periods and positive stride required")
    complete = frame.dropna(subset=columns + ["target"])
    result = {}
    for name, start, end in [("train", a, b), ("validation", c, d), ("test", e, f)]:
        # Origins and their entire target period must lie in the assigned interval.
        interval = complete.loc[complete["sales_date"].between(start, end)]
        part = interval.loc[interval["target_end"].le(end)].copy()
        if name != "train":
            part = part.loc[(part["sales_date"] - start).dt.days.mod(stride).eq(0)]
        if part.empty:
            raise ValueError(f"Empty {name} split")
        result[name] = part.reset_index(drop=True)
    return result


def split_summary(frame) -> dict:
    return {"rows": len(frame), "products": frame["stock_code"].nunique(),
            "origins": frame["sales_date"].nunique(),
            "origin_start": frame["sales_date"].min().date().isoformat(),
            "origin_end": frame["sales_date"].max().date().isoformat(),
            "target_start": frame["target_start"].min().date().isoformat(),
            "target_end": frame["target_end"].max().date().isoformat()}


def compare_predictions(frame, model_predictions, baseline_predictions) -> tuple[dict, list[dict], pd.DataFrame]:
    rows = frame[["stock_code", "sales_date", "target_start", "target_end", "target"]].copy()
    rows["lightgbm"] = model_predictions
    rows["baseline"] = baseline_predictions
    summary = {name: metrics(rows["target"], rows[name]) for name in ["lightgbm", "baseline"]}
    per_product = [
        {"stock_code": code, **{name: metrics(group["target"], group[name]) for name in ["lightgbm", "baseline"]}}
        for code, group in rows.groupby("stock_code", sort=True)
    ]
    return summary, per_product, rows
