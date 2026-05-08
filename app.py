import streamlit as st
import pandas as pd
import requests
from difflib import get_close_matches, SequenceMatcher
from datetime import date, datetime

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="HKJC Football Goal Model",
    page_icon="⚽",
    layout="wide"
)

# =========================
# CONSTANTS
# =========================
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRvctEexKxd5XWdetu8Swx_UoiAYi8omOjKlIPGfpogGiuMlObrdEta81U5OUhwc9_QegMpmT3Iz3cZ/pub?gid=1411325930&single=true&output=csv"

BET_LOG_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRsx-N19kLkdtdL0oSHXFOgCUnH11Hq-Ddm5XpgittBGS0AiSOhco-XzDWA6tu7d6TgiZvxKQUEGC3s/pub?gid=1909142678&single=true&output=csv"

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyOpCg7z7Mm6PJ1G1fTduYlNFRUase3ZZsqR4lHXQtqwykklDfrDdtO0Ia9oGYnpc4F/exec"

API_TOKEN = "hkjc_private_2026"

NO_TEAM_OPTION = "不用球隊資料，只用聯賽數據"

# =========================
# SESSION STATE
# =========================
if "last_bet_payload" not in st.session_state:
    st.session_state["last_bet_payload"] = None

if "last_bet_preview" not in st.session_state:
    st.session_state["last_bet_preview"] = None

if "last_saved_bet" not in st.session_state:
    st.session_state["last_saved_bet"] = None

if "analysis_result" not in st.session_state:
    st.session_state["analysis_result"] = None

# =========================
# CSS / UI STYLE
# =========================
st.markdown("""
<style>
    .stApp {
         input {
        color: #f8fafc !important;
        background-color: #1e293b !important;
    }

    textarea {
        color: #f8fafc !important;
        background-color: #1e293b !important;
    }

    div[data-baseweb="input"] {
        background-color: #1e293b !important;
        color: #f8fafc !important;
        border-radius: 12px !important;
    }

    div[data-baseweb="input"] input {
        color: #f8fafc !important;
        background-color: #1e293b !important;
    }

    div[data-baseweb="select"] {
        background-color: #1e293b !important;
        color: #f8fafc !important;
        border-radius: 12px !important;
    }

    div[data-baseweb="select"] div {
        color: #f8fafc !important;
    }

    div[data-baseweb="popover"] {
        background-color: #1e293b !important;
        color: #f8fafc !important;
    }

    ul[role="listbox"] {
        background-color: #1e293b !important;
        color: #f8fafc !important;
    }

    li[role="option"] {
        color: #f8fafc !important;
        background-color: #1e293b !important;
    }

    li[role="option"]:hover {
        background-color: #334155 !important;
        color: #ffffff !important;
    }

    label {
        color: #e2e8f0 !important;
    }

    .stTextInput label,
    .stSelectbox label,
    .stNumberInput label,
    .stDateInput label {
        color: #e2e8f0 !important;
        font-weight: 600 !important;
    }
    }
</style>
""", unsafe_allow_html=True)

# =========================
# HELPER FUNCTIONS
# =========================
def show_metric_card(label, value, sub=""):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def show_big_call(title, value, note="", tone="blue"):
    tone_class = {
        "green": "green-glow",
        "red": "red-glow",
        "yellow": "yellow-glow",
        "blue": "blue-glow"
    }.get(tone, "blue-glow")

    st.markdown(
        f"""
        <div class="call-card {tone_class}">
            <div class="call-title">{title}</div>
            <div class="call-value">{value}</div>
            <div class="call-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

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

    if decision == "No Bet":
        final_call = "Final Call: No Bet。今場沒有足夠優勢。"
    elif side == "Over":
        final_call = f"Final Call: 偏 Over {line}。公平賠率約 {over_fair:.2f}。"
    elif side == "Under":
        final_call = f"Final Call: 偏 Under {line}。公平賠率約 {under_fair:.2f}。"
    else:
        final_call = "Final Call: No Bet。"

    return {
        "decision": decision,
        "side": side,
        "note": note,
        "value_note": value_note,
        "confidence": confidence,
        "confidence_note": confidence_note,
        "final_over": final_over,
        "final_under": final_under,
        "final_avg": final_avg,
        "over_fair": over_fair,
        "under_fair": under_fair,
        "data_source": data_source,
        "team_sample": team_sample,
        "final_call": final_call
    }

def make_bet_payload(bet_date, league, home, away, line, decision, side, over_odds, under_odds, stake):
    if side == "Over":
        odds = over_odds
        final_stake = stake
        bet_side = "Over"
    elif side == "Under":
        odds = under_odds
        final_stake = stake
        bet_side = "Under"
    else:
        odds = 0
        final_stake = 0
        bet_side = "No Bet"

    payload = {
        "token": API_TOKEN,
        "bet_date": str(bet_date),
        "league_ch": league,
        "home_team_ch": home,
        "away_team_ch": away,
        "line": line,
        "model_decision": decision,
        "bet_side": bet_side,
        "odds": odds,
        "stake": final_stake,
        "result": "Pending",
        "profit_loss": ""
    }

    return payload

def save_bet_to_google_sheet(payload):
    try:
        response = requests.post(
            APPS_SCRIPT_URL,
            json=payload,
            timeout=15
        )

        try:
            data = response.json()
        except Exception:
            return False, {"error": response.text}

        ok_value = data.get("ok")

        if ok_value:
            return True, data

        return False, data

    except Exception as e:
        return False, {"error": str(e)}

def remove_blank_bet_rows(df):
    if df.empty:
        return df

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    key_cols = [
        "bet_date",
        "league_ch",
        "home_team_ch",
        "away_team_ch",
        "line",
        "model_decision",
        "bet_side",
        "odds",
        "stake",
        "result"
    ]

    existing_key_cols = [c for c in key_cols if c in df.columns]

    if not existing_key_cols:
        return df

    for col in existing_key_cols:
        df[col] = df[col].astype(str).replace("nan", "").str.strip()

    df = df[
        df[existing_key_cols]
        .apply(lambda row: any(str(x).strip() != "" for x in row), axis=1)
    ]

    return df

def prepare_bet_log(df):
    if df.empty:
        return df

    df = remove_blank_bet_rows(df)

    if df.empty:
        return df

    if "odds" in df.columns:
        df["odds"] = pd.to_numeric(df["odds"], errors="coerce").fillna(0)

    if "stake" in df.columns:
        df["stake"] = pd.to_numeric(df["stake"], errors="coerce").fillna(0)

    if "line" in df.columns:
        df["line"] = pd.to_numeric(df["line"], errors="coerce")

    if "profit_loss" not in df.columns:
        df["profit_loss"] = ""

    df["profit_loss"] = pd.to_numeric(df["profit_loss"], errors="coerce")

    if "result" in df.columns and "odds" in df.columns and "stake" in df.columns:
        calculated = []

        for _, row in df.iterrows():
            existing_profit = row.get("profit_loss")
            if pd.notna(existing_profit):
                calculated.append(existing_profit)
                continue

            result = str(row.get("result", "")).strip().lower()
            odds = row.get("odds", 0)
            stake = row.get("stake", 0)

            if result == "win":
                calculated.append((odds - 1) * stake)
            elif result == "lose":
                calculated.append(-stake)
            elif result == "push":
                calculated.append(0)
            else:
                calculated.append(0)

        df["profit_loss"] = calculated

    return df

def show_bet_log_dashboard(df):
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.subheader("📊 Bet Log Dashboard")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("Reload Bet Log Now"):
            st.cache_data.clear()
            st.rerun()
    with col_b:
        st.caption("Google CSV 可能有 1 至 5 分鐘延遲。")

    if df.empty:
        st.info("Bet Log 暫時未有資料。")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    df = prepare_bet_log(df)

    if df.empty:
        st.info("Bet Log 暫時未有有效資料。")
        st.markdown('</div>', unsafe_allow_html=True)
        return

    total_bets = len(df)

    if "result" in df.columns:
        wins = (df["result"].astype(str).str.lower() == "win").sum()
        losses = (df["result"].astype(str).str.lower() == "lose").sum()
        pushes = (df["result"].astype(str).str.lower() == "push").sum()
    else:
        wins = 0
        losses = 0
        pushes = 0

    settled = wins + losses
    hit_rate = wins / settled if settled > 0 else 0

    total_stake = df["stake"].sum() if "stake" in df.columns else 0
    total_profit = df["profit_loss"].sum() if "profit_loss" in df.columns else 0
    roi = total_profit / total_stake if total_stake > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        show_metric_card("Total Bets", total_bets, "總紀錄")
    with c2:
        show_metric_card("Hit Rate", f"{hit_rate * 100:.1f}%", f"Win {wins} / Settled {settled}")
    with c3:
        show_metric_card("Profit / Loss", f"{total_profit:.2f}", "已結算計")
    with c4:
        show_metric_card("ROI", f"{roi * 100:.1f}%", f"Stake {total_stake:.2f}")

    c5, c6, c7 = st.columns(3)
    with c5:
        show_metric_card("Win", wins)
    with c6:
        show_metric_card("Lose", losses)
    with c7:
        show_metric_card("Push", pushes)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### Latest 10 Bets")
    latest_10 = df.tail(10).iloc[::-1]
    st.dataframe(latest_10, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### Full Bet Log")
    st.dataframe(df, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if "line" in df.columns and "stake" in df.columns and "profit_loss" in df.columns:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Performance by Goal Line")

        line_summary = df.groupby("line").agg(
            bets=("line", "count"),
            total_stake=("stake", "sum"),
            profit_loss=("profit_loss", "sum")
        ).reset_index()

        line_summary["ROI"] = line_summary.apply(
            lambda row: row["profit_loss"] / row["total_stake"] if row["total_stake"] > 0 else 0,
            axis=1
        )
        line_summary["ROI"] = line_summary["ROI"].map(lambda x: f"{x * 100:.1f}%")

        st.dataframe(line_summary, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

# =========================
# LOAD DATA
# =========================
try:
    raw_df = load_csv(SHEET_CSV_URL)
except Exception as e:
    st.error(f"讀取主 database 失敗：{e}")
    st.stop()

try:
    bet_log_df = load_csv(BET_LOG_CSV_URL)
except Exception:
    bet_log_df = pd.DataFrame()

df, league_col, home_col, away_col, goals_col, date_col = prepare_main_data(raw_df)
league_list = make_league_list(df, league_col)
team_list = make_team_list(df, home_col, away_col)

# =========================
# HEADER
# =========================
st.markdown('<div class="main-title">HKJC Football Goal Model</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Version 10D UI Upgrade · 手機友善版 · Auto Save Bet · Bet Log Dashboard</div>', unsafe_allow_html=True)

tag_html = """
<span class="small-badge">⚽ 1.5 / 2.5 / 3.5 / 4.5</span>
<span class="small-badge">📱 Mobile Friendly</span>
<span class="small-badge">📝 Auto Save Bet</span>
<span class="small-badge">📊 Bet Log</span>
"""
st.markdown(tag_html, unsafe_allow_html=True)

st.success(f"Main database loaded successfully. Total rows: {len(df)}")

# =========================
# TABS
# =========================
tab_model, tab_betlog, tab_settings = st.tabs(["🎯 Model", "📊 Bet Log", "⚙️ Settings"])

# =========================
# MODEL TAB
# =========================
with tab_model:
    left_col, right_col = st.columns([1, 1.25], gap="large")

    with left_col:
        st.markdown('<div class="section-box">', unsafe_allow_html=True)
        st.subheader("Match Input")

        with st.form("analyse_form"):
            league_keyword = st.text_input("Search League", value="澳洲盃")
            filtered_leagues = search_leagues(league_keyword, league_list)

            if len(filtered_leagues) == 0:
                filtered_leagues = league_list

            selected_league = st.selectbox("Select League", filtered_leagues)
            line = st.selectbox("Goal Line", [1.5, 2.5, 3.5, 4.5], index=2)

            home_input = st.text_input("Home Team", value="坎培拉祖雲達斯")
            away_input = st.text_input("Away Team", value="昆比恩城")

            home_choice = st.selectbox("Suggested Home Team", get_team_suggestions(home_input, team_list))
            away_choice = st.selectbox("Suggested Away Team", get_team_suggestions(away_input, team_list))

            home_team = extract_team_name(home_choice)
            away_team = extract_team_name(away_choice)

            st.markdown("#### Odds Input")
            odds_col1, odds_col2 = st.columns(2)
            with odds_col1:
                over_odds = st.number_input("Over Odds", min_value=0.00, value=0.00, step=0.01)
            with odds_col2:
                under_odds = st.number_input("Under Odds", min_value=0.00, value=0.00, step=0.01)

            st.markdown("#### Bet Input")
            bet_col1, bet_col2 = st.columns(2)
            with bet_col1:
                bet_date = st.date_input("Bet Date", value=date.today())
            with bet_col2:
                stake = st.number_input("Stake", min_value=0.00, value=100.00, step=10.00)

            analyse_button = st.form_submit_button("Analyse Match", use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

        if analyse_button:
            display_home = home_input.strip() if home_team == NO_TEAM_OPTION else home_team
            display_away = away_input.strip() if away_team == NO_TEAM_OPTION else away_team

            league_result = analyse_league(df, league_col, goals_col, selected_league, line)

            if league_result is None:
                st.error("找不到此聯賽資料。")
            else:
                home_result = analyse_team(df, home_col, away_col, goals_col, home_team, line)
                away_result = analyse_team(df, home_col, away_col, goals_col, away_team, line)

                trend_rows, signal = analyse_recent_trend(
                    df, league_col, goals_col, date_col, selected_league, line
                )

                final = make_final_decision(
                    league_result, home_result, away_result, line, over_odds, under_odds, signal
                )

                payload = make_bet_payload(
                    bet_date, selected_league, display_home, display_away, line,
                    final["decision"], final["side"], over_odds, under_odds, stake
                )

                preview = pd.DataFrame([{
                    "bet_date": payload["bet_date"],
                    "league_ch": payload["league_ch"],
                    "home_team_ch": payload["home_team_ch"],
                    "away_team_ch": payload["away_team_ch"],
                    "line": payload["line"],
                    "model_decision": payload["model_decision"],
                    "bet_side": payload["bet_side"],
                    "odds": payload["odds"],
                    "stake": payload["stake"],
                    "result": payload["result"],
                    "profit_loss": payload["profit_loss"]
                }])

                st.session_state["last_bet_payload"] = payload
                st.session_state["last_bet_preview"] = preview
                st.session_state["analysis_result"] = {
                    "selected_league": selected_league,
                    "line": line,
                    "display_home": display_home,
                    "display_away": display_away,
                    "league_result": league_result,
                    "home_result": home_result,
                    "away_result": away_result,
                    "trend_rows": trend_rows,
                    "signal": signal,
                    "final": final
                }

    with right_col:
        if st.session_state.get("analysis_result") is None:
            st.markdown('<div class="section-box">', unsafe_allow_html=True)
            st.subheader("Selected Match")
            st.info("先喺左邊輸入資料，再按 Analyse Match。")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            result = st.session_state["analysis_result"]
            selected_league = result["selected_league"]
            line = result["line"]
            display_home = result["display_home"]
            display_away = result["display_away"]
            league_result = result["league_result"]
            trend_rows = result["trend_rows"]
            signal = result["signal"]
            final = result["final"]

            st.markdown('<div class="section-box">', unsafe_allow_html=True)
            st.subheader("Selected Match")

            s1, s2, s3, s4 = st.columns(4)
            with s1:
                show_metric_card("League", selected_league)
            with s2:
                show_metric_card("Goal Line", line)
            with s3:
                show_metric_card("Home", display_home)
            with s4:
                show_metric_card("Away", display_away)

            st.markdown('</div>', unsafe_allow_html=True)

            tone = "blue"
            if "No Bet" in final["decision"]:
                tone = "red"
            elif "Small Bet" in final["decision"]:
                tone = "yellow"
            else:
                tone = "green"

            show_big_call(
                "Final Call",
                final["decision"],
                f"{final['final_call']} · {final['confidence_note']}",
                tone=tone
            )

            top1, top2, top3, top4 = st.columns(4)
            with top1:
                show_metric_card("Over Probability", f"{final['final_over'] * 100:.1f}%", f"Line {line}")
            with top2:
                show_metric_card("Under Probability", f"{final['final_under'] * 100:.1f}%", f"Line {line}")
            with top3:
                show_metric_card("Average Goals", f"{final['final_avg']:.2f}", "模型平均")
            with top4:
                show_metric_card("Confidence", final["confidence"], final["data_source"])

            mid1, mid2, mid3, mid4 = st.columns(4)
            with mid1:
                show_metric_card("Fair Over Odds", f"{final['over_fair']:.2f}")
            with mid2:
                show_metric_card("Fair Under Odds", f"{final['under_fair']:.2f}")
            with mid3:
                show_metric_card("League Matches", league_result["matches"])
            with mid4:
                show_metric_card("League Median Goals", f"{league_result['median_goals']:.2f}")

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### Reading")
            st.write(final["note"])
            st.write(final["value_note"])
            st.write(signal)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### Save Bet Preview")
            if st.session_state.get("last_bet_preview") is not None:
                st.dataframe(st.session_state["last_bet_preview"], use_container_width=True)

            if st.button("Save Bet to Google Sheet", use_container_width=True):
                if st.session_state.get("last_bet_payload") is None:
                    st.error("未有可儲存投注，請先 Analyse。")
                else:
                    ok, message = save_bet_to_google_sheet(st.session_state["last_bet_payload"])

                    if ok:
                        saved_payload = st.session_state["last_bet_payload"].copy()
                        saved_payload["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        saved_payload["script_response"] = str(message)
                        st.session_state["last_saved_bet"] = saved_payload

                        st.success("Bet saved successfully. Google Sheet 已寫入。")
                        st.cache_data.clear()
                    else:
                        st.error(f"Save failed: {message}")
            st.markdown('</div>', unsafe_allow_html=True)

            if st.session_state.get("last_saved_bet") is not None:
                st.markdown('<div class="card">', unsafe_allow_html=True)
                st.markdown("#### Latest Saved Bet This Session")
                saved_df = pd.DataFrame([st.session_state["last_saved_bet"]])
                st.dataframe(saved_df, use_container_width=True)
                st.caption("如果 Bet Log 未即時更新，等 1 至 5 分鐘，再去 Bet Log 分頁按 Reload。")
                st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### League Reference")
            league_table = pd.DataFrame([{
                "League": selected_league,
                "Matches": league_result["matches"],
                "Average Goals": round(league_result["avg_goals"], 2),
                "Median Goals": round(league_result["median_goals"], 2),
                "Over 1.5": f"{league_result['over_1_5'] * 100:.1f}%",
                "Over 2.5": f"{league_result['over_2_5'] * 100:.1f}%",
                "Over 3.5": f"{league_result['over_3_5'] * 100:.1f}%",
                "Over 4.5": f"{league_result['over_4_5'] * 100:.1f}%"
            }])
            st.dataframe(league_table, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown("#### Recent Trend")
            if trend_rows:
                st.dataframe(pd.DataFrame(trend_rows), use_container_width=True)
            else:
                st.info("沒有近期走勢資料。")
            st.markdown('</div>', unsafe_allow_html=True)

# =========================
# BET LOG TAB
# =========================
with tab_betlog:
    show_bet_log_dashboard(bet_log_df)

# =========================
# SETTINGS TAB
# =========================
with tab_settings:
    st.markdown('<div class="section-box">', unsafe_allow_html=True)
    st.subheader("Settings / Info")

    st.markdown("#### Current URLs")
    st.code(SHEET_CSV_URL, language="text")
    st.code(BET_LOG_CSV_URL, language="text")
    st.code(APPS_SCRIPT_URL, language="text")

    st.markdown("#### Notes")
    st.write("1. 主數據來自你已 publish 的 Google Sheet CSV。")
    st.write("2. Bet Log 會從另外一條 CSV link 讀取。")
    st.write("3. Google publish CSV 通常有 1 至 5 分鐘延遲。")
    st.write("4. Save Bet 成功後，如 Bet Log 未即時顯示，去 Bet Log 分頁按 Reload。")

    if st.button("Refresh All Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
