"""Reproducible end-to-end data preparation with an auditable JSON report."""

import json
from pathlib import Path

import pandas as pd

from demandpilot.config import load_settings
from demandpilot.db import initialize_schema
from demandpilot.data.aggregate import aggregate_daily, select_products
from demandpilot.data.clean import clean_transactions
from demandpilot.data.download import SOURCE_URL, download_dataset, sha256
from demandpilot.data.storage import save_snapshot


def prepare_data(settings_path: str = "config/settings.yaml") -> dict:
    settings = load_settings(settings_path)
    config = settings["data"]
    if not (pd.Timestamp(config["observation_start"]) <= pd.Timestamp(config["training_start"])
            <= pd.Timestamp(config["training_end"]) <= pd.Timestamp(config["observation_end"])):
        raise ValueError("Training dates must lie inside the observation period")
    workbook = download_dataset()
    print(f"Reading {workbook}", flush=True)
    raw = pd.read_excel(workbook, engine="openpyxl", dtype={"InvoiceNo": "string", "StockCode": "string"})
    clean, quality = clean_transactions(raw, config["observation_start"], config["observation_end"])
    products, selection = select_products(
        clean, config["training_start"], config["training_end"], settings["target_product_count"],
        config["min_active_days"], config["min_history_days"],
    )
    daily = aggregate_daily(clean, products, config["observation_start"], config["observation_end"])
    initialize_schema()
    database = save_snapshot(products, clean, daily)
    selected_transactions = clean.loc[clean["StockCode"].isin(products["stock_code"])]
    report = {
        "source": {"url": SOURCE_URL, "workbook": str(workbook), "sha256": sha256(workbook)},
        "settings": settings,
        "quality": quality,
        "period": {
            "raw_start": str(pd.to_datetime(raw["InvoiceDate"]).min()),
            "raw_end": str(pd.to_datetime(raw["InvoiceDate"]).max()),
            "observation_start": config["observation_start"], "observation_end": config["observation_end"],
            "training_start": config["training_start"], "training_end": config["training_end"],
        },
        "selected_product_count": len(products),
        "selected_transaction_rows": len(selected_transactions),
        "daily_rows": len(daily),
        "database": database,
        "selected_products": json.loads(selection.to_json(orient="records", date_format="iso")),
    }
    report_dir = Path("artifacts")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "data_quality.json"
    temporary = report_path.with_suffix(".json.part")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(report_path)
    print(json.dumps({"quality": quality, "database": database, "report": str(report_path)}, ensure_ascii=False, indent=2))
    return report
