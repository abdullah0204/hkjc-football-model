import streamlit as st
import pandas as pd


st.set_page_config(
    page_title="HKJC Football Goal Model",
    page_icon="⚽",
    layout="centered"
)

st.title("HKJC Football Goal Model")
st.write("Upload your HKJC Excel file and analyse Over / Under 2.5 or 3.5.")


uploaded_file = st.file_uploader(
    "Upload HKJC Excel file",
    type=["xlsx"]
)


def load_data(file):
    try:
        df = pd.read_excel(file, sheet_name="Model_Input")
    except Exception:
        df = pd.read_excel(file, sheet_name="Raw_Data")

    df.columns = [str(c).strip() for c in df.columns]

    return df


def find_column(df, possible_names):
    for name in possible_names:
        if name in df.columns:
            return name
    return None


def prepare_data(df):
    league_col = find_column(df, ["league_ch", "league_en", "league_code"])
    home_col = find_column(df, ["home_team_ch", "home_team_en"])
    away_col = find_column(df, ["away_team_ch", "away_team_en"])
    goals_col = find_column(df, ["ft_total_goals", "total_goals"])

    if not league_col or not home_col or not away_col or not goals_col:
        st.error("Excel 欄位不完整。需要 league, home team, away team, ft_total_goals。")
        st.stop()

    df = df.copy()

    df[goals_col] = pd.to_numeric(df[goals_col], errors="coerce")
    df = df.dropna(subset=[goals_col])

    return df, league_col, home_col, away_col, goals_col


def analyse(df, league_col, home_col, away_col, goals_col, league, home, away, line):
    league_df = df[df[league_col].astype(str).str.contains(league, case=False, na=False)]

    home_df = df[
        (df[home_col].astype(str).str.contains(home, case=False, na=False)) |
        (df[away_col].astype(str).str.contains(home, case=False, na=False))
    ]

    away_df = df[
        (df[home_col].astype(str).str.contains(away, case=False, na=False)) |
        (df[away_col].astype(str).str.contains(away, case=False, na=False))
    ]

    if len(league_df) == 0:
        league_df = df

    over_rate = (league_df[goals_col] > line).mean()
    under_rate = 1 - over_rate
    avg_goals = league_df[goals_col].mean()
    median_goals = league_df[goals_col].median()

    home_avg = home_df[goals_col].mean() if len(home_df) > 0 else None
    away_avg = away_df[goals_col].mean() if len(away_df) > 0 else None

    sample_size = len(league_df)

    if line == 2.5:
        if over_rate >= 0.58 and avg_goals >= 2.8:
            decision = "Bet Over 2.5"
        elif over_rate <= 0.48:
            decision = "Avoid Over 2.5"
        else:
            decision = "No Bet"

    elif line == 3.5:
        if over_rate >= 0.48 and avg_goals >= 3.4:
            decision = "Small Bet Over 3.5"
        elif under_rate >= 0.58:
            decision = "Small Bet Under 3.5"
        else:
            decision = "No Bet"

    else:
        decision = "No Bet"

    return {
        "sample_size": sample_size,
        "over_rate": over_rate,
        "under_rate": under_rate,
        "avg_goals": avg_goals,
        "median_goals": median_goals,
        "home_avg": home_avg,
        "away_avg": away_avg,
        "decision": decision
    }


if uploaded_file:
    df = load_data(uploaded_file)
    df, league_col, home_col, away_col, goals_col = prepare_data(df)

    st.success("Excel loaded successfully.")

    st.subheader("Match Input")

    league = st.text_input("League", value="澳洲盃")
    home = st.text_input("Home Team", value="坎培拉祖雲達斯")
    away = st.text_input("Away Team", value="昆比恩城")

    line = st.selectbox(
        "Goal Line",
        options=[2.5, 3.5],
        index=1
    )

    if st.button("Analyse Match"):
        result = analyse(
            df,
            league_col,
            home_col,
            away_col,
            goals_col,
            league,
            home,
            away,
            line
        )

        st.subheader("Model Result")

        st.metric("Decision", result["decision"])
        st.metric("Sample Size", result["sample_size"])
        st.metric("Average Goals", round(result["avg_goals"], 2))
        st.metric("Median Goals", round(result["median_goals"], 2))
        st.metric(f"Over {line}", f"{result['over_rate'] * 100:.1f}%")
        st.metric(f"Under {line}", f"{result['under_rate'] * 100:.1f}%")

        st.subheader("Team Reference")

        if result["home_avg"] is not None:
            st.write(f"Home team related matches average goals: {result['home_avg']:.2f}")
        else:
            st.write("Home team data not found.")

        if result["away_avg"] is not None:
            st.write(f"Away team related matches average goals: {result['away_avg']:.2f}")
        else:
            st.write("Away team data not found.")

        st.subheader("Simple Reading")

        if result["decision"] == "No Bet":
            st.write("模型認為今場沒有明顯優勢，建議跳過。")
        elif "Under" in result["decision"]:
            st.write("模型偏向細，但只適合小注，不建議串關。")
        elif "Over" in result["decision"]:
            st.write("模型偏向大，但仍要留意賠率是否有價值。")

else:
    st.info("Please upload your HKJC Excel file first.")
