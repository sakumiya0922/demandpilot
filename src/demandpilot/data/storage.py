"""Atomically replace the three pipeline-owned tables using PostgreSQL COPY."""

import pandas as pd

from demandpilot.db import connect


def _copy(connection, table: str, columns: str, rows) -> None:
    # Table and columns are internal constants, never user-provided identifiers.
    with connection.cursor().copy(f"COPY {table} ({columns}) FROM STDIN") as target:
        for row in rows:
            target.write_row(tuple(None if pd.isna(value) else value for value in row))


def save_snapshot(products: pd.DataFrame, transactions: pd.DataFrame, daily: pd.DataFrame) -> dict:
    with connect() as connection:
        # Serialize concurrent writers. All changes commit together, or roll back.
        connection.execute("SELECT pg_advisory_xact_lock(352)")
        connection.execute("TRUNCATE daily_sales, products, transactions")
        _copy(connection, "products", "stock_code, description", products.itertuples(index=False, name=None))
        columns = ["source_row", "InvoiceNo", "StockCode", "InvoiceDate", "Quantity", "UnitPrice", "Country"]
        _copy(connection, "transactions", "source_row, invoice_no, stock_code, invoice_date, quantity, unit_price, country",
              transactions[columns].itertuples(index=False, name=None))
        rows = ((code, date.date(), int(quantity)) for code, date, quantity in daily.itertuples(index=False, name=None))
        _copy(connection, "daily_sales", "stock_code, sales_date, quantity", rows)
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ["products", "transactions", "daily_sales"]
        }
        for table, expected in zip(counts, [len(products), len(transactions), len(daily)]):
            if counts[table] != expected:
                raise ValueError(f"Unexpected count in {table}")
        total = connection.execute("SELECT COALESCE(SUM(quantity), 0) FROM daily_sales").fetchone()[0]
        if int(total) != int(daily["quantity"].sum()):
            raise ValueError("Daily quantity mismatch")
        counts["daily_quantity_sum"] = int(total)
        counts["daily_zero_rows"] = connection.execute("SELECT COUNT(*) FROM daily_sales WHERE quantity = 0").fetchone()[0]
    return counts
