import streamlit as st
import pandas as pd
from difflib import get_close_matches, SequenceMatcher

st.set_page_config(
    page_title="HKJC Football Goal Model",
    page_icon="⚽",
    layout="wide"
)

st.title("HKJC Football Goal Model")
st.write("Version 8 Fixed: 1.5 / 2.5 / 3.5 / 4.5 + Google Sheet database + Final Call")

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRvctEexKxd5XWdetu8Swx_UoiAYi8omOjKlIPGfpogGiuMlObrdEta81U5OUhwc9_QegMpmT3Iz3cZ/pub?gid=1411325930&single=true&output=csv"

NO_TEAM_OPTION = "不用球隊資料，只用聯賽數據"


@st.cache_data(ttl=300)
def load_database(sheet_csv_url):
    df = pd.read_csv(sheet_csv_url)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def find_column(df, names):
    for name in names:
        if name in df.columns:
            return name
    return None


def prepare_data(df):
    league_col = find_column(df, ["league_ch", "league_en", "league_code"])
    home_col = find_column(df, ["home_team_ch", "home_team_en"])
    away_col = find_column(df, ["away_team_ch", "away_team_en"])
    goals_col = find_column(df, ["ft_total_goals", "total_goals"])
    date_col = find_column(df, ["match_date", "kick_off_time", "date"])

    if league_col is None or home_col is None or away_col is None or goals_col is None:
        st.error("資料欄位不完整。需要 league, home team, away team, ft_total_goals。")
        st.stop()

    df = df.copy()
    df[goals_col] = pd.to_numeric(df[goals_col], errors="coerce")
    df = df.dropna(subset=[goals_col])

    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

    return df, league_col, home_col, away_col, goals_col, date_col


def get_all_leagues(df, league_col):
    return sorted(df[league_col].dropna().astype(str).unique().tolist())


def get_all_teams(df, home_col, away_col):
    home_teams = df[home_col].dropna().astype(str).tolist()
    away_teams = df[away_col].dropna().astype(str).tolist()
    return sorted(list(set(home_teams + away_teams)))


def search_leagues(keyword, league_list):
    if not keyword:
        return league_list

    keyword = str(keyword).strip().lower()

    exact = []
    for league in league_list:
        if keyword in league.lower():
            exact.append(league)

    fuzzy = get_close_matches(keyword, league_list, n=20, cutoff=0.20)

    output = []
    for item in exact + fuzzy:
        if item not in output:
            output.append(item)

    return output if output else league_list


def similarity(a, b):
    a = str(a).strip().lower()
    b = str(b).strip().lower()

    if not a or not b:
        return 0

    return SequenceMatcher(None, a, b).ratio()


def suggest_team_names(input_name, team_list):
    if not input_name:
        return [NO_TEAM_OPTION]

    input_name = str(input_name).strip()
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

    output = [NO_TEAM_OPTION]

    for team, score in scored[:8]:
        output.append(f"{team} | match {score * 100:.0f}%")

    return output


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
    }


def analyse_recent_trend(df, league_col, goals_col, date_col, selected_league, line):
    if date_col is None:
        return []

    league_df = df[df[league_col].astype(str) == selected_league].copy()
    league_df = league_df.dropna(subset=[date_col])

    if len(league_df) == 0:
        return []

    latest_date = league_df[date_col].max()
    rows = []

    for days in [30, 90, 180]:
        start_date = latest_date - pd.Timedelta(days=days)
        recent_df = league_df[league_df[date_col] >= start_date]

        if len(recent_df) == 0:
            continue

        rows.append({
            "Period": f"Last {days} days",
            "Matches": len(recent_df),
            "Average Goals": round(recent_df[goals_col].mean(), 2),
            "Median Goals": round(recent_df[goals_col].median(), 2),
            f"Over {line}": f"{(recent_df[goals_col] > line).mean() * 100:.1f}%",
            f"Under {line}": f"{(recent_df[goals_col] <= line).mean() * 100:.1f}%"
        })

    return rows


def get_recent_signal(trend_rows, league_over_rate, line):
    if not trend_rows:
        return "沒有足夠日期資料判斷近期走勢。"

    last_90 = None

    for row in trend_rows:
        if row["Period"] == "Last 90 days":
            last_90 = row
            break

    if last_90 is None:
        return "近期樣本不足，只參考兩年總體數據。"

    recent_over_text = last_90[f"Over {line}"].replace("%", "")
    recent_over = float(recent_over_text) / 100

    diff = recent_over - league_over_rate

    if diff >= 0.10:
        return "近期走勢升溫，近 90 日 Over 比兩年平均高 10% 以上。"

    if diff <= -0.10:
        return "近期走勢降溫，近 90 日 Over 比兩年平均低 10% 以上。"

    return "近期走勢接近兩年平均，沒有明顯升溫或降溫。"


def fair_odds(probability):
    if probability <= 0:
        return None
    return 1 / probability


def line_decision(line, final_over, final_under, final_avg):
    if line == 1.5:
        if final_over >= 0.68 and final_avg >= 2.00:
            return "Consider Over 1.5", "Over", "1.5 線偏低，模型支持大 1.5。"
        if final_under >= 0.45 and final_avg <= 1.70:
            return "Small Bet Under 1.5", "Under", "模型偏向極低入球，但 Under 1.5 風險較高。"
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


def build_final_call(decision, line, over_fair, under_fair, over_odds, under_odds):
    if decision == "No Bet":
        return "Final Call: No Bet。今場沒有足夠優勢，唔好為買而買。"

    if "Over" in decision:
        if over_odds > 0 and over_fair is not None:
            if over_odds > over_fair:
                return f"Final Call: 可考慮 Over {line}，只建議單關小注。公平賠率約 {over_fair:.2f}，你輸入賠率 {over_odds:.2f} 有 value。"
            return f"Final Call: No Bet。Over {line} 方向可以，但賠率低過公平賠率 {over_fair:.2f}。"

        return f"Final Call: 偏 Over {line}，但未輸入賠率。要高過公平賠率 {over_fair:.2f} 先考慮。"

    if "Under" in decision or "Avoid Over" in decision or "Prefer Under" in decision:
        if under_odds > 0 and under_fair is not None:
            if under_odds > under_fair:
                return f"Final Call: 可考慮 Under {line}，只建議單關小注。公平賠率約 {under_fair:.2f}，你輸入賠率 {under_odds:.2f} 有 value。"
            return f"Final Call: No Bet。Under {line} 方向可以，但賠率低過公平賠率 {under_fair:.2f}。"

        return f"Final Call: 偏 Under {line}，但未輸入賠率。要高過公平賠率 {under_fair:.2f} 先考慮。"

    return "Final Call: No Bet。"


def make_decision(league_result, home_result, away_result, line, over_odds, under_odds, recent_signal):
    league_over = league_result["over_rate"]
    league_avg = league_result["avg_goals"]

    team_results = []

    if home_result:
        team_results.append(home_result)

    if away_result:
        team_results.append(away_result)

    if len(team_results) > 0:
        team_sample = sum(t["matches"] for t in team_results)
        team_over = sum(t["over_rate"] for t in team_results) / len(team_results)
        team_avg = sum(t["avg_goals"] for t in team_results) / len(team_results)
    else:
        team_sample = 0
        team_over = None
        team_avg = None

    if team_over is not None and team_sample >= 10:
        final_over = league_over * 0.65 + team_over * 0.35
        final_avg = league_avg * 0.65 + team_avg * 0.35
        data_source = "League + Team"
    else:
        final_over = league_over
        final_avg = league_avg
        data_source = "League only"

    if "近期走勢降溫" in recent_signal:
        final_over = max(0, final_over - 0.03)
        final_avg = max(0, final_avg - 0.10)

    if "近期走勢升溫" in recent_signal:
        final_over = min(1, final_over + 0.03)
        final_avg = final_avg + 0.10

    final_under = 1 - final_over

    over_fair = fair_odds(final_over)
    under_fair = fair_odds(final_under)

    decision, side, note = line_decision(line, final_over, final_under, final_avg)

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

    final_call = build_final_call(
        decision,
        line,
        over_fair,
        under_fair,
        over_odds,
        under_odds
    )

    return {
        "decision": decision,
        "note": note,
        "value_note": value_note,
        "confidence": confidence,
        "confidence_note": confidence_note,
        "parlay_note": "不建議串關。",
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

st.sidebar.header("Odds Input")

over_odds = st.sidebar.number_input("Over Odds", min_value=0.00, value=0.00, step=0.01)
under_odds = st.sidebar.number_input("Under Odds", min_value=0.00, value=0.00, step=0.01)

analyse_button = st.sidebar.button("Analyse")

display_home = home_team_input if selected_home_team == NO_TEAM_OPTION else selected_home_team
display_away = away_team_input if selected_away_team == NO_TEAM_OPTION else selected_away_team

st.subheader("Selected Match")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.write("League")
    st.info(selected_league)

with c2:
    st.write("Goal Line")
    st.info(str(line))

with c3:
    st.write("Home Team")
    st.info(display_home)

with c4:
    st.write("Away Team")
    st.info(display_away)

if analyse_button:
    league_result = analyse_league(df, league_col, goals_col, selected_league, line)

    if league_result is None:
        st.error("找不到此聯賽資料。")
        st.stop()

    home_result = analyse_team(df, home_col, away_col, goals_col, selected_home_team, line)
    away_result = analyse_team(df, home_col, away_col, goals_col, selected_away_team, line)

    trend_rows = analyse_recent_trend(df, league_col, goals_col, date_col, selected_league, line)
    recent_signal = get_recent_signal(trend_rows, league_result["over_rate"], line)

    final = make_decision(
        league_result,
        home_result,
        away_result,
        line,
        over_odds,
        under_odds,
        recent_signal
    )

    st.subheader("Final Call")
    st.success(final["final_call"])

    st.subheader("Model Decision")

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric("Decision", final["decision"])

    with m2:
        st.metric(f"Final Over {line}", f"{final['final_over'] * 100:.1f}%")

    with m3:
        st.metric(f"Final Under {line}", f"{final['final_under'] * 100:.1f}%")

    with m4:
        st.metric("Final Avg Goals", f"{final['final_avg']:.2f}")

    m5, m6, m7, m8 = st.columns(4)

    with m5:
        st.metric("Confidence", final["confidence"])

    with m6:
        st.metric("Data Source", final["data_source"])

    with m7:
        st.metric("Fair Over Odds", f"{final['over_fair']:.2f}")

    with m8:
        st.metric("Fair Under Odds", f"{final['under_fair']:.2f}")

    st.subheader("League Reference")

    league_table = pd.DataFrame([
        {
            "League": selected_league,
            "Matches": league_result["matches"],
            "Average Goals": round(league_result["avg_goals"], 2),
            "Median Goals": round(league_result["median_goals"], 2),
            "Over 1.5": f"{league_result['over_1_5'] * 100:.1f}%",
            "Over 2.5": f"{league_result['over_2_5'] * 100:.1f}%",
            "Over 3.5": f"{league_result['over_3_5'] * 100:.1f}%",
            "Over 4.5": f"{league_result['over_4_5'] * 100:.1f}%",
            f"Over {line}": f"{league_result['over_rate'] * 100:.1f}%",
            f"Under {line}": f"{league_result['under_rate'] * 100:.1f}%"
        }
    ])

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
