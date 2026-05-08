import streamlit as st
import pandas as pd
from difflib import get_close_matches, SequenceMatcher

st.set_page_config(
    page_title="HKJC Football Goal Model",
    page_icon="⚽",
    layout="wide"
)

st.title("HKJC Football Goal Model")
st.write("Version 8: 1.5 / 2.5 / 3.5 / 4.5 model + safer team matching + final call")
def similarity(a, b):
    a = str(a).strip().lower()
    b = str(b).strip().lower()

    if not a or not b:
        return 0

    return SequenceMatcher(None, a, b).ratio()


def suggest_team_names(input_name, team_list):
    if not input_name:
        return [NO_TEAM_OPTION]

    input_name = input_name.strip()
    scored = []

    for team in team_list:
        team_text = str(team).strip()
        score = similarity(input_name, team_text)

        if input_name.lower() == team_text.lower():
            score = 1.00
        elif input_name.lower() in team_text.lower():
            score = max(score, 0.80)
        elif team_text.lower() in input_name.lower():
            score = max(score, 0.75)

        if score >= 0.45:
            scored.append((team_text, score))

    scored = sorted(scored, key=lambda x: x[1], reverse=True)

    combined = [NO_TEAM_OPTION]

    for team, score in scored[:8]:
        label = f"{team}  | match {score * 100:.0f}%"
        combined.append(label)

    return combined


def extract_team_name(selection):
    if not selection or selection == NO_TEAM_OPTION:
        return NO_TEAM_OPTION

    if " | match " in selection:
        return selection.split(" | match ")[0].strip()

    return selection.strip()


def analyse_league(df, league_col, goals_col, selected_league, line):
    league_df = df[df[league_col].astype(str) == selected_league].copy()

    if len(league_df) == 0:
        return None

    over_rate = (league_df[goals_col] > line).mean()
    under_rate = 1 - over_rate

    return {
        "matches": len(league_df),
        "avg_goals": league_df[goals_col].mean(),
        "median_goals": league_df[goals_col].median(),
        "over_rate": over_rate,
        "under_rate": under_rate,
        "over_1_5": (league_df[goals_col] > 1.5).mean(),
        "over_2_5": (league_df[goals_col] > 2.5).mean(),
        "over_3_5": (league_df[goals_col] > 3.5).mean(),
        "over_4_5": (league_df[goals_col] > 4.5).mean()
    }


def analyse_team(df, home_col, away_col, goals_col, team_name, line):
    if not team_name or team_name == NO_TEAM_OPTION:
        return None

    team_df = df[
        (df[home_col].astype(str) == team_name) |
        (df[away_col].astype(str) == team_name)
    ].copy()

    if len(team_df) == 0:
        return None

    over_rate = (team_df[goals_col] > line).mean()
    under_rate = 1 - over_rate

    return {
        "team": team_name,
        "matches": len(team_df),
        "avg_goals": team_df[goals_col].mean(),
        "median_goals": team_df[goals_col].median(),
        "over_rate": over_rate,
        "under_rate": under_rate,
        "over_1_5": (team_df[goals_col] > 1.5).mean(),
        "over_2_5": (team_df[goals_col] > 2.5).mean(),
        "over_3_5": (team_df[goals_col] > 3.5).mean(),
        "over_4_5": (team_df[goals_col] > 4.5).mean()
def make_line_decision(line, final_over, final_under, final_avg):
    if line == 1.5:
        if final_over >= 0.68 and final_avg >= 2.00:
            return "Consider Over 1.5", "Over", "1.5 線偏低，模型支持大 1.5。"
        if final_under >= 0.45 and final_avg <= 1.70:
            return "Small Bet Under 1.5", "Under", "模型偏向極低入球，但 Under 1.5 風險高。"
        return "No Bet", "None", "1.5 線沒有足夠價值。"

    if line == 2.5:
        if final_over >= 0.58 and final_avg >= 2.80:
            return "Bet Over 2.5", "Over", "模型偏向大 2.5。"
        if final_under >= 0.58 and final_avg <= 2.50:
            return "Avoid Over 2.5", "Under", "模型偏向低入球，不建議買大 2.5。"
        return "No Bet", "None", "2.5 線沒有明顯優勢。"

    if line == 3.5:
        if final_over >= 0.48 and final_avg >= 3.40:
            return "Small Bet Over 3.5", "Over", "模型偏向大 3.5，但只適合小注。"
        if final_under >= 0.58:
            return "Small Bet Under 3.5", "Under", "3.5 線偏高，模型較支持細。"
        return "No Bet", "None", "3.5 線沒有足夠優勢。"

    if line == 4.5:
        if final_over >= 0.35 and final_avg >= 4.00:
            return "Small Bet Over 4.5", "Over", "模型有超高入球方向，但 4.5 線只適合極小注。"
        if final_under >= 0.70:
            return "Prefer Under 4.5", "Under", "4.5 線很高，模型偏向細。"
        return "No Bet", "None", "4.5 線波動太大，沒有清晰優勢。"

    return "No Bet", "None", "暫時只支援 1.5、2.5、3.5、4.5。"


def build_final_call(decision, line, final_over, final_under, over_fair, under_fair, over_odds, under_odds, confidence, data_source):
    if decision == "No Bet":
        return "Final Call: No Bet。今場沒有足夠優勢，唔好為買而買。"

    if "Over" in decision:
        if over_odds > 0 and over_fair is not None:
            if over_odds > over_fair:
                return f"Final Call: 可考慮 Over {line}，但只建議單關小注。模型公平賠率約 {over_fair:.2f}，你輸入賠率 {over_odds:.2f} 有 value。"
            return f"Final Call: No Bet。Over {line} 方向可以，但賠率低過模型公平賠率 {over_fair:.2f}。"

        return f"Final Call: 偏 Over {line}，但未輸入賠率。要高過公平賠率 {over_fair:.2f} 先考慮。"

    if "Under" in decision or "Avoid Over" in decision or "Prefer Under" in decision:
        if under_odds > 0 and under_fair is not None:
            if under_odds > under_fair:
                return f"Final Call: 可考慮 Under {line}，但只建議單關小注。模型公平賠率約 {under_fair:.2f}，你輸入賠率 {under_odds:.2f} 有 value。"
            return f"Final Call: No Bet。Under {line} 方向可以，但賠率低過模型公平賠率 {under_fair:.2f}。"

        return f"Final Call: 偏 Under {line}，但未輸入賠率。要高過公平賠率 {under_fair:.2f} 先考慮。"

    return "Final Call: No Bet。"
    decision, side, note = make_line_decision(line, final_over, final_under, final_avg)

    value_note = "未輸入賠率，暫時只作機率判斷。"

    if side == "Over" and over_odds > 0 and over_fair is not None:
        if over_odds > over_fair:
            value_note = "Over 賠率高過模型公平賠率，有價值。"
        else:
            value_note = "Over 賠率未夠值，不建議硬買。"
            decision = "No Bet"

    if side == "Under" and under_odds > 0 and under_fair is not None:
        if under_odds > under_fair:
            value_note = "Under 賠率高過模型公平賠率，有價值。"
        else:
            value_note = "Under 賠率未夠值，不建議硬買。"
            decision = "No Bet"

    if team_sample == 0:
        confidence = "Medium" if abs(final_over - 0.5) >= 0.08 else "Low"
        confidence_note = "今次只用聯賽數據，沒有使用球隊資料。"
    elif team_sample < 10:
        confidence = "Low"
        confidence_note = "球隊樣本太少，主要仍以聯賽數據判斷。"
    else:
        confidence = "High" if abs(final_over - 0.5) >= 0.10 else "Medium"
        confidence_note = "今次已加入球隊資料。"

    parlay_note = "不建議串關。"

    final_call = build_final_call(
        decision,
        line,
        final_over,
        final_under,
        over_fair,
        under_fair,
        over_odds,
        under_odds,
        confidence,
        data_source
    )

    return {
        "decision": decision,
        "note": note,
        "value_note": value_note,
        "confidence": confidence,
        "confidence_note": confidence_note,
        "parlay_note": parlay_note,
        "recent_signal": recent_signal,
        "final_over": final_over,
        "final_under": final_under,
        "final_avg": final_avg,
        "over_fair": over_fair,
        "under_fair": under_fair,
        "data_source": data_source,
        "team_sample": team_sample,
        "final_call": final_call
    }


st.sidebar.header("Database")

sheet_url_input = st.sidebar.text_input(
    "Google Sheet CSV URL",
    value=SHEET_CSV_URL
)

if st.sidebar.button("Refresh database"):
    st.cache_data.clear()

try:
    df = load_database(sheet_url_input)
except Exception as e:
    st.error(f"讀取 database 失敗：{e}")
    st.stop()

df, league_col, home_col, away_col, goals_col, date_col = prepare_data(df)

team_list = get_all_teams(df, home_col, away_col)
league_list = get_all_leagues(df, league_col)

st.success(f"Database loaded successfully. Total rows: {len(df)}")

st.sidebar.header("Match Input")

league_keyword = st.sidebar.text_input("Search League", value="澳洲盃")
filtered_leagues = search_leagues(league_keyword, league_list)

selected_league = st.sidebar.selectbox("Select League", filtered_leagues)

line = st.sidebar.selectbox("Goal Line", [1.5, 2.5, 3.5, 4.5], index=2)

home_team_input = st.sidebar.text_input("Home Team", value="坎培拉祖雲達斯")
away_team_input = st.sidebar.text_input("Away Team", value="昆比恩城")

home_suggestions = suggest_team_names(home_team_input, team_list)
away_suggestions = suggest_team_names(away_team_input, team_list)

selected_home_label = st.sidebar.selectbox("Suggested Home Team", home_suggestions)
selected_away_label = st.sidebar.selectbox("Suggested Away Team", away_suggestions)

selected_home_team = extract_team_name(selected_home_label)
selected_away_team = extract_team_name(selected_away_label)
    st.subheader("Final Call")
    st.success(final["final_call"])
            "Over 1.5": f"{league_result['over_1_5'] * 100:.1f}%",
            "Over 2.5": f"{league_result['over_2_5'] * 100:.1f}%",
            "Over 3.5": f"{league_result['over_3_5'] * 100:.1f}%",
            "Over 4.5": f"{league_result['over_4_5'] * 100:.1f}%",
            f"Over {line}": f"{league_result['over_rate'] * 100:.1f}%",
            f"Under {line}": f"{league_result['under_rate'] * 100:.1f}%"
        }
    

    st.dataframe(league_table, use_container_width=True)

    st.subheader("Recent Trend")

    if trend_rows:
        trend_table = pd.DataFrame(trend_rows)
        st.dataframe(trend_table, use_container_width=True)
        st.info(recent_signal)
    else:
        st.warning("沒有足夠日期資料顯示近期走勢。")

    st.subheader("Team Reference")

    team_rows = []

    if home_result:
        team_rows.append({
            "Side": "Home",
            "Team": home_result["team"],
            "Matches": home_result["matches"],
            "Average Goals": round(home_result["avg_goals"], 2),
            "Over 1.5": f"{home_result['over_1_5'] * 100:.1f}%",
            "Over 2.5": f"{home_result['over_2_5'] * 100:.1f}%",
            "Over 3.5": f"{home_result['over_3_5'] * 100:.1f}%",
            "Over 4.5": f"{home_result['over_4_5'] * 100:.1f}%",
            f"Over {line}": f"{home_result['over_rate'] * 100:.1f}%"
        })

    if away_result:
        team_rows.append({
            "Side": "Away",
            "Team": away_result["team"],
            "Matches": away_result["matches"],
            "Average Goals": round(away_result["avg_goals"], 2),
            "Over 1.5": f"{away_result['over_1_5'] * 100:.1f}%",
            "Over 2.5": f"{away_result['over_2_5'] * 100:.1f}%",
            "Over 3.5": f"{away_result['over_3_5'] * 100:.1f}%",
            "Over 4.5": f"{away_result['over_4_5'] * 100:.1f}%",
            f"Over {line}": f"{away_result['over_rate'] * 100:.1f}%"
        })

    if team_rows:
        st.dataframe(pd.DataFrame(team_rows), use_container_width=True)
    else:
        st.warning("No valid team selected. Model uses league data only.")

    st.subheader("Reading")

    st.write(final["note"])
    st.write(final["confidence_note"])
    st.write(final["value_note"])
    st.write(final["parlay_note"])
    st.write(final["recent_signal"])

    if final["decision"] == "No Bet":
        st.warning("建議跳過，唔好為買而買。")
    elif "Under" in final["decision"] or "Avoid Over" in final["decision"]:
        st.warning("只適合小注，不建議放入串關。")
    elif "Over" in final["decision"]:
        st.success("可以考慮，但仍要檢查賠率是否有價值。")

else:
    st.info("Choose a league and goal line, then click Analyse.")
