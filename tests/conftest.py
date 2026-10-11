import pandas as pd
import pytest


@pytest.fixture
def raw_factory():
    def make(**changes):
        row = {"InvoiceNo": "536365", "StockCode": "85123A", "Description": "TEST PRODUCT",
               "Quantity": 2, "InvoiceDate": "2011-01-01 10:00:00", "UnitPrice": 2.55,
               "CustomerID": 12345, "Country": "United Kingdom"}
        row.update(changes)
        return row
    return make


@pytest.fixture
def training_transactions():
    return pd.DataFrame([
        {"StockCode": code, "Description": f"Product {code}", "Quantity": quantity, "InvoiceDate": date}
        for code, quantity in [("10001", 2), ("10002", 1)]
        for date in pd.date_range("2011-01-01", "2011-01-05")
    ])
