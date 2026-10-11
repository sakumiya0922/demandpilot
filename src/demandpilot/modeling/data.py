"""Read the existing selected cohort; do not reselect products during training."""

import pandas as pd

from demandpilot.db import connect


def load_daily_sales() -> tuple[pd.DataFrame, pd.DataFrame]:
    with connect() as connection:
        products = pd.DataFrame(connection.execute("SELECT stock_code, description FROM products ORDER BY stock_code").fetchall(),
                                columns=["stock_code", "description"])
        daily = pd.DataFrame(connection.execute("SELECT stock_code, sales_date, quantity FROM daily_sales ORDER BY stock_code, sales_date").fetchall(),
                             columns=["stock_code", "sales_date", "quantity"])
    if products.empty or daily.empty or set(daily["stock_code"]) != set(products["stock_code"]):
        raise ValueError("Run prepare-data first: selected cohort and daily sales required")
    daily["sales_date"] = pd.to_datetime(daily["sales_date"])
    return daily, products
