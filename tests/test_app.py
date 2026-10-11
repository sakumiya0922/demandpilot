"""Real-model, real-DB Streamlit interaction tests in the Compose environment."""

import json
import os
from pathlib import Path

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from demandpilot.dashboard import load_dashboard
from demandpilot.replenishment import recommended_replenishment


@pytest.fixture
def prepared_dashboard():
    if not os.getenv("POSTGRES_PASSWORD") or not Path("artifacts/ml/final_model.txt").exists():
        pytest.skip("Run prepare-data and train in Compose before the UI integration tests")
    st.cache_data.clear()
    return load_dashboard()


def assert_app_ok(app):
    assert not app.exception
    assert not app.error


def test_real_ui_product_switching_forecasts_and_evaluation(prepared_dashboard):
    bundle = prepared_dashboard
    app = AppTest.from_file("app/streamlit_app.py", default_timeout=20).run()
    assert_app_ok(app)
    assert len(app.selectbox(key="product").options) == 30
    assert any("2011年12月08日" in c.value for c in app.caption)
    assert len(app.get("arrow_vega_lite_chart")) == 1
    assert len(app.metric) == 4
    expected = bundle["forecasts"].set_index("stock_code")
    saved = pd.read_csv("artifacts/ml/forecast.csv", dtype={"stock_code": str}).set_index("stock_code")
    for code in bundle["products"]["stock_code"]:
        app.selectbox(key="product").set_value(code).run()
        assert_app_ok(app)
        assert app.metric[0].value == f"{int(expected.loc[code, 'baseline_quantity']):,} 個"
        assert app.metric[1].value == f"{saved.loc[code, 'predicted_quantity']:,.1f} 個"
        assert app.metric[2].value == f"{expected.loc[code, 'baseline_quantity']:,.0f} 個"
        assert code in app.selectbox(key="product").options[bundle["products"]["stock_code"].tolist().index(code)]
    overall = app.dataframe[0].value
    assert overall["MAE（個）"].tolist() == ["274.01", "206.67"]
    assert overall["WAPE"].tolist() == ["57.41%", "43.30%"]
    assert any("下回って" in w.value for w in app.warning)
    app.radio(key="evaluation_scope").set_value("選択商品").run()
    metrics = bundle["product_metrics"][code]
    assert app.dataframe[0].value["MAE（個）"].tolist() == [f"{metrics[m]['mae']:,.2f}" for m in ["lightgbm", "baseline"]]
    assert app.dataframe[0].value["WAPE"].tolist() == [f"{metrics[m]['wape']:.2%}" for m in ["lightgbm", "baseline"]]
    app.selectbox(key="product").set_value("20725").run()
    assert "155.88" in app.dataframe[0].value["MAE（個）"].tolist()
    assert not app.warning  # Overall underperformance remains in the caption.
    assert any("LightGBMが下回りました" in c.value for c in app.caption)


def test_stock_changes_and_model_switch_recompute(prepared_dashboard):
    app = AppTest.from_file("app/streamlit_app.py", default_timeout=20).run()
    assert_app_ok(app)
    code = app.selectbox(key="product").value
    forecast = prepared_dashboard["forecasts"].set_index("stock_code").loc[code]
    expected = recommended_replenishment(float(forecast.predicted_quantity), 300, 100)
    assert app.metric[3].value == f"{expected:,} 個"
    app.number_input(key="current_stock").set_value(400).run()
    assert app.metric[3].value == f"{max(0, expected - 100):,} 個"
    app.number_input(key="safety_stock").set_value(200).run()
    assert app.metric[3].value == f"{expected:,} 個"
    app.radio(key="forecast_method").set_value("ベースライン").run()
    assert app.metric[3].value == f"{recommended_replenishment(float(forecast.baseline_quantity), 400, 200):,} 個"
    app.number_input(key="current_stock").set_value(100000).run()
    assert app.metric[3].value == "0 個"
    assert_app_ok(app)


def test_dashboard_read_only_and_exact_90_days(prepared_dashboard):
    bundle = prepared_dashboard
    history = bundle["history"]
    assert len(history) == 2700
    assert history.sales_date.min() == pd.Timestamp("2011-09-10")
    assert history.sales_date.max() == pd.Timestamp("2011-12-08")
    assert history.groupby("stock_code").size().eq(90).all()
    evaluation = json.loads(Path("artifacts/ml/evaluation.json").read_text())
    assert bundle["evaluation"] == evaluation
    assert not bundle["forecasts"].actual_available.any()


def test_missing_artifacts_show_recovery_message(monkeypatch):
    import demandpilot.dashboard as dashboard
    st.cache_data.clear()
    def missing():
        raise FileNotFoundError("missing model")
    monkeypatch.setattr(dashboard, "load_dashboard", missing)
    app = AppTest.from_file("app/streamlit_app.py").run()
    assert not app.exception
    assert "学習成果物が見つかりません" in app.error[0].value
    assert not app.selectbox
    st.cache_data.clear()
