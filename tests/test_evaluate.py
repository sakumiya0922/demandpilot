import numpy as np
import pandas as pd
import pytest

from demandpilot.features import build_features, feature_columns
from demandpilot.modeling.evaluate import chronological_split, compare_predictions, metrics
from demandpilot.modeling.baseline import predict_baseline


def test_metric_values_and_zero_denominator():
    result = metrics([10, 20, 0], [8, 25, 3])
    assert result["mae"] == pytest.approx(10 / 3)
    assert result["wape"] == pytest.approx(10 / 30)
    assert metrics([0, 0], [1, 2])["wape"] is None
    assert metrics([0, 0], [1, 2])["mae"] == 1.5


@pytest.mark.parametrize("actual,prediction", [([], []), ([1], [1, 2]), ([np.nan], [1]), ([-1], [1]), ([1], [np.inf])])
def test_invalid_metrics_rejected(actual, prediction):
    with pytest.raises(ValueError):
        metrics(actual, prediction)


def test_split_purges_boundary_labels_and_has_nonoverlapping_evaluation():
    daily = pd.DataFrame({"stock_code": ["A"] * 373,
                         "sales_date": pd.date_range("2010-12-01", "2011-12-08"), "quantity": 1})
    features = build_features(daily)
    splits = chronological_split(features, feature_columns(), "2010-12-01", "2011-08-31",
                                 "2011-09-01", "2011-10-31", "2011-11-01", "2011-12-08")
    assert splits["train"].sales_date.max() == pd.Timestamp("2011-08-24")
    assert splits["train"].target_end.max() == pd.Timestamp("2011-08-31")
    assert splits["train"].sales_date.min() == pd.Timestamp("2010-12-28")
    assert len(splits["validation"]) == 8
    assert len(splits["test"]) == 5
    assert splits["validation"].target_end.max() < splits["test"].sales_date.min()
    for name in ["validation", "test"]:
        part = splits[name]
        assert part.sales_date.diff().dropna().eq(pd.Timedelta(days=7)).all()
        assert (part.target_start.iloc[1:].to_numpy() > part.target_end.iloc[:-1].to_numpy()).all()
    assert splits["test"].target_end.max() == pd.Timestamp("2011-12-06")
    with pytest.raises(ValueError, match="Disjoint"):
        chronological_split(features, feature_columns(), "2010-12-01", "2011-09-01",
                            "2011-09-01", "2011-10-31", "2011-11-01", "2011-12-08")


def test_baseline_and_product_metrics_use_identical_rows():
    frame = pd.DataFrame({"stock_code": ["A", "B"], "sales_date": pd.to_datetime(["2011-01-01"] * 2),
                          "target_start": pd.to_datetime(["2011-01-02"] * 2),
                          "target_end": pd.to_datetime(["2011-01-08"] * 2),
                          "target": [10, 20], "sales_sum_7": [8, 24]})
    overall, products, rows = compare_predictions(frame, [9, 21], predict_baseline(frame))
    assert overall["lightgbm"]["mae"] == 1
    assert overall["baseline"]["mae"] == 3
    assert len(products) == 2 and len(rows) == 2
