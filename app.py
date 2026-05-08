import streamlit as st
import pandas as pd
import requests
from difflib import get_close_matches, SequenceMatcher
from datetime import date

st.set_page_config(
    page_title="HKJC Football Goal Model",
    page_icon="⚽",
    layout="wide"
)

st.title("HKJC Football Goal Model")
st.write("Version 10B: Auto Save Bet to Google Sheet")

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRvctEexKxd5XWdetu8Swx_UoiAYi8omOjKlIPGfpogGiuMlObrdEta81U5OUhwc9_QegMpmT3Iz3cZ/pub?gid=1411325930&single=true&output=csv"

BET_LOG_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQMMbUrTIsjnOdZZrxUf7t8rhMeXeCYCrPu9-lTmHTHnB34sqq7kAlUHpTKcP7VuQ/pub?gid=1909142678&single=true&output=csv"

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyOpCg7z7Mm6PJ1G1fTduYlNFRUase3ZZsqR4lHXQtqwykklDfrDdtO0Ia9oGYnpc4F/exec"

API_TOKEN = "hkjc_private_2026"

NO_TEAM_OPTION = "不用球隊資料，只用聯賽數據"


@st.cache_data(ttl=300)
def load_csv(url):
    df = pd.read_csv(url)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def find_column(df, possible_names):
    for name in possible_names:
        if name in df.columns:
            return name
    return None


def prepare_main_data(df):
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


def make_league_list(df, league_col):
    return sorted(df[league_col].dropna().astype(str).unique().tolist())


def make_team_list(df, home_col, away_col):
    home_teams = df[home_col].dropna().astype(str).tolist()
    away_teams = df[away_col].dropna().astype(str).tolist()
    return sorted(list(set(home_teams + away_teams)))


def search_leagues(keyword, league_list):
    if not keyword:
        return league_list

    keyword = str(keyword).strip().lower()

    exact = []
    for league in league_list:
        if keyword in str(league).lower():
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


def get_team_suggestions(input_name, team_list):
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
    if not selection:
        return NO_TEAM_OPTION

    if selection == NO_TEAM_OPTION:
        return NO_TEAM_OPTION

    if " | match " in selection:
        return selection.split(" | match ")[0].strip()

    return str(selection).strip()


def analyse_group(group_df, goals_col, line):
    over_rate = (group_df[goals_col] > line).mean()
    under_rate = 1 - over_rate

    return {
        "matches": len(group_df),
        "avg_goals": group_df[goals_col].mean(),
        "median_goals": group_df[goals_col].median(),
        "over_rate": over_rate,
        "under_rate": under_rate,
        "over_1_5": (group_df[goals_col] > 1.5).mean(),
        "over_2_5": (group_df[goals_col] > 2.5).mean(),
        "over_3_5": (group_df[goals_col] > 3.5).mean(),
        "over_4_5": (group_df[goals_col] > 4.5).mean()
    }


def analyse_league(df, league_col, goals_col, selected_league, line):
    league_df = df[df[league_col].astype(str) == selected_league].copy()

    if len(league_df) == 0:
        return None

    return analyse_group(league_df, goals_col, line)


def analyse_team(df, home_col, away_col, goals_col, team_name, line):
    if not team_name or team_name == NO_TEAM_OPTION:
        return None

    team_df = df[
        (df[home_col].astype(str) == team_name) |
        (df[away_col].astype(str) == team_name)
    ].copy()

    if len(team_df) == 0:
        return None

    result = analyse_group(team_df, goals_col, line)
    result["team"] = team_name
    return result


def analyse_recent_trend(df, league_col, goals_col, date_col, selected_league, line):
    if date_col is None:
        return [], "沒有足夠日期資料判斷近期走勢。"

    league_df = df[df[league_col].astype(str) == selected_league].copy()
    league_df = league_df.dropna(subset=[date_col])

    if len(league_df) == 0:
        return [], "沒有足夠日期資料判斷近期走勢。"

    latest_date = league_df[date_col].max()
    full_over = (league_df[goals_col] > line).mean()

    rows = []
    recent_90_over = None

    for days in [30, 90, 180]:
        start_date = latest_date - pd.Timedelta(days=days)
        recent_df = league_df[league_df[date_col] >= start_date]

        if len(recent_df) == 0:
            continue

        over_rate = (recent_df[goals_col] > line).mean()
        under_rate = 1 - over_rate

        if days == 90:
            recent_90_over = over_rate

        rows.append({
            "Period": f"Last {days} days",
            "Matches": len(recent_df),
            "Average Goals": round(recent_df[goals_col].mean(), 2),
            "Median Goals": round(recent_df[goals_col].median(), 2),
            f"Over {line}": f"{over_rate * 100:.1f}%",
            f"Under {line}": f"{under_rate * 100:.1f}%"
        })

    if recent_90_over is None:
        return rows, "近期樣本不足，只參考兩年總體數據。"

    diff = recent_90_over - full_over

    if diff >= 0.10:
        return rows, "近期走勢升溫，近 90 日 Over 比兩年平均高 10% 以上。"

    if diff <= -0.10:
        return rows, "近期走勢降溫，近 90 日 Over 比兩年平均低 10% 以上。"

    return rows, "近期走勢接近兩年平均，沒有明顯升溫或降溫。"


def fair_odds(probability):
    if probability <= 0:
        return 0
    return 1 / probability


def decide_line(line, final_over, final_avg):
    final_under = 1 - final_over

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

    return "No Bet", "None", "不支援此盤口。"


def make_final_decision(league_result, home_result, away_result, line, over_odds, under_odds, signal):
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

    if "降溫" in signal:
        final_over = max(0, final_over - 0.03)
        final_avg = max(0, final_avg - 0.10)

    if "升溫" in signal:
        final_over = min(1, final_over + 0.03)
        final_avg = final_avg + 0.10

    final_under = 1 - final_over

    over_fair = fair_odds(final_over)
    under_fair = fair_odds(final_under)

    decision, side, note = decide_line(line, final_over, final_avg)

    value_note = "未輸入賠率，暫時只作機率判斷。"

    if side == "Over" and over_odds > 0:
        if over_odds > over_fair:
            value_note = "Over 賠率高過模型公平賠率，有 value。"
        else:
            value_note = "Over 賠率低過模型公平賠率，不買。"
            decision = "No Bet"
            side = "None"

    if side == "Under" and under_odds > 0:
        if under_odds > under_fair:
            value_note = "Under 賠率高過模型公平賠率，有 value。"
        else:
            value_note = "Under 賠率低過模型公平賠率，不買。"
            decision = "No Bet"
            side = "None"

    if team_sample == 0:
        confidence = "Medium" if abs(final_over - 0.5) >= 0.08 else "Low"
        confidence_note = "今次只用聯賽數據，沒有使用球隊資料。"
    elif team_sample < 10:
        confidence = "Low"
        confidence_note = "球隊樣本太少，主要仍以聯賽數據判斷。"
    else:
        confidence = "High" if abs(final_over - 0.5) >= 0.10 else "Medium"
        confidence_note = "今次已加入球隊資料。"

    if decision == "No
