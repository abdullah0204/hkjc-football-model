import streamlit as st
import pandas as pd
from difflib import get_close_matches, SequenceMatcher
from datetime import date

st.set_page_config(
    page_title="HKJC Football Goal Model",
    page_icon="⚽",
    layout="wide"
)

st.title("HKJC Football Goal Model")
st.write("Version 10A Fixed: Model + Google Sheet database + Bet Log copy row")

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRvctEexKxd5XWdetu8Swx_UoiAYi8omOjKlIPGfpogGiuMlObrdEta81U5OUhwc9_QegMpmT3Iz3cZ/pub?gid=1411325930&single=true&output=csv"

BET_LOG_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQMMbUrTIsjnOdZZrxUf7t8rhMeXeCYCrPu9-lTmHTHnB34sqq7kAlUHpTKcP7VuQ/pub?gid=1909142678&single=true&output=csv"

NO_TEAM_OPTION = "不用球隊資料，只用聯賽數據"


@st.cache_data(ttl=300)
def load_csv(url):
    df = pd.read_csv(url)
    if output:
        return output

    return league_list
st.sidebar.header("Database")

sheet_url_input = st.sidebar.text_input(
    "Google Sheet CSV URL",
    value=SHEET_CSV_URL
)

bet_log_url_input = st.sidebar.text_input(
    "Bet Log CSV URL",
    value=BET_LOG_CSV_URL
)

if st.sidebar.button("Refresh database"):
    st.cache_data.clear()

try:
    df = load_csv(sheet_url_input)
except Exception as e:
    st.error(f"讀取 database 失敗：{e}")
    st.stop()

try:
    bet_log_df = load_csv(bet_log_url_input)
except Exception:
    bet_log_df = pd.DataFrame()
        st.subheader("Reading")

        st.write(final["note"])
        st.write(final["confidence_note"])
        st.write(final["value_note"])
        st.write(final["parlay_note"])
        st.write(final["recent_signal"])

    else:
        st.info("Choose a league and goal line, then click Analyse.")

with tab_bet_log:
    show_bet_log_dashboard(bet_log_df)
