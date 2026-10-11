"""Forecast next seven days with the observed last seven days."""


def predict_baseline(frame):
    return frame["sales_sum_7"].to_numpy(dtype=float)
