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
st.write("Version 10A: Goal model + Google Sheet database + Bet Log copy row")
def infer_bet_side(decision):
    if "Over" in decision and "Avoid" not in decision:
        return "Over"

    if "Under" in decision or "Avoid Over" in decision or "Prefer Under" in decision:
        return "Under"

    return "No Bet"


def generate_bet_log_row(bet_date, league, home, away, line, decision, bet_side, odds, stake):
    result = "Pending"
    profit_loss = ""

    values = [
        bet_date,
        league,
        home,
        away,
        line,
        decision,
        bet_side,
        odds,
        stake,
        result,
        profit_loss
    ]

    clean_values = []

    for value in values:
        text = str(value)
        text = text.replace('"', '""')
        clean_values.append(f'"{text}"')

    return ",".join(clean_values)
        st.write("欄位：bet_date, league_ch, home_team_ch, away_team_ch, line, model_decision, bet_side, odds, stake, result, profit_loss")
    st.sidebar.header("Bet Log Input")

    bet_date = st.sidebar.date_input("Bet Date", value=date.today())
    stake = st.sidebar.number_input("Stake", min_value=0.00, value=100.00, step=10.00)
    manual_bet_side = st.sidebar.selectbox("Bet Side to Log", ["Auto", "Over", "Under", "No Bet"])
        st.subheader("Copy to Bet Log")

        auto_side = infer_bet_side(final["decision"])
        chosen_side = auto_side if manual_bet_side == "Auto" else manual_bet_side

        chosen_odds = 0

        if chosen_side == "Over":
            chosen_odds = over_odds
        elif chosen_side == "Under":
            chosen_odds = under_odds

        bet_log_row = generate_bet_log_row(
            str(bet_date),
            selected_league,
            display_home,
            display_away,
            line,
            final["decision"],
            chosen_side,
            chosen_odds,
            stake,
        )

        bet_log_preview = pd.DataFrame([
            {
                "bet_date": str(bet_date),
                "league_ch": selected_league,
                "home_team_ch": display_home,
                "away_team_ch": display_away,
                "line": line,
                "model_decision": final["decision"],
                "bet_side": chosen_side,
                "odds": chosen_odds,
                "stake": stake,
                "result": "Pending",
                "profit_loss": ""
            }
        ])

        st.dataframe(bet_log_preview, use_container_width=True)

        st.write("Copy this row and paste it into the bottom of your bet_log Google Sheet:")
        st.code(bet_log_row, language="csv")
