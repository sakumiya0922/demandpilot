import pandas as pd
import pytest

from demandpilot.data.aggregate import aggregate_daily, select_products


def test_future_data_does_not_change_selection_or_labels(training_transactions):
    args = ("2011-01-01", "2011-01-05", 1, 3, 5)
    products, stats = select_products(training_transactions, *args)
    future = pd.DataFrame([
        {"StockCode": "99999", "Description": "Future bestseller", "Quantity": 100000, "InvoiceDate": pd.Timestamp("2011-01-06")},
        {"StockCode": "10001", "Description": "Future renamed", "Quantity": 100000, "InvoiceDate": pd.Timestamp("2011-01-06")},
    ])
    other_products, other_stats = select_products(pd.concat([training_transactions, future]), *args)
    pd.testing.assert_frame_equal(products, other_products)
    pd.testing.assert_frame_equal(stats, other_stats)
    assert products["stock_code"].tolist() == ["10001"]


def test_selection_threshold_and_deterministic_ties(training_transactions):
    training_transactions["Quantity"] = 1
    products, _ = select_products(training_transactions.sample(frac=1, random_state=42), "2011-01-01", "2011-01-05", 1, 5, 5)
    assert products["stock_code"].tolist() == ["10001"]
    with pytest.raises(ValueError, match="eligible products"):
        select_products(training_transactions, "2011-01-01", "2011-01-05", 2, 6, 5)


def test_zero_completion_boundaries_and_sales_conservation():
    products = pd.DataFrame({"stock_code": ["10001", "10002"], "description": ["A", "B"]})
    transactions = pd.DataFrame({
        "StockCode": ["10001", "10001", "10001", "99999", "10002"],
        "InvoiceDate": pd.to_datetime(["2011-01-01 10:00", "2011-01-01 11:00", "2011-01-04", "2011-01-02", "2011-01-03 23:59"], format="mixed"),
        "Quantity": [2, 3, 100, 100, 7],
    })
    daily = aggregate_daily(transactions, products, "2011-01-01", "2011-01-03")
    assert len(daily) == 6
    assert daily["quantity"].tolist() == [5, 0, 0, 0, 0, 7]
    assert not daily.duplicated(["stock_code", "sales_date"]).any()
    assert daily["quantity"].sum() == 12
