import streamlit as st
import pandas as pd
from difflib import SequenceMatcher
from datetime import date

st.set_page_config(
    page_title="HKJC Football Goal Model",
    page_icon="⚽",
    layout="wide"
)

st.title("HKJC Football Goal Model")
st.write("Version 19A: Team Backtest + Strong Picks Scanner + Backtest")

SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRvctEexKxd5XWdetu8Swx_UoiAYi8omOjKlIPGfpogGiuMlObrdEta81U5OUhwc9_QegMpmT3Iz3cZ/pub?gid=1411325930&single=true&output=csv"

UPCOMING_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQL4uV8fCNh5wEuweCiffRi0Bq5Xl4kHykQzJrKQldYFjSL-8vO6iMC99A8TI2CDrcR6pZEh4k8tuUY/pub?gid=0&single=true&output=csv"

NO_TEAM_OPTION = "不用球隊資料，只用聯賽數據"
SUPPORTED_LINES = [2.5, 3.5]


@st.cache_data(ttl=60)
def load_csv(url):
    df = pd.read_csv(url)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def find_column(df, possible_names):
    for name in possible_names:
        if name in df.columns:
            return name
    return None


def clean_date_for_model(value):
    if pd.isna(value):
        return pd.NaT

    text = str(value).strip()
    extracted = pd.Series([text]).str.extract(r"(\d{4}-\d{2}-\d{2})").iloc[0, 0]

    if pd.notna(extracted):
        return pd.to_datetime(extracted, errors="coerce")

    return pd.to_datetime(text, errors="coerce")


def prepare_main_data(df):
    league_col = find_column(df, ["league_ch", "league", "league_name_ch", "league_code"])
    home_col = find_column(df, ["home_team_ch", "home_team", "home", "home_name_ch"])
    away_col = find_column(df, ["away_team_ch", "away_team", "away", "away_name_ch"])

    home_goals_col = find_column(df, ["ft_home_goals", "home_goals", "home_score", "ft_home_score"])
    away_goals_col = find_column(df, ["ft_away_goals", "away_goals", "away_score", "ft_away_score"])

    goals_col = find_column(df, ["ft_total_goals", "total_goals", "ft_total", "goals_total"])

    date_col = find_column(df, [
        "match_date",
        "match_datetime",
        "match_time",
        "kick_off_time",
        "kickoff_time",
        "kick_off",
        "date",
        "start_time"
    ])

    if league_col is None:
        st.error("找不到 league_ch 欄位。")
        st.stop()

    if home_col is None:
        st.error("找不到 home_team_ch 欄位。")
        st.stop()

    if away_col is None:
        st.error("找不到 away_team_ch 欄位。")
        st.stop()

    if goals_col is None:
        if home_goals_col and away_goals_col:
            df = df.copy()
            df[home_goals_col] = pd.to_numeric(df[home_goals_col], errors="coerce")
            df[away_goals_col] = pd.to_numeric(df[away_goals_col], errors="coerce")
            df["ft_total_goals_auto"] = df[home_goals_col] + df[away_goals_col]
            goals_col = "ft_total_goals_auto"
        else:
            st.error("找不到 ft_total_goals，也找不到 ft_home_goals + ft_away_goals。")
            st.stop()

    if date_col is None:
        st.error("找不到日期欄位。")
        st.stop()

    df = df.copy()

    df[goals_col] = pd.to_numeric(df[goals_col], errors="coerce")
    df = df.dropna(subset=[goals_col])

    if home_goals_col:
        df[home_goals_col] = pd.to_numeric(df[home_goals_col], errors="coerce")

    if away_goals_col:
        df[away_goals_col] = pd.to_numeric(df[away_goals_col], errors="coerce")

    df[date_col] = df[date_col].apply(clean_date_for_model)
    df = df.dropna(subset=[date_col])

    return df, league_col, home_col, away_col, goals_col, home_goals_col, away_goals_col, date_col


def prepare_upcoming_data(df):
    if df.empty:
        return df

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    required_cols = [
        "match_date",
        "home_team_ch",
        "away_team_ch",
        "line",
        "over_odds",
        "under_odds",
        "stake"
    ]

    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    if "league_ch" not in df.columns:
        df["league_ch"] = ""

    df["line"] = pd.to_numeric(df["line"], errors="coerce")
    df["over_odds"] = pd.to_numeric(df["over_odds"], errors="coerce").fillna(0)
    df["under_odds"] = pd.to_numeric(df["under_odds"], errors="coerce").fillna(0)
    df["stake"] = pd.to_numeric(df["stake"], errors="coerce").fillna(100)

    df = df.dropna(subset=["line"])
    df = df[df["home_team_ch"].astype(str).str.strip() != ""]
    df = df[df["away_team_ch"].astype(str).str.strip() != ""]

    return df


def make_league_list(df, league_col):
    return sorted(df[league_col].dropna().astype(str).unique().tolist())


def make_team_list(df, home_col, away_col):
    home_teams = df[home_col].dropna().astype(str).tolist()
    away_teams = df[away_col].dropna().astype(str).tolist()
    return sorted(list(set(home_teams + away_teams)))


def similarity(a, b):
    a = str(a).strip().lower()
    b = str(b).strip().lower()

    if not a or not b:
        return 0

    return SequenceMatcher(None, a, b).ratio()


def get_best_team_match(input_name, team_list, min_score=0.40):
    if not input_name:
        return NO_TEAM_OPTION, 0

    input_name = str(input_name).strip()
    best_team = NO_TEAM_OPTION
    best_score = 0

    for team in team_list:
        team_text = str(team).strip()
        score = similarity(input_name, team_text)

        if input_name.lower() == team_text.lower():
            score = 1.00
        elif input_name.lower() in team_text.lower():
            score = max(score, 0.85)
        elif team_text.lower() in input_name.lower():
            score = max(score, 0.80)

        if score > best_score:
            best_score = score
            best_team = team_text

    if best_score < min_score:
        return NO_TEAM_OPTION, best_score

    return best_team, best_score


def get_team_suggestions(input_name, team_list):
    if not input_name:
        return [NO_TEAM_OPTION]

    scored = []

    for team in team_list:
        score = similarity(input_name, team)

        if str(input_name).lower() == str(team).lower():
            score = 1.00
        elif str(input_name).lower() in str(team).lower():
            score = max(score, 0.85)
        elif str(team).lower() in str(input_name).lower():
            score = max(score, 0.80)

        if score >= 0.35:
            scored.append((team, score))

    scored = sorted(scored, key=lambda x: x[1], reverse=True)

    output = [NO_TEAM_OPTION]

    for team, score in scored[:10]:
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


def normalise_line(value):
    try:
        line = float(value)
    except Exception:
        return 2.5

    if line in [2.5, 3.5]:
        return line

    return 2.5


def analyse_group(group_df, goals_col, line):
    over_rate = (group_df[goals_col] > line).mean()
    under_rate = 1 - over_rate

    return {
        "matches": len(group_df),
        "avg_goals": group_df[goals_col].mean(),
        "median_goals": group_df[goals_col].median(),
        "over_rate": over_rate,
        "under_rate": under_rate,
        "over_2_5": (group_df[goals_col] > 2.5).mean(),
        "over_3_5": (group_df[goals_col] > 3.5).mean()
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
        (df[home_col].astype(str) == str(team_name)) |
        (df[away_col].astype(str) == str(team_name))
    ].copy()

    if len(team_df) == 0:
        return None

    result = analyse_group(team_df, goals_col, line)
    result["team"] = team_name
    return result


def analyse_recent_team_form(df, home_col, away_col, goals_col, date_col, team_name, line, recent_n):
    if not team_name or team_name == NO_TEAM_OPTION:
        return None

    team_df = df[
        (df[home_col].astype(str) == str(team_name)) |
        (df[away_col].astype(str) == str(team_name))
    ].copy()

    if len(team_df) == 0:
        return None

    team_df = team_df.dropna(subset=[date_col])
    team_df = team_df.sort_values(date_col)
    team_df = team_df.tail(recent_n).copy()

    if len(team_df) == 0:
        return None

    return {
        "team": team_name,
        "recent_matches": len(team_df),
        "recent_avg_total_goals": team_df[goals_col].mean(),
        "recent_over_rate": (team_df[goals_col] > line).mean(),
        "recent_under_rate": (team_df[goals_col] < line).mean()
    }


def infer_leagues_from_teams(df, league_col, home_col, away_col, home_team, away_team):
    home_team = str(home_team).strip()
    away_team = str(away_team).strip()

    exact_df = df[
        (
            (df[home_col].astype(str) == home_team) |
            (df[away_col].astype(str) == home_team)
        ) &
        (
            (df[home_col].astype(str) == away_team) |
            (df[away_col].astype(str) == away_team)
        )
    ].copy()

    if len(exact_df) > 0:
        return exact_df[league_col].astype(str).value_counts().index.tolist()

    home_df = df[
        (df[home_col].astype(str) == home_team) |
        (df[away_col].astype(str) == home_team)
    ].copy()

    away_df = df[
        (df[home_col].astype(str) == away_team) |
        (df[away_col].astype(str) == away_team)
    ].copy()

    home_leagues = set(home_df[league_col].astype(str).tolist())
    away_leagues = set(away_df[league_col].astype(str).tolist())

    common = list(home_leagues.intersection(away_leagues))

    if common:
        counts = {}

        for lg in common:
            counts[lg] = (
                (home_df[league_col].astype(str) == lg).sum() +
                (away_df[league_col].astype(str) == lg).sum()
            )

        return sorted(common, key=lambda x: counts[x], reverse=True)

    combined = pd.concat([home_df, away_df], ignore_index=True)

    if len(combined) > 0:
        return combined[league_col].astype(str).value_counts().index.tolist()

    return []


def fair_odds(probability):
    if probability <= 0:
        return 0

    return 1 / probability


def make_final_decision(league_result, home_result, away_result, home_recent, away_recent, line, over_odds, under_odds):
    league_over = league_result["over_rate"]
    league_avg = league_result["avg_goals"]
    league_matches = league_result["matches"]

    team_results = []

    if home_result:
        team_results.append(home_result)

    if away_result:
        team_results.append(away_result)

    if team_results:
        team_sample = sum(t["matches"] for t in team_results)
        team_over = sum(t["over_rate"] for t in team_results) / len(team_results)
        team_avg = sum(t["avg_goals"] for t in team_results) / len(team_results)
    else:
        team_sample = 0
        team_over = None
        team_avg = None

    recent_results = []

    if home_recent and home_recent["recent_matches"] >= 3:
        recent_results.append(home_recent)

    if away_recent and away_recent["recent_matches"] >= 3:
        recent_results.append(away_recent)

    if recent_results:
        recent_sample = sum(r["recent_matches"] for r in recent_results)
        recent_over = sum(r["recent_over_rate"] for r in recent_results) / len(recent_results)
        recent_avg = sum(r["recent_avg_total_goals"] for r in recent_results) / len(recent_results)
    else:
        recent_sample = 0
        recent_over = None
        recent_avg = None

    if team_over is not None and recent_over is not None:
        final_over = league_over * 0.50 + team_over * 0.25 + recent_over * 0.25
        final_avg = league_avg * 0.50 + team_avg * 0.25 + recent_avg * 0.25
        data_source = "League 50% + Team 25% + Recent 25%"
    elif team_over is not None:
        final_over = league_over * 0.65 + team_over * 0.35
        final_avg = league_avg * 0.65 + team_avg * 0.35
        data_source = "League + Team"
    else:
        final_over = league_over
        final_avg = league_avg
        data_source = "League only"

    final_under = 1 - final_over

    over_fair = fair_odds(final_over)
    under_fair = fair_odds(final_under)

    if line == 2.5:
        if final_over >= 0.58 and final_avg >= 2.70:
            raw_side = "Over"
        elif final_under >= 0.58 and final_avg <= 2.60:
            raw_side = "Under"
        else:
            raw_side = "None"

    elif line == 3.5:
        if final_over >= 0.48 and final_avg >= 3.30:
            raw_side = "Over"
        elif final_under >= 0.58:
            raw_side = "Under"
        else:
            raw_side = "None"

    else:
        raw_side = "None"

    side = raw_side

    if side == "Over" and over_odds > 0 and over_odds <= over_fair:
        side = "None"

    if side == "Under" and under_odds > 0 and under_odds <= under_fair:
        side = "None"

    if recent_sample >= 10 and team_sample >= 10:
        confidence = "High" if abs(final_over - 0.5) >= 0.10 else "Medium"
    elif team_sample >= 10:
        confidence = "Medium"
    else:
        confidence = "Low"

    if side == "None":
        decision = "Watch Only" if raw_side in ["Over", "Under"] else "No Bet"
    else:
        decision = side

    return {
        "decision": decision,
        "raw_side": raw_side,
        "side": side,
        "final_over": final_over,
        "final_under": final_under,
        "final_avg": final_avg,
        "over_fair": over_fair,
        "under_fair": under_fair,
        "confidence": confidence,
        "league_sample": league_matches,
        "team_sample": team_sample,
        "recent_sample": recent_sample,
        "data_source": data_source
    }


def grade_pick(line, side, probability, odds, fair, league_sample, team_sample, recent_sample, confidence):
    reasons = []

    if side not in ["Over", "Under"]:
        return "Avoid", 0, "No clear side."

    if odds <= 0:
        return "Avoid", 0, "No odds."

    if fair <= 0:
        return "Avoid", 0, "No fair odds."

    value_edge = (odds / fair) - 1
    probability_edge = probability - 0.50

    score = 0
    score += probability_edge * 100
    score += value_edge * 40
    score += min(15, league_sample / 10)
    score += min(10, team_sample / 3)
    score += min(10, recent_sample / 3)

    if league_sample < 30:
        reasons.append("League sample below 30")

    if team_sample < 10:
        reasons.append("Team sample below 10")

    if recent_sample < 10:
        reasons.append("Recent sample below 10")

    if odds <= fair:
        reasons.append("Odds not higher than fair odds")

    if confidence == "Low":
        reasons.append("Low confidence")

    grade = "Avoid"

    if line == 2.5:
        if probability >= 0.62 and odds > fair and league_sample >= 30 and team_sample >= 10 and confidence != "Low":
            grade = "A"
        elif probability >= 0.58 and league_sample >= 20:
            grade = "B"

    if line == 3.5:
        if side == "Under":
            if probability >= 0.64 and league_sample >= 30 and confidence != "Low":
                grade = "A"
            elif probability >= 0.60 and league_sample >= 20:
                grade = "B"
        else:
            if probability >= 0.54 and odds > fair and league_sample >= 30 and team_sample >= 10:
                grade = "A"
            elif probability >= 0.50 and odds > fair and league_sample >= 20:
                grade = "B"

    if grade == "A":
        reasons.insert(0, "Strong signal")
    elif grade == "B":
        reasons.insert(0, "Watchlist signal")
    else:
        reasons.insert(0, "Not strong enough")

    return grade, round(score, 2), " | ".join(reasons)


def scan_upcoming_matches(upcoming_df, df, league_col, home_col, away_col, goals_col, date_col, league_list, team_list, recent_n=10, top_n=20):
    rows = []

    for _, match_row in upcoming_df.iterrows():
        raw_home = str(match_row.get("home_team_ch", "")).strip()
        raw_away = str(match_row.get("away_team_ch", "")).strip()

        if not raw_home or not raw_away:
            continue

        matched_home, home_score = get_best_team_match(raw_home, team_list)
        matched_away, away_score = get_best_team_match(raw_away, team_list)

        if matched_home == NO_TEAM_OPTION or matched_away == NO_TEAM_OPTION:
            continue

        line = normalise_line(match_row.get("line", 2.5))

        if line not in [2.5, 3.5]:
            continue

        over_odds = float(match_row.get("over_odds", 0) or 0)
        under_odds = float(match_row.get("under_odds", 0) or 0)

        suggested_leagues = infer_leagues_from_teams(
            df,
            league_col,
            home_col,
            away_col,
            matched_home,
            matched_away
        )

        raw_league = str(match_row.get("league_ch", "")).strip()

        if raw_league and raw_league in league_list:
            selected_league = raw_league
        elif suggested_leagues:
            selected_league = suggested_leagues[0]
        else:
            continue

        league_result = analyse_league(df, league_col, goals_col, selected_league, line)

        if league_result is None:
            continue

        home_result = analyse_team(df, home_col, away_col, goals_col, matched_home, line)
        away_result = analyse_team(df, home_col, away_col, goals_col, matched_away, line)

        home_recent = analyse_recent_team_form(df, home_col, away_col, goals_col, date_col, matched_home, line, recent_n)
        away_recent = analyse_recent_team_form(df, home_col, away_col, goals_col, date_col, matched_away, line, recent_n)

        final = make_final_decision(
            league_result,
            home_result,
            away_result,
            home_recent,
            away_recent,
            line,
            over_odds,
            under_odds
        )

        if final["side"] == "Over":
            probability = final["final_over"]
            odds = over_odds
            fair = final["over_fair"]
        elif final["side"] == "Under":
            probability = final["final_under"]
            odds = under_odds
            fair = final["under_fair"]
        else:
            if final["final_over"] >= final["final_under"]:
                probability = final["final_over"]
                odds = over_odds
                fair = final["over_fair"]
                possible_side = "Over"
            else:
                probability = final["final_under"]
                odds = under_odds
                fair = final["under_fair"]
                possible_side = "Under"

            final["side"] = possible_side

        grade, score, reason = grade_pick(
            line,
            final["side"],
            probability,
            odds,
            fair,
            final["league_sample"],
            final["team_sample"],
            final["recent_sample"],
            final["confidence"]
        )

        rows.append({
            "grade": grade,
            "score": score,
            "match_date": match_row.get("match_date", ""),
            "league_ch": selected_league,
            "raw_match": f"{raw_home} vs {raw_away}",
            "matched_match": f"{matched_home} vs {matched_away}",
            "home_match_score": round(home_score * 100, 1),
            "away_match_score": round(away_score * 100, 1),
            "line": line,
            "pick": final["side"],
            "odds": odds,
            "model_probability": probability,
            "fair_odds": fair,
            "confidence": final["confidence"],
            "league_sample": final["league_sample"],
            "team_sample": final["team_sample"],
            "recent_sample": final["recent_sample"],
            "avg_goals": final["final_avg"],
            "reason": reason
        })

    result = pd.DataFrame(rows)

    if result.empty:
        return result

    grade_order = {"A": 1, "B": 2, "Avoid": 3}
    result["grade_order"] = result["grade"].map(grade_order).fillna(9)
    result = result.sort_values(["grade_order", "score"], ascending=[True, False])
    result = result.drop(columns=["grade_order"])

    return result.head(top_n)


def run_backtest(df, league_col, home_col, away_col, goals_col, date_col, line, max_rows=10000):
    bt_df = df.copy()
    bt_df = bt_df.dropna(subset=[date_col, goals_col])
    bt_df[goals_col] = pd.to_numeric(bt_df[goals_col], errors="coerce")
    bt_df = bt_df.dropna(subset=[goals_col])
    bt_df[date_col] = pd.to_datetime(bt_df[date_col], errors="coerce")
    bt_df = bt_df.dropna(subset=[date_col])
    bt_df["backtest_date_only"] = bt_df[date_col].dt.date
    bt_df = bt_df.sort_values(date_col).reset_index(drop=True)

    if len(bt_df) > max_rows:
        bt_df = bt_df.tail(max_rows).reset_index(drop=True)

    league_stats = {}
    team_stats = {}
    results = []

    def empty_stats():
        return {"matches": 0, "goals_sum": 0.0, "over_count": 0}

    def get_rate(stats):
        if stats is None or stats["matches"] <= 0:
            return None

        return {
            "sample": stats["matches"],
            "avg_goals": stats["goals_sum"] / stats["matches"],
            "over_rate": stats["over_count"] / stats["matches"]
        }

    def update_stats(stats_dict, key, goals):
        if key not in stats_dict:
            stats_dict[key] = empty_stats()

        stats_dict[key]["matches"] += 1
        stats_dict[key]["goals_sum"] += goals

        if goals > line:
            stats_dict[key]["over_count"] += 1

    grouped_dates = sorted(bt_df["backtest_date_only"].dropna().unique())

    for current_day in grouped_dates:
        day_df = bt_df[bt_df["backtest_date_only"] == current_day].copy()
        day_results = []

        for _, row in day_df.iterrows():
            match_date = row[date_col]
            league = str(row[league_col])
            home = str(row[home_col])
            away = str(row[away_col])
            actual_goals = float(row[goals_col])

            league_rate = get_rate(league_stats.get(league))
            home_rate = get_rate(team_stats.get(home))
            away_rate = get_rate(team_stats.get(away))

            if not league_rate or league_rate["sample"] < 10:
                continue

            league_over = league_rate["over_rate"]
            league_avg = league_rate["avg_goals"]

            team_over_values = []
            team_avg_values = []

            home_sample = 0
            away_sample = 0

            if home_rate and home_rate["sample"] >= 3:
                team_over_values.append(home_rate["over_rate"])
                team_avg_values.append(home_rate["avg_goals"])
                home_sample = home_rate["sample"]

            if away_rate and away_rate["sample"] >= 3:
                team_over_values.append(away_rate["over_rate"])
                team_avg_values.append(away_rate["avg_goals"])
                away_sample = away_rate["sample"]

            if team_over_values:
                team_over = sum(team_over_values) / len(team_over_values)
                team_avg = sum(team_avg_values) / len(team_avg_values)
                final_over = league_over * 0.60 + team_over * 0.40
                final_avg = league_avg * 0.60 + team_avg * 0.40
            else:
                final_over = league_over
                final_avg = league_avg

            final_under = 1 - final_over

            if line == 2.5:
                if final_over >= 0.58 and final_avg >= 2.65:
                    decision = "Over"
                elif final_under >= 0.58 and final_avg <= 2.60:
                    decision = "Under"
                else:
                    decision = "Watch Only"
            else:
                if final_over >= 0.48 and final_avg >= 3.30:
                    decision = "Over"
                elif final_under >= 0.58:
                    decision = "Under"
                else:
                    decision = "Watch Only"

            if decision == "Over":
                win = actual_goals > line
            elif decision == "Under":
                win = actual_goals < line
            else:
                win = None

            day_results.append({
                "match_date": match_date,
                "league_ch": league,
                "home_team_ch": home,
                "away_team_ch": away,
                "line": line,
                "actual_goals": actual_goals,
                "model_decision": decision,
                "win": win,
                "final_over_probability": final_over,
                "final_under_probability": final_under,
                "final_avg_goals": final_avg,
                "league_sample": league_rate["sample"],
                "home_sample": home_sample,
                "away_sample": away_sample
            })

        results.extend(day_results)

        for _, row in day_df.iterrows():
            league = str(row[league_col])
            home = str(row[home_col])
            away = str(row[away_col])
            actual_goals = float(row[goals_col])

            update_stats(league_stats, league, actual_goals)
            update_stats(team_stats, home, actual_goals)
            update_stats(team_stats, away, actual_goals)

    return pd.DataFrame(results)

def analyse_team_backtest(df, league_col, home_col, away_col, goals_col, date_col, home_team, away_team, line, recent_n):
    home_team = str(home_team).strip()
    away_team = str(away_team).strip()

    if not home_team or not away_team:
        return None

    data = df.copy()
    data = data.dropna(subset=[goals_col, date_col])
    data[goals_col] = pd.to_numeric(data[goals_col], errors="coerce")
    data = data.dropna(subset=[goals_col])
    data = data.sort_values(date_col)

    h2h_df = data[
        (
            (data[home_col].astype(str) == home_team) &
            (data[away_col].astype(str) == away_team)
        ) |
        (
            (data[home_col].astype(str) == away_team) &
            (data[away_col].astype(str) == home_team)
        )
    ].copy()

    home_all = data[
        (data[home_col].astype(str) == home_team) |
        (data[away_col].astype(str) == home_team)
    ].copy()

    away_all = data[
        (data[home_col].astype(str) == away_team) |
        (data[away_col].astype(str) == away_team)
    ].copy()

    if recent_n != "All":
        home_recent = home_all.tail(int(recent_n)).copy()
        away_recent = away_all.tail(int(recent_n)).copy()
    else:
        home_recent = home_all.copy()
        away_recent = away_all.copy()

    combined_recent = pd.concat([home_recent, away_recent], ignore_index=True)

    def make_stats(sample_df):
        if sample_df.empty:
            return {
                "matches": 0,
                "avg_goals": 0,
                "median_goals": 0,
                "over_rate": 0,
                "under_rate": 0
            }

        over_rate = (sample_df[goals_col] > line).mean()
        under_rate = (sample_df[goals_col] < line).mean()

        return {
            "matches": len(sample_df),
            "avg_goals": sample_df[goals_col].mean(),
            "median_goals": sample_df[goals_col].median(),
            "over_rate": over_rate,
            "under_rate": under_rate
        }

    h2h_stats = make_stats(h2h_df)
    home_stats = make_stats(home_recent)
    away_stats = make_stats(away_recent)
    combined_stats = make_stats(combined_recent)

    over_score = 0
    under_score = 0
    reasons = []
    risks = []

    if h2h_stats["matches"] >= 3:
        over_score += h2h_stats["over_rate"] * 25
        under_score += h2h_stats["under_rate"] * 25
        reasons.append("H2H sample available.")
    else:
        risks.append("H2H sample is small.")

    over_score += home_stats["over_rate"] * 25
    under_score += home_stats["under_rate"] * 25

    over_score += away_stats["over_rate"] * 25
    under_score += away_stats["under_rate"] * 25

    over_score += combined_stats["over_rate"] * 25
    under_score += combined_stats["under_rate"] * 25

    if combined_stats["avg_goals"] >= line + 0.35:
        over_score += 10
        reasons.append("Combined average goals support Over.")

    if combined_stats["avg_goals"] <= line - 0.35:
        under_score += 10
        reasons.append("Combined average goals support Under.")

    if line == 3.5:
        under_score += 5
        risks.append("3.5 line favours Under unless both teams show strong high-goal pattern.")

    if combined_stats["matches"] < 10:
        risks.append("Combined recent sample is below 10.")

    if home_stats["matches"] < 5:
        risks.append("Home team sample is low.")

    if away_stats["matches"] < 5:
        risks.append("Away team sample is low.")

    if over_score > under_score + 8:
        suggested = f"Over {line}"
    elif under_score > over_score + 8:
        suggested = f"Under {line}"
    else:
        suggested = "Watch Only"

    confidence_gap = abs(over_score - under_score)

    if confidence_gap >= 20 and combined_stats["matches"] >= 20:
        confidence = "High"
    elif confidence_gap >= 10 and combined_stats["matches"] >= 10:
        confidence = "Medium"
    else:
        confidence = "Low"

    return {
        "home_team": home_team,
        "away_team": away_team,
        "line": line,
        "recent_n": recent_n,
        "suggested": suggested,
        "confidence": confidence,
        "over_score": over_score,
        "under_score": under_score,
        "h2h_stats": h2h_stats,
        "home_stats": home_stats,
        "away_stats": away_stats,
        "combined_stats": combined_stats,
        "reasons": reasons,
        "risks": risks,
        "h2h_df": h2h_df.tail(20),
        "home_recent": home_recent.tail(20),
        "away_recent": away_recent.tail(20)
    }


def show_team_backtest_dashboard(df, league_col, home_col, away_col, goals_col, date_col, team_list):
    st.subheader("Team Backtest V19A")
    st.write("針對一場比賽，檢查兩隊歷史入球方向。")

    with st.form("team_backtest_form"):
        c1, c2 = st.columns(2)

        with c1:
            home_input = st.text_input("Home Team", value="阿克隆陶爾亞蒂")

        with c2:
            away_input = st.text_input("Away Team", value="羅斯托夫")

        home_match, home_score = get_best_team_match(home_input, team_list)
        away_match, away_score = get_best_team_match(away_input, team_list)

        st.write({
            "matched_home": home_match,
            "home_match_score": round(home_score * 100, 1),
            "matched_away": away_match,
            "away_match_score": round(away_score * 100, 1)
        })

        c3, c4 = st.columns(2)

        with c3:
            selected_line = st.selectbox("Goal Line", [2.5, 3.5], index=1)

        with c4:
            recent_n = st.selectbox("Recent Matches", [10, 20, 30, "All"], index=1)

        run_team_bt = st.form_submit_button("Run Team Backtest", use_container_width=True)

    if not run_team_bt:
        st.warning("輸入兩隊後，按 Run Team Backtest。")
        return

    if home_match == NO_TEAM_OPTION or away_match == NO_TEAM_OPTION:
        st.error("隊名未能配對。請改用 database 入面較接近嘅隊名。")
        return

    result = analyse_team_backtest(
        df,
        league_col,
        home_col,
        away_col,
        goals_col,
        date_col,
        home_match,
        away_match,
        selected_line,
        recent_n
    )

    if result is None:
        st.error("未能完成 Team Backtest。")
        return

    st.subheader("Final Team View")

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric("Suggested", result["suggested"])

    with m2:
        st.metric("Confidence", result["confidence"])

    with m3:
        st.metric("Over Score", f"{result['over_score']:.1f}")

    with m4:
        st.metric("Under Score", f"{result['under_score']:.1f}")

    st.subheader("Summary Table")

    rows = []

    for name, stats in [
        ("H2H", result["h2h_stats"]),
        ("Home Recent", result["home_stats"]),
        ("Away Recent", result["away_stats"]),
        ("Combined Recent", result["combined_stats"])
    ]:
        rows.append({
            "section": name,
            "matches": stats["matches"],
            "avg_goals": round(stats["avg_goals"], 2),
            "median_goals": round(stats["median_goals"], 2),
            f"Over {selected_line}": f"{stats['over_rate'] * 100:.1f}%",
            f"Under {selected_line}": f"{stats['under_rate'] * 100:.1f}%"
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.subheader("Reasons")

    if result["reasons"]:
        for item in result["reasons"]:
            st.write(f"- {item}")
    else:
        st.write("- No strong positive reason.")

    st.subheader("Risk Notes")

    if result["risks"]:
        for item in result["risks"]:
            st.write(f"- {item}")
    else:
        st.write("- No major risk note.")

    st.subheader("H2H Detail")
    if result["h2h_df"].empty:
        st.info("No H2H records found.")
    else:
        st.dataframe(result["h2h_df"], use_container_width=True)

    st.subheader("Home Recent Detail")
    st.dataframe(result["home_recent"], use_container_width=True)

    st.subheader("Away Recent Detail")
    st.dataframe(result["away_recent"], use_container_width=True)
    
try:
    raw_df = load_csv(SHEET_CSV_URL)
except Exception as e:
    st.error(f"讀取主 database 失敗：{e}")
    st.stop()

try:
    upcoming_df = load_csv(UPCOMING_CSV_URL)
    upcoming_df = prepare_upcoming_data(upcoming_df)
except Exception:
    upcoming_df = pd.DataFrame()

df, league_col, home_col, away_col, goals_col, home_goals_col, away_goals_col, date_col = prepare_main_data(raw_df)

league_list = make_league_list(df, league_col)
team_list = make_team_list(df, home_col, away_col)

st.success(f"Main database loaded successfully. Total rows: {len(df)}")

if not upcoming_df.empty:
    st.info(f"Upcoming matches loaded: {len(upcoming_df)}")
else:
    st.warning("Upcoming matches not loaded or empty.")

tab_model, tab_backtest, tab_strong, tab_team = st.tabs(["Model", "Backtest", "Strong Picks", "Team Backtest])


with tab_model:
    st.subheader("Single Match Model")

    if upcoming_df.empty:
        st.warning("upcoming_matches 暫時冇資料。")
    else:
        labels = []

        for i, row in upcoming_df.iterrows():
            labels.append(
                f"{i + 1}. {row.get('match_date', '')} | "
                f"{row.get('home_team_ch', '')} vs {row.get('away_team_ch', '')} | "
                f"Line {row.get('line', '')} | "
                f"O {row.get('over_odds', '')} / U {row.get('under_odds', '')}"
            )

        selected_label = st.selectbox("Select Upcoming Match", labels)
        selected_index = labels.index(selected_label)
        selected_match = upcoming_df.iloc[selected_index]

        raw_home = str(selected_match.get("home_team_ch", "")).strip()
        raw_away = str(selected_match.get("away_team_ch", "")).strip()

        matched_home, home_score = get_best_team_match(raw_home, team_list)
        matched_away, away_score = get_best_team_match(raw_away, team_list)

        suggested_leagues = infer_leagues_from_teams(
            df,
            league_col,
            home_col,
            away_col,
            matched_home,
            matched_away
        )

        if not suggested_leagues:
            suggested_leagues = league_list

        selected_league = st.selectbox("Suggested League", suggested_leagues)

        line = normalise_line(selected_match.get("line", 2.5))
        over_odds = float(selected_match.get("over_odds", 0) or 0)
        under_odds = float(selected_match.get("under_odds", 0) or 0)

        if st.button("Analyse Match", use_container_width=True):
            league_result = analyse_league(df, league_col, goals_col, selected_league, line)
            home_result = analyse_team(df, home_col, away_col, goals_col, matched_home, line)
            away_result = analyse_team(df, home_col, away_col, goals_col, matched_away, line)
            home_recent = analyse_recent_team_form(df, home_col, away_col, goals_col, date_col, matched_home, line, 10)
            away_recent = analyse_recent_team_form(df, home_col, away_col, goals_col, date_col, matched_away, line, 10)

            final = make_final_decision(
                league_result,
                home_result,
                away_result,
                home_recent,
                away_recent,
                line,
                over_odds,
                under_odds
            )

            st.subheader("Final View")

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                st.metric("Decision", final["decision"])

            with c2:
                st.metric("Over Probability", f"{final['final_over'] * 100:.1f}%")

            with c3:
                st.metric("Under Probability", f"{final['final_under'] * 100:.1f}%")

            with c4:
                st.metric("Avg Goals", f"{final['final_avg']:.2f}")

            st.write({
                "raw_home": raw_home,
                "matched_home": matched_home,
                "home_match_score": round(home_score * 100, 1),
                "raw_away": raw_away,
                "matched_away": matched_away,
                "away_match_score": round(away_score * 100, 1),
                "league": selected_league,
                "line": line,
                "over_odds": over_odds,
                "under_odds": under_odds,
                "fair_over": round(final["over_fair"], 2),
                "fair_under": round(final["under_fair"], 2),
                "confidence": final["confidence"],
                "league_sample": final["league_sample"],
                "team_sample": final["team_sample"],
                "recent_sample": final["recent_sample"]
            })


with tab_backtest:
    st.subheader("Backtest 17A Strict Fast")

    valid_rows = df.dropna(subset=[date_col, goals_col])
    st.info(f"Valid rows: {len(valid_rows)} | Date column: {date_col} | Goals column: {goals_col}")

    with st.form("backtest_form"):
        c1, c2, c3 = st.columns(3)

        with c1:
            selected_line = st.selectbox("Backtest Line", [2.5, 3.5], index=0)

        with c2:
            max_rows = st.selectbox("Rows to Test", [1000, 3000, 5000, 10000, 30000], index=3)

        with c3:
            only_strong = st.checkbox("Only Conservative Strong Signals", value=True)

        run_bt = st.form_submit_button("Run Backtest", use_container_width=True)

    if run_bt:
        with st.spinner("Running strict backtest..."):
            bt = run_backtest(df, league_col, home_col, away_col, goals_col, date_col, selected_line, max_rows=max_rows)

        if bt.empty:
            st.warning("未有足夠資料完成 backtest。")
        else:
            st.write("Raw backtest rows:", len(bt))

            if only_strong:
                bt = bt[bt["model_decision"].isin(["Over", "Under"])].copy()

            settled = bt[bt["win"].notna()].copy()

            if settled.empty:
                st.warning("沒有 strong signal。請取消勾選再試。")
            else:
                wins = settled["win"].sum()
                win_rate = wins / len(settled)

                over_df = settled[settled["model_decision"] == "Over"]
                under_df = settled[settled["model_decision"] == "Under"]

                m1, m2, m3, m4 = st.columns(4)

                with m1:
                    st.metric("Strong Bets", len(settled))

                with m2:
                    st.metric("Win Rate", f"{win_rate * 100:.1f}%")

                with m3:
                    st.metric("Over Win Rate", f"{over_df['win'].mean() * 100:.1f}%" if len(over_df) else "0.0%")

                with m4:
                    st.metric("Under Win Rate", f"{under_df['win'].mean() * 100:.1f}%" if len(under_df) else "0.0%")

                st.subheader("Performance by League")
                league_summary = settled.groupby("league_ch").agg(
                    bets=("win", "count"),
                    wins=("win", "sum"),
                    avg_goals=("actual_goals", "mean")
                ).reset_index()

                league_summary["win_rate"] = league_summary["wins"] / league_summary["bets"]

                st.write("Best Leagues")
                st.dataframe(
                    league_summary[league_summary["bets"] >= 5].sort_values(["win_rate", "bets"], ascending=[False, False]).head(15),
                    use_container_width=True
                )

                st.write("Worst Leagues")
                st.dataframe(
                    league_summary[league_summary["bets"] >= 5].sort_values(["win_rate", "bets"], ascending=[True, False]).head(15),
                    use_container_width=True
                )

                st.subheader("Backtest Detail")
                st.dataframe(settled.tail(300).iloc[::-1], use_container_width=True)


with tab_strong:
    st.subheader("Strong Picks Scanner V18")

    if upcoming_df.empty:
        st.warning("upcoming_matches 未有資料。")
    else:
        st.info(f"Upcoming matches loaded: {len(upcoming_df)}")

        with st.form("strong_picks_form"):
            c1, c2, c3 = st.columns(3)

            with c1:
                recent_n = st.selectbox("Recent Form Matches", [5, 8, 10, 15], index=2)

            with c2:
                top_n = st.selectbox("Show Top", [10, 20, 30, 50, 100], index=1)

            with c3:
                show_grade = st.selectbox("Show Grade", ["A only", "A + B", "All"], index=1)

            run_scan = st.form_submit_button("Run Strong Picks Scanner", use_container_width=True)

        if run_scan:
            with st.spinner("Scanning upcoming matches..."):
                picks = scan_upcoming_matches(
                    upcoming_df,
                    df,
                    league_col,
                    home_col,
                    away_col,
                    goals_col,
                    date_col,
                    league_list,
                    team_list,
                    recent_n=recent_n,
                    top_n=top_n
                )

            if picks.empty:
                st.warning("今日未掃到任何有效建議。")
            else:
                if show_grade == "A only":
                    display = picks[picks["grade"] == "A"].copy()
                elif show_grade == "A + B":
                    display = picks[picks["grade"].isin(["A", "B"])].copy()
                else:
                    display = picks.copy()

                if display.empty:
                    st.warning("目前冇 A / B 級建議。以下係全部掃描結果。")
                    display = picks.copy()

                display["model_probability"] = display["model_probability"].map(lambda x: f"{x * 100:.1f}%")
                display["fair_odds"] = display["fair_odds"].map(lambda x: f"{x:.2f}")
                display["avg_goals"] = display["avg_goals"].map(lambda x: f"{x:.2f}")

                st.dataframe(display, use_container_width=True)

                csv = display.to_csv(index=False).encode("utf-8-sig")

                st.download_button(
                    "Download Strong Picks CSV",
                    csv,
                    "strong_picks_v18.csv",
                    "text/csv",
                    use_container_width=True
                )
                with tab_team:
    show_team_backtest_dashboard(
        df,
        league_col,
        home_col,
        away_col,
        goals_col,
        date_col,
        team_list
    )
