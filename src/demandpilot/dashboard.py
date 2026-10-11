"""Read-only data loading and saved-model inference, independent of Streamlit."""

import json
from pathlib import Path

import pandas as pd

from demandpilot.db import connect
from demandpilot.modeling.predict import infer


def load_dashboard(model_directory: Path = Path("artifacts/ml")) -> dict:
    metadata = json.loads((model_directory / "training_conditions.json").read_text(encoding="utf-8"))
    evaluation = json.loads((model_directory / "evaluation.json").read_text(encoding="utf-8"))
    origin = pd.Timestamp(metadata["forecast_origin"])
    start = origin - pd.Timedelta(days=89)
    with connect() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        products = pd.DataFrame(connection.execute("SELECT stock_code, description FROM products ORDER BY stock_code").fetchall(),
                                columns=["stock_code", "description"])
        history = pd.DataFrame(connection.execute(
            "SELECT stock_code, sales_date, quantity FROM daily_sales WHERE sales_date BETWEEN %s AND %s ORDER BY stock_code, sales_date",
            (start.date(), origin.date()),
        ).fetchall(), columns=["stock_code", "sales_date", "quantity"])
    if len(products) != 30 or set(products["stock_code"]) != set(metadata["product_codes"]):
        raise ValueError("Products differ from the model cohort")
    history["sales_date"] = pd.to_datetime(history["sales_date"])
    sizes = history.groupby("stock_code").size()
    if set(sizes.index) != set(metadata["product_codes"]) or not sizes.eq(90).all():
        raise ValueError("Complete 90-day history required")
    forecasts = infer(history, model_directory / "final_model.txt", metadata)
    per_product = {row["stock_code"]: row for row in evaluation["results"]["test"]["per_product"]}
    if set(per_product) != set(metadata["product_codes"]):
        raise ValueError("Evaluation cohort differs from saved model")
    return {"products": products, "history": history, "forecasts": forecasts,
            "evaluation": evaluation, "metadata": metadata, "product_metrics": per_product}


def test_scores(bundle: dict, stock_code: str | None = None) -> dict:
    if stock_code is None:
        return bundle["evaluation"]["results"]["test"]["overall"]
    return {name: bundle["product_metrics"][stock_code][name] for name in ["lightgbm", "baseline"]}
