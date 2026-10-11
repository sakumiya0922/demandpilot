"""Select products using training history only and construct a complete calendar."""

import pandas as pd


def select_products(
    transactions: pd.DataFrame, training_start: str, training_end: str,
    count: int, min_active_days: int, min_history_days: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    start, end = pd.Timestamp(training_start), pd.Timestamp(training_end)
    if start > end or min(count, min_active_days, min_history_days) < 1:
        raise ValueError("Invalid product selection settings")
    dates = transactions["InvoiceDate"].dt.normalize()
    train = transactions.loc[dates.between(start, end)].copy()
    train["sales_date"] = train["InvoiceDate"].dt.normalize()
    stats = train.groupby("StockCode").agg(
        active_days=("sales_date", "nunique"), first_sale=("sales_date", "min"),
        last_sale=("sales_date", "max"), training_quantity=("Quantity", "sum"),
    )
    stats["history_days"] = (stats["last_sale"] - stats["first_sale"]).dt.days + 1
    eligible = stats.loc[(stats["active_days"] >= min_active_days) & (stats["history_days"] >= min_history_days)]
    ranked = eligible.reset_index().sort_values(
        ["active_days", "training_quantity", "StockCode"], ascending=[False, False, True],
    )
    if len(ranked) < count:
        raise ValueError(f"Only {len(ranked)} eligible products; requested {count}")
    selected = ranked.head(count).copy()
    # Label is also derived exclusively from training data, with deterministic ties.
    descriptions = train.dropna(subset=["Description"]).groupby(["StockCode", "Description"]).size()
    labels = descriptions.rename("frequency").reset_index().sort_values(
        ["StockCode", "frequency", "Description"], ascending=[True, False, True],
    ).drop_duplicates("StockCode").set_index("StockCode")["Description"]
    selected["description"] = selected["StockCode"].map(labels).fillna(selected["StockCode"])
    products = selected[["StockCode", "description"]].rename(columns={"StockCode": "stock_code"})
    return products.reset_index(drop=True), selected.reset_index(drop=True)


def aggregate_daily(transactions: pd.DataFrame, products: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    calendar = pd.date_range(start, end, freq="D")
    if calendar.empty or products["stock_code"].duplicated().any():
        raise ValueError("Invalid calendar or duplicate products")
    frame = transactions.loc[transactions["StockCode"].isin(products["stock_code"])].copy()
    frame["sales_date"] = frame["InvoiceDate"].dt.normalize()
    frame = frame.loc[frame["sales_date"].between(calendar[0], calendar[-1])]
    totals = frame.groupby(["StockCode", "sales_date"])["Quantity"].sum()
    full_index = pd.MultiIndex.from_product(
        [products["stock_code"].sort_values(), calendar], names=["stock_code", "sales_date"],
    )
    daily = totals.reindex(full_index, fill_value=0).rename("quantity").reset_index()
    daily["quantity"] = daily["quantity"].astype("int64")
    assert int(daily["quantity"].sum()) == int(frame["Quantity"].sum())
    return daily
