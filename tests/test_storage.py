"""Integration checks use an isolated schema, never the pipeline tables."""

import os
import uuid

import pandas as pd
import psycopg
import pytest
from psycopg import sql

from demandpilot.db import connect, initialize_schema
from demandpilot.data import storage


@pytest.fixture
def isolated_database(monkeypatch):
    if not os.getenv("POSTGRES_PASSWORD"):
        pytest.skip("PostgreSQL integration tests require the Compose environment")
    schema = "test_" + uuid.uuid4().hex
    with connect() as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    def scoped_connect():
        connection = connect()
        connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        return connection
    monkeypatch.setattr(storage, "connect", scoped_connect)
    import demandpilot.db as db
    monkeypatch.setattr(db, "connect", scoped_connect)
    try:
        initialize_schema()
        yield scoped_connect
    finally:
        with connect() as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_snapshot_rerun_and_rollback(isolated_database, raw_factory):
    from demandpilot.data.clean import clean_transactions
    from demandpilot.data.aggregate import aggregate_daily
    clean, _ = clean_transactions(pd.DataFrame([raw_factory(Country=None)]), "2011-01-01", "2011-01-03")
    products = pd.DataFrame({"stock_code": ["85123A"], "description": ["TEST PRODUCT"]})
    daily = aggregate_daily(clean, products, "2011-01-01", "2011-01-03")
    first = storage.save_snapshot(products, clean, daily)
    assert storage.save_snapshot(products, clean, daily) == first
    assert first == {"products": 1, "transactions": 1, "daily_sales": 3, "daily_quantity_sum": 2, "daily_zero_rows": 2}
    broken = daily.copy()
    broken.loc[0, "quantity"] = -1
    with pytest.raises(psycopg.errors.CheckViolation):
        storage.save_snapshot(products, clean, broken)
    with isolated_database() as connection:
        assert connection.execute("SELECT SUM(quantity), COUNT(*) FROM daily_sales").fetchone() == (2, 3)
        assert connection.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 1
