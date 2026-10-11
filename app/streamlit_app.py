"""Read-only forecasts, historical evaluation and stock simulation."""

import pandas as pd
import streamlit as st

from demandpilot.dashboard import load_dashboard, test_scores
from demandpilot.replenishment import recommended_replenishment

st.set_page_config(page_title="DemandPilot | 需要予測", page_icon="📦", layout="wide")
st.markdown("""
<style>
.block-container {max-width:1280px; padding-top:2rem; padding-bottom:3rem;}
[data-testid="stMetric"] {background:white; border:1px solid #E2E8F0; border-radius:14px; padding:20px;}
[data-testid="stMetricLabel"] {color:#64748B;}
[data-testid="stMetricValue"] {color:#0F172A; font-size:1.9rem;}
h1 {letter-spacing:-0.04em;}
@media (max-width:640px) {
  .block-container {padding:1rem;}
  [data-testid="stHorizontalBlock"] {flex-direction:column;}
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {width:100% !important; flex:1 1 auto !important;}
  [data-testid="stMetric"] {padding:14px;}
}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=60, show_spinner=False)
def dashboard_data():
    return load_dashboard()


def wape_text(value):
    return "算出不可" if value is None else f"{value:.2%}"


st.title("DemandPilot")
st.caption("需要を見通し、次の補充を考える。｜需要予測・在庫補充支援")
try:
    with st.spinner("販売実績と予測を読み込んでいます…"):
        bundle = dashboard_data()
except FileNotFoundError:
    st.error("学習成果物が見つかりません。事前にデータ準備とモデル学習を完了してください。")
    st.stop()
except Exception:
    st.error("販売実績を読み込めませんでした。データベースの接続と学習成果物の整合性を確認してください。")
    st.stop()

origin = pd.Timestamp(bundle["metadata"]["forecast_origin"])
start, end = origin + pd.Timedelta(days=1), origin + pd.Timedelta(days=7)
st.caption(f"データ最終基準日：{origin:%Y年%m月%d日} ｜ 予測対象：{start:%Y/%m/%d}〜{end:%Y/%m/%d}")
names = bundle["products"].set_index("stock_code")["description"].to_dict()
code = st.selectbox("商品", list(names), format_func=lambda value: f"{value} ｜ {names[value]}", key="product")
history = bundle["history"].loc[lambda frame: frame["stock_code"].eq(code)]
forecast = bundle["forecasts"].set_index("stock_code").loc[code]
model_quantity, baseline_quantity = float(forecast["predicted_quantity"]), float(forecast["baseline_quantity"])
recent_quantity = int(history.loc[history["sales_date"].gt(origin - pd.Timedelta(days=7)), "quantity"].sum())

kpis = st.columns(3)
kpis[0].metric("直近7日間の販売数量", f"{recent_quantity:,} 個")
kpis[1].metric("翌7日間の予測 · LightGBM", f"{model_quantity:,.1f} 個")
kpis[2].metric("翌7日間の予測 · ベースライン", f"{baseline_quantity:,.0f} 個")
st.caption("予測は7日間の合計です。予測対象期間の完全な実績は存在せず、この未来予測自体の精度は未評価です。")

with st.container(border=True):
    st.subheader("販売実績", anchor=False)
    st.caption(f"過去90日間 · {history['sales_date'].min():%Y/%m/%d}〜{origin:%Y/%m/%d} ｜ {names[code]}")
    st.line_chart(history.rename(columns={"sales_date": "日付", "quantity": "販売数量"}),
                  x="日付", y="販売数量", color="#2563EB", height=280, use_container_width=True)
    st.caption("販売のない日は0として表示しています。欠品による販売機会損失は判別できません。")

left, right = st.columns(2, gap="large")
with left, st.container(border=True):
    st.subheader("予測精度の比較", anchor=False)
    scope = st.radio("評価対象", ["全体（30商品）", "選択商品"], horizontal=True, key="evaluation_scope")
    scores = test_scores(bundle, code if scope == "選択商品" else None)
    split = bundle["evaluation"]["splits"]["test"]
    st.caption(f"テスト基準日：{split['origin_start']}〜{split['origin_end']} · 7日間隔 ｜ 対象実績：{split['target_start']}〜{split['target_end']} · {scores['lightgbm']['rows']}件")
    st.dataframe(pd.DataFrame([
        {"モデル": label, "MAE（個）": f"{scores[name]['mae']:,.2f}", "WAPE": wape_text(scores[name]["wape"])}
        for name, label in [("lightgbm", "LightGBM"), ("baseline", "ベースライン")]
    ]), hide_index=True, use_container_width=True)
    if scores["lightgbm"]["mae"] > scores["baseline"]["mae"]:
        st.warning("この評価対象ではLightGBMの精度がベースラインを下回っています（MAE・WAPE）。")
    elif scores["lightgbm"]["mae"] < scores["baseline"]["mae"]:
        st.info("この評価対象ではLightGBMのMAE・WAPEがベースラインより小さくなっています。")
    else:
        st.info("この評価対象では両モデルの誤差は同じです。")
    overall = test_scores(bundle)
    st.caption(f"全体テスト：LightGBM MAE {overall['lightgbm']['mae']:.2f} / WAPE {wape_text(overall['lightgbm']['wape'])}、ベースライン MAE {overall['baseline']['mae']:.2f} / WAPE {wape_text(overall['baseline']['wape'])}。LightGBMが下回りました。")
    st.caption("誤差は小さいほど良い指標です。MAEは7日合計の平均絶対誤差、WAPEは絶対誤差合計÷実績合計。実績合計0のWAPEは算出不可です。")
    st.caption("上記は再学習前の評価用モデルの結果です。未来予測は全期間の完全ラベルで再学習した最終モデルを使用しています。テスト結果による再選定・再調整は行っていません。")

with right, st.container(border=True):
    st.subheader("補充シミュレーション", anchor=False)
    method = st.radio("補充計算に使う予測", ["LightGBM", "ベースライン"], horizontal=True, key="forecast_method")
    current = st.number_input("現在庫（仮定値・個）", min_value=0, max_value=10000000, value=300, step=10, key="current_stock")
    safety = st.number_input("安全在庫（仮定値・個）", min_value=0, max_value=10000000, value=100, step=10, key="safety_stock")
    demand = model_quantity if method == "LightGBM" else baseline_quantity
    st.metric("推奨補充数（簡易計算）", f"{recommended_replenishment(demand, current, safety):,} 個")
    st.caption(f"{method}の予測 {demand:,.1f}個 ＋ 安全在庫 {safety:,}個 − 現在庫 {current:,}個。0未満は0、端数は切り上げます。")
    st.caption("現在庫と安全在庫はユーザーが入力する仮定値です。実際の在庫データとの連携はありません。")
    st.caption("発注リードタイム、発注残、ロット、欠品コストは考慮しない簡易計算です。本格的な在庫最適化や発注指示ではありません。")

st.caption("DemandPilot · UCI Online Retailを用いたポートフォリオ ｜ 返品・キャンセルを除いた観測販売数量")
