"""Application shell; forecasting UI is added after the pipeline is ready."""

import streamlit as st

from demandpilot.db import check_database

st.set_page_config(page_title="DemandPilot", page_icon="📦", layout="wide")
st.title("DemandPilot")
st.caption("需要予測・在庫補充支援システム")

try:
    check_database()
except Exception:
    st.error("データベースに接続できません。コンテナの状態と設定を確認してください。")
else:
    st.success("PostgreSQLへの接続を確認しました。")

st.info("実行基盤を準備しました。販売データ・予測・補充シミュレーションは次の段階で実装します。")
st.caption("現在庫は仮定値です。補充シミュレーションは簡易計算であり、本格的な在庫最適化ではありません。")
