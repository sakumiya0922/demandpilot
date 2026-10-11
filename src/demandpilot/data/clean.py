"""Auditable row filtering; keep legitimate bulk sales and anonymous customers."""

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate",
    "UnitPrice", "CustomerID", "Country",
]


def clean_transactions(raw: pd.DataFrame, start: str, end: str) -> tuple[pd.DataFrame, dict]:
    missing_columns = set(REQUIRED_COLUMNS) - set(raw.columns)
    if missing_columns:
        raise ValueError(f"Missing columns: {sorted(missing_columns)}")
    lower, upper = pd.Timestamp(start), pd.Timestamp(end)
    if lower > upper:
        raise ValueError("Observation start must not exceed end")
    frame = raw.reset_index(drop=True).copy()
    frame["source_row"] = np.arange(2, len(frame) + 2)  # Original Excel row, including header.
    for column in ["InvoiceNo", "StockCode", "Description", "Country"]:
        frame[column] = frame[column].astype("string").str.strip()
        frame[column] = frame[column].mask(frame[column].eq(""))
    frame["StockCode"] = frame["StockCode"].str.upper()
    dates = pd.to_datetime(frame["InvoiceDate"], errors="coerce", format="mixed")
    quantity = pd.to_numeric(frame["Quantity"], errors="coerce")
    price = pd.to_numeric(frame["UnitPrice"], errors="coerce")
    finite_quantity = pd.Series(np.isfinite(quantity), index=frame.index).fillna(False)
    finite_price = pd.Series(np.isfinite(price), index=frame.index).fillna(False)
    rules = {
        "missing_invoice_no": frame["InvoiceNo"].isna(),
        "invalid_invoice_date": dates.isna(),
        "missing_stock_code": frame["StockCode"].isna(),
        "invalid_quantity": ~finite_quantity | quantity.mod(1).ne(0) | quantity.abs().gt(2147483647),
        "invalid_unit_price": ~finite_price | price.abs().ge(10**10),
        "cancellation": frame["InvoiceNo"].str.upper().str.startswith("C", na=False),
        "negative_quantity_return_or_adjustment": quantity.lt(0),
        "zero_quantity": quantity.eq(0),
        "nonpositive_unit_price": price.le(0),
        "non_product_stock_code": ~frame["StockCode"].str.fullmatch(r"\d{5}[A-Z]{0,2}", na=False),
        "outside_observation_period": dates.dt.normalize().lt(lower) | dates.dt.normalize().gt(upper),
    }
    reasons = pd.Series("", index=frame.index, dtype="string")
    for name, mask in rules.items():
        reasons.loc[reasons.eq("") & mask.fillna(False)] = name
    keep = reasons.eq("")
    frame["InvoiceDate"] = dates
    frame["Quantity"] = quantity
    frame["UnitPrice"] = price
    cleaned = frame.loc[keep].copy()
    cleaned["Quantity"] = cleaned["Quantity"].astype("int64")
    # Observations only: do not remove exact-looking duplicates or high-volume sales.
    report = {
        "raw_rows": len(raw),
        "missing_values": {
            column: int(raw[column].isna().sum()) for column in REQUIRED_COLUMNS
        },
        "blank_text_values": {
            column: int(raw[column].astype("string").str.strip().eq("").sum())
            for column in ["InvoiceNo", "StockCode", "Description", "Country"]
        },
        "condition_counts_overlapping": {name: int(mask.fillna(False).sum()) for name, mask in rules.items()},
        "excluded_counts_exclusive": {name: int(reasons.eq(name).sum()) for name in rules},
        "excluded_rows": int((~keep).sum()),
        "clean_rows": len(cleaned),
        "exact_duplicate_rows_observed_not_removed": int(raw.duplicated().sum()),
        "quantity_summary_retained": cleaned["Quantity"].describe(percentiles=[0.5, 0.95, 0.99]).to_dict(),
        "unit_price_summary_retained": cleaned["UnitPrice"].describe(percentiles=[0.5, 0.95, 0.99]).to_dict(),
        "non_product_codes_observed": sorted(frame.loc[rules["non_product_stock_code"], "StockCode"].dropna().unique().tolist()),
    }
    assert report["raw_rows"] == report["clean_rows"] + sum(report["excluded_counts_exclusive"].values())
    return cleaned.reset_index(drop=True), report
