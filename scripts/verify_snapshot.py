"""Verify the stage-2 dataset and compare complete DB snapshots across reruns."""
import hashlib
import json
import sys
from pathlib import Path

from demandpilot.db import connect

snapshot = {}
with connect() as connection:
    for table, order in [("products", "stock_code"), ("transactions", "source_row"), ("daily_sales", "stock_code, sales_date")]:
        digest = hashlib.sha256()
        count = 0
        with connection.cursor(name=f"verify_{table}") as cursor:
            cursor.execute(f"SELECT row_to_json(t)::text FROM {table} t ORDER BY {order}")
            for (row,) in cursor:
                digest.update((row + "\n").encode())
                count += 1
        snapshot[table] = {"rows": count, "sha256": digest.hexdigest()}
    assert snapshot["products"]["rows"] == 30
    assert snapshot["transactions"]["rows"] == 526107
    assert snapshot["daily_sales"]["rows"] == 11190
    assert connection.execute("SELECT COUNT(*) FROM (SELECT stock_code FROM daily_sales GROUP BY stock_code HAVING COUNT(*) <> 373) t").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM (SELECT stock_code, sales_date FROM daily_sales GROUP BY stock_code, sales_date HAVING COUNT(*) > 1) t").fetchone()[0] == 0
    assert connection.execute("""
        WITH actual AS (
            SELECT t.stock_code, t.invoice_date::date AS sales_date, SUM(t.quantity) AS quantity
            FROM transactions t JOIN products p ON t.stock_code = p.stock_code
            GROUP BY t.stock_code, t.invoice_date::date
        )
        SELECT COUNT(*) FROM daily_sales d LEFT JOIN actual a USING (stock_code, sales_date)
        WHERE d.quantity <> COALESCE(a.quantity, 0)
    """).fetchone()[0] == 0
report_bytes = Path("artifacts/data_quality.json").read_bytes()
snapshot["report_sha256"] = hashlib.sha256(report_bytes).hexdigest()
baseline = Path("artifacts/db_snapshot_before.json")
if sys.argv[1] == "before":
    baseline.write_text(json.dumps(snapshot, indent=2) + "\n")
else:
    assert json.loads(baseline.read_text()) == snapshot, "Snapshot changed on rerun"
    Path("artifacts/db_snapshot_after.json").write_text(json.dumps(snapshot, indent=2) + "\n")
print(json.dumps(snapshot, indent=2))
print("Calendar, daily SQL aggregation, and snapshot checks passed.")
