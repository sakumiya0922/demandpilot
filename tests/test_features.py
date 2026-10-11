import numpy as np
import pandas as pd
import pytest

from demandpilot.features import build_features, feature_columns, feature_matrix


def daily_example():
    return pd.DataFrame({"stock_code": ["A"] * 45, "sales_date": pd.date_range("2011-01-01", periods=45),
                         "quantity": np.arange(1, 46)})


def test_causal_windows_and_complete_target():
    daily = daily_example()
    result = build_features(daily)
    row = result.iloc[27]
    assert row["sales_sum_7"] == sum(range(22, 29))
    assert row["sales_sum_14"] == sum(range(15, 29))
    assert row["sales_sum_28"] == sum(range(1, 29))
    assert row["sales_mean_7"] == np.mean(range(22, 29))
    assert row["sales_std_7"] == pytest.approx(np.std(range(22, 29), ddof=1))
    assert row["target"] == sum(range(29, 36))
    assert row["target_start"] == pd.Timestamp("2011-01-29")
    assert row["target_end"] == pd.Timestamp("2011-02-04")
    assert result.iloc[-7:]["target"].isna().all()
    assert result.iloc[:27]["sales_sum_28"].isna().all()


def test_future_changes_never_change_features_and_products_are_isolated():
    daily = daily_example()
    other = daily.assign(stock_code="B", quantity=999)
    original = build_features(pd.concat([daily, other]))
    changed = daily.copy()
    changed.loc[28:, "quantity"] = 1000000
    result = build_features(pd.concat([changed, other]))
    columns = feature_columns()
    pd.testing.assert_frame_equal(original.loc[original.sales_date.le("2011-01-28"), columns],
                                  result.loc[result.sales_date.le("2011-01-28"), columns])
    assert result.loc[result.stock_code.eq("B"), "sales_sum_7"].dropna().eq(7 * 999).all()


@pytest.mark.parametrize("kind", ["gap", "duplicate", "negative"])
def test_invalid_daily_input_rejected(kind):
    frame = daily_example()
    if kind == "gap":
        frame = frame.drop(index=10)
    elif kind == "duplicate":
        frame = pd.concat([frame, frame.iloc[[0]]])
    else:
        frame.loc[0, "quantity"] = -1
    with pytest.raises(ValueError):
        build_features(frame)


def test_feature_contract_categories_and_missing_history():
    frame = build_features(daily_example())
    assert "target" not in feature_columns()
    matrix = feature_matrix(frame.iloc[[27]], feature_columns(), ["A", "B"])
    assert matrix["stock_code"].cat.categories.tolist() == ["A", "B"]
    with pytest.raises(ValueError, match="Unknown"):
        feature_matrix(frame.iloc[[27]], feature_columns(), ["B"])
    with pytest.raises(ValueError, match="Incomplete"):
        feature_matrix(frame.iloc[[0]], feature_columns(), ["A"])
