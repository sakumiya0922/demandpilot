"""Causal features at end of day t and complete labels for t+1 through t+7."""

import pandas as pd


def build_features(daily: pd.DataFrame, windows=(7, 14, 28), horizon: int = 7) -> pd.DataFrame:
    if horizon < 1 or not windows or min(windows) < 1:
        raise ValueError("Positive windows and horizon required")
    frame = daily.copy()
    frame["sales_date"] = pd.to_datetime(frame["sales_date"])
    frame = frame.sort_values(["stock_code", "sales_date"]).reset_index(drop=True)
    if frame.duplicated(["stock_code", "sales_date"]).any() or frame["quantity"].isna().any() or frame["quantity"].lt(0).any():
        raise ValueError("Unique, nonnegative daily sales required")
    gaps = frame.groupby("stock_code")["sales_date"].diff().dropna()
    if not gaps.eq(pd.Timedelta(days=1)).all():
        raise ValueError("Daily calendar must be complete for each product")
    grouped = frame.groupby("stock_code", sort=False)["quantity"]
    for window in windows:
        for statistic in ["sum", "mean", "std"]:
            frame[f"sales_{statistic}_{window}"] = grouped.transform(
                lambda values, w=window, s=statistic: getattr(values.rolling(w, min_periods=w), s)()
            )
    # Each shift is strictly future data and only enters the label, never X.
    future = pd.concat([grouped.shift(-offset) for offset in range(1, horizon + 1)], axis=1)
    frame["target"] = future.sum(axis=1, min_count=horizon)
    frame["target_start"] = frame["sales_date"] + pd.Timedelta(days=1)
    frame["target_end"] = frame["sales_date"] + pd.Timedelta(days=horizon)
    frame["month"] = frame["sales_date"].dt.month
    frame["day_of_week"] = frame["sales_date"].dt.dayofweek
    frame["day_of_month"] = frame["sales_date"].dt.day
    return frame


def feature_columns(windows=(7, 14, 28)) -> list[str]:
    return [f"sales_{statistic}_{window}" for window in windows for statistic in ["sum", "mean", "std"]] + [
        "month", "day_of_week", "day_of_month", "stock_code",
    ]


def feature_matrix(frame: pd.DataFrame, columns: list[str], product_codes: list[str]) -> pd.DataFrame:
    matrix = frame[columns].copy()
    unknown = set(matrix["stock_code"]) - set(product_codes)
    if unknown:
        raise ValueError(f"Unknown products: {sorted(unknown)}")
    matrix["stock_code"] = pd.Categorical(matrix["stock_code"], categories=product_codes)
    if matrix.isna().any().any():
        raise ValueError("Incomplete feature history")
    return matrix
