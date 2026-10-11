import numpy as np
import pandas as pd
import pytest

from demandpilot.data.clean import clean_transactions


@pytest.mark.parametrize("changes, reason", [
    ({"InvoiceNo": None}, "missing_invoice_no"),
    ({"InvoiceDate": "invalid"}, "invalid_invoice_date"),
    ({"StockCode": " "}, "missing_stock_code"),
    ({"Quantity": None}, "invalid_quantity"),
    ({"Quantity": 1.5}, "invalid_quantity"),
    ({"Quantity": np.inf}, "invalid_quantity"),
    ({"UnitPrice": None}, "invalid_unit_price"),
    ({"UnitPrice": np.inf}, "invalid_unit_price"),
    ({"InvoiceNo": "c536365", "Quantity": -2}, "cancellation"),
    ({"Quantity": -2}, "negative_quantity_return_or_adjustment"),
    ({"Quantity": 0}, "zero_quantity"),
    ({"UnitPrice": 0}, "nonpositive_unit_price"),
    ({"UnitPrice": -1}, "nonpositive_unit_price"),
    ({"StockCode": "POST"}, "non_product_stock_code"),
    ({"InvoiceDate": "2011-12-09 08:00"}, "outside_observation_period"),
])
def test_exclusion_rules(raw_factory, changes, reason):
    clean, report = clean_transactions(pd.DataFrame([raw_factory(), raw_factory(**changes)]), "2010-12-01", "2011-12-08")
    assert len(clean) == 1
    assert report["excluded_counts_exclusive"][reason] == 1
    assert sum(report["excluded_counts_exclusive"].values()) == 1
    assert report["raw_rows"] == report["clean_rows"] + report["excluded_rows"]


def test_overlap_missing_optional_fields_bulk_sales_and_original_rows(raw_factory):
    raw = pd.DataFrame([
        raw_factory(InvoiceNo="C123", Quantity=-2, UnitPrice=0),
        raw_factory(Description=None, CustomerID=None, Quantity=80000, StockCode="15056bl"),
        raw_factory(Description=None, CustomerID=None, Quantity=80000, StockCode="15056bl"),
    ])
    clean, report = clean_transactions(raw, "2010-12-01", "2011-12-08")
    assert clean["source_row"].tolist() == [3, 4]
    assert clean["StockCode"].tolist() == ["15056BL", "15056BL"]
    assert report["missing_values"]["CustomerID"] == 2
    assert report["missing_values"]["Description"] == 2
    assert report["exact_duplicate_rows_observed_not_removed"] == 1
    assert report["condition_counts_overlapping"]["negative_quantity_return_or_adjustment"] == 1
    assert report["excluded_counts_exclusive"]["negative_quantity_return_or_adjustment"] == 0


def test_missing_columns_rejected():
    with pytest.raises(ValueError, match="Missing columns"):
        clean_transactions(pd.DataFrame(), "2010-12-01", "2011-12-08")
