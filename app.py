import streamlit as st
import pandas as pd
import requests
import math

st.set_page_config(page_title="NFL Fantasy League", page_icon="🏈", layout="wide")
st.title("🏈 NFL Fantasy Season 2026/2027")

# Links & Secrets
sheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
webhook_url = st.secrets["connections"]["gsheets"].get("webhook_url", "")

def get_csv_url(url, sheet_name):
    base_url = url.split("/edit")[0]
    return f"{base_url}/gviz/tq?tqx=out:csv&sheet={sheet_name}"

@st.cache_data(ttl=5)
def load_data():
    try:
        url_picks = get_csv_url(sheet_url, "Picks")
        url_kader = get_csv_url(sheet_url, "NFL_Kader")
        
        df_picks = pd.read_csv(url_picks)
        df_kader = pd.read_csv(url_kader)
        
        df_picks.columns = [str(c).strip() for c in df_picks.columns]
        df_kader.columns = [str(c).strip() for c in df_kader.columns]
        return df_picks, df_kader
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

df_picks, df_kader = load_data()

from streamlit_gsheets import GSheetsConnection

def update_points_in_gsheet(df_updated):
    """Speichert die aktualisierte Tabelle mit den berechneten Punkten zurück in Google Sheets."""
    try:
        # Nutzung des vorhandenen Streamlit-Connections-Mechanismus
        conn = st.connection("gsheets", type="streamlit_gsheets.GSheetsConnection")
        conn.update(worksheet="Picks", data=df_updated)
        st.cache_data.clear()  # Cache leeren, damit die neuen Daten sofort geladen werden
        return True
    except Exception as e:
        # Fallback, falls st.connection anders initialisiert wurde
        try:
            from streamlit_gsheets import GSheetsConnection
            conn = st.connection("gsheets", type=GSheetsConnection)
            conn.update(worksheet="Picks", data=df_updated)
            st.cache_data.clear()
            return True
        except Exception as e_inner:
            st.error(f"Fehler beim Speichern in Google Sheets: {e_inner}")
            return False

# Navigation Tabs
tab1, tab2 = st.tabs(["📝 Aufstellung abgeben", "📊 Rangliste & Bisherige Picks"])

# ==========================================
# BERECHNUNGS-LOGIK FÜR ALLE 4 SLOT-TYPEN
# ==========================================

# 1. PASS OFFENSE (TEAM)
def calculate_pass_offense_points(pass_yd, pass_td):
    pts = 0
    pts += math.floor(pass_yd / 25) * 1
    pts += pass_td * 6
    return pts

# 2. RUSH OFFENSE (TEAM)
def calculate_rush_offense_points(rush_yd, rush_td):
    pts = 0
    pts += math.floor(rush_yd / 10) * 1
    pts += rush_td * 6
    return pts

# 3. EINZELSPIELER (QB, WR, RB)
def calculate_player_points(pass_yd, rush_yd, rec_yd, pass_td, rush_td, rec_td, pass_int=0):
    pts = 0
    # Jede Kategorie wird einzeln abgerundet:
    pts += max(0, math.floor(pass_yd / 25)) * 1  # 1 Pkt pro 25 Pass Yds
    pts += max(0, math.floor(rush_yd / 10)) * 1  # 1 Pkt pro 10 Rush Yds
    pts += max(0, math.floor(rec_yd / 10)) * 1   # 1 Pkt pro 10 Rec Yds
    pts += (pass_td + rush_td + rec_td) * 6       # 6 Pkt pro TD
    pts -= pass_int * 2                           # 2 Minuspunkte pro Interception
    return pts

# 4. DEFENSE (TEAM)
def calculate_def_points(sacks, interceptions, def_td, opponent_points):
    """
    Berechnet die Defense-Punkte nach deinen exakten Vorgaben:
    - 1 Pkt pro Sack
    - 2 Pkt pro Interception
    - 6 Pkt pro Defensive TD
    - Staffel-Bonus für zugelassene Punkte des Gegners:
        0 Punkte           -> 10 Pkt
        1 - 9 Punkte       -> 6 Pkt
        10 - 20 Punkte     -> 3 Pkt
        > 20 Punkte        -> 0 Pkt
    """
    pts = 0
    pts += max(0, sacks) * 1            # 1 Pkt pro Sack
    pts += max(0, interceptions) * 2    # 2 Pkt pro Interception
    pts += max(0, def_td) * 6           # 6 Pkt pro Def TD
    
    # Exakter Staffel-Bonus für zugelassene Punkte (Opponent Points)
    if opponent_points == 0:
        pts += 10
    elif 1 <= opponent_points <= 9:
        pts += 6
    elif 10 <= opponent_points <= 20:
        pts += 3
    else:
        pts += 0
        
    return pts


# ==========================================
# SLEEPER API SCHNITTSTELLE & MAPPING
# ==========================================

# Zuordnung deiner Teamnamen zu den offiziellen NFL-Kürzeln der API
TEAM_MAPPING = {
    "Cardinals": "ARI", "Falcons": "ATL", "Ravens": "BAL", "Bills": "BUF",
    "Panthers": "CAR", "Bears": "CHI", "Bengals": "CIN", "Browns": "CLE",
    "Cowboys": "DAL", "Broncos": "DEN", "Lions": "DET", "Packers": "GB",
    "Texans": "HOU", "Colts": "IND", "Jaguars": "JAX", "Chiefs": "KC",
    "Raiders": "LV", "Chargers": "LAC", "Rams": "LAR", "Dolphins": "MIA",
    "Vikings": "MIN", "Patriots": "NE", "Saints": "NO", "Giants": "NYG",
    "Jets": "NYJ", "Eagles": "PHI", "Steelers": "PIT", "49ers": "SF",
    "Seahawks": "SEA", "Buccaneers": "TB", "Titans": "TEN", "Commanders": "WAS"
}

import re

def get_clean_player_name(display_name):
    """ Entfernt z. B. '(Chiefs)' aus 'Patrick Mahomes (Chiefs)' """
    return re.sub(r'\s*\([^)]*\)', '', str(display_name)).strip()

@st.cache_data(ttl=3600)
def fetch_nfl_week_stats(season, week):
    try:
        url = f"https://api.sleeper.app/v1/stats/nfl/regular/{season}/{week}"
        res = requests.get(url)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return {}

# ==========================================
# TAB 1: AUFSTELLUNG ABGEBEN
# ==========================================
with tab1:
    st.sidebar.header("Einstellungen")
    mitspieler = st.sidebar.selectbox("Wer bist du?", ["Dominic", "Uli"])
    spieltag = st.sidebar.number_input("Spieltag (Week)", min_value=1, max_value=18, value=1)

    user_picks = df_picks[df_picks["Spieler_Name"] == mitspieler] if not df_picks.empty and "Spieler_Name" in df_picks.columns else pd.DataFrame()

    def get_clean_list(df, col_name):
        if col_name in df.columns:
            return [str(x).strip() for x in df[col_name].dropna().tolist() if str(x).strip() != "" and str(x) != "nan"]
        return []

    def get_clean_map(df, player_col, team_col):
        if player_col in df.columns and team_col in df.columns:
            sub_df = df[[player_col, team_col]].dropna()
            return {str(r[player_col]).strip(): str(r[team_col]).strip() for _, r in sub_df.iterrows() if str(r[player_col]).strip() != "" and str(r[player_col]) != "nan"}
        return {}

    all_teams = get_clean_list(df_kader, "Teams")
    qb_map = get_clean_map(df_kader, "QBs", "QB_Team")
    wr_map = get_clean_map(df_kader, "WRs", "WR_Team")
    rb_map = get_clean_map(df_kader, "RBs", "RB_Team")

    def get_saison_available(full_list, slot_name):
        if user_picks.empty or slot_name not in user_picks.columns:
            return full_list
        used = [str(x).strip() for x in user_picks[slot_name].dropna().unique()]
        return [x for x in full_list if x not in used]

    avail_pass_off = get_saison_available(all_teams, "Pass_Offense")
    avail_rush_off = get_saison_available(all_teams, "Rush_Offense")
    avail_defense = get_saison_available(all_teams, "Defense")

    avail_qbs = get_saison_available(list(qb_map.keys()), "QB")
    avail_wrs = get_saison_available(list(wr_map.keys()), "WR")
    avail_rbs = get_saison_available(list(rb_map.keys()), "RB")

    st.subheader(f"Aufstellung für Week {spieltag} – {mitspieler}")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🛡️ Teams")
        pass_sel = st.selectbox("Passing Offense Team", ["-- Bitte wählen --"] + sorted(avail_pass_off))
        
        rush_options = [t for t in avail_rush_off if t != pass_sel]
        rush_sel = st.selectbox("Rushing Offense Team", ["-- Bitte wählen --"] + sorted(rush_options))
        
        def_options = [t for t in avail_defense if t not in [pass_sel, rush_sel]]
        def_sel = st.selectbox("Defense Team", ["-- Bitte wählen --"] + sorted(def_options))

    selected_teams_today = [t for t in [pass_sel, rush_sel, def_sel] if t != "-- Bitte wählen --"]

    with col2:
        st.markdown("#### 🏃 Spieler")
        
        qb_options = [p for p in avail_qbs if qb_map.get(p) not in selected_teams_today]
        qb_sel = st.selectbox("Quarterback (QB)", ["-- Bitte wählen --"] + sorted(qb_options))
        
        selected_qb_team = qb_map.get(qb_sel)
        blocked_teams_for_wr = selected_teams_today + ([selected_qb_team] if selected_qb_team else [])
        wr_options = [p for p in avail_wrs if wr_map.get(p) not in blocked_teams_for_wr]
        wr_sel = st.selectbox("Wide Receiver (WR)", ["-- Bitte wählen --"] + sorted(wr_options))
        
        selected_wr_team = wr_map.get(wr_sel)
        blocked_teams_for_rb = blocked_teams_for_wr + ([selected_wr_team] if selected_wr_team else [])
        rb_options = [p for p in avail_rbs if rb_map.get(p) not in blocked_teams_for_rb]
        rb_sel = st.selectbox("Running Back (RB)", ["-- Bitte wählen --"] + sorted(rb_options))

    st.markdown("---")
    st.markdown("#### 🃏 Joker einsetzen (Max. 1x pro Slot in der Saison)")

    used_jokers_str = ",".join(user_picks["Joker_Slot"].dropna().tolist()) if not user_picks.empty and "Joker_Slot" in user_picks.columns else ""

    j1, j2, j3, j4, j5, j6 = st.columns(6)
    joker_pass = j1.checkbox("Pass Offense", disabled=("Pass_Offense" in used_jokers_str))
    joker_rush = j2.checkbox("Rush Offense", disabled=("Rush_Offense" in used_jokers_str))
    joker_def = j3.checkbox("Defense", disabled=("Defense" in used_jokers_str))
    joker_qb = j4.checkbox("QB", disabled=("QB" in used_jokers_str))
    joker_wr = j5.checkbox("WR", disabled=("WR" in used_jokers_str))
    joker_rb = j6.checkbox("RB", disabled=("RB" in used_jokers_str))

    if st.button("Aufstellung speichern", type="primary"):
        if "-- Bitte wählen --" in [pass_sel, rush_sel, def_sel, qb_sel, wr_sel, rb_sel]:
            st.error("Bitte wähle für alle 6 Slots ein Team bzw. einen Spieler aus!")
        elif not webhook_url:
            st.error("Bitte hinterlege zuerst die webhook_url in den Streamlit Secrets!")
        else:
            jokers_set = []
            if joker_pass: jokers_set.append("Pass_Offense")
            if joker_rush: jokers_set.append("Rush_Offense")
            if joker_def: jokers_set.append("Defense")
            if joker_qb: jokers_set.append("QB")
            if joker_wr: jokers_set.append("WR")
            if joker_rb: jokers_set.append("RB")
            
            payload = {
                "Spieler_Name": mitspieler,
                "Week": int(spieltag),
                "Pass_Offense": pass_sel,
                "Rush_Offense": rush_sel,
                "Defense": def_sel,
                "QB": qb_sel,
                "WR": wr_sel,
                "RB": rb_sel,
                "Joker_Slot": ", ".join(jokers_set),
                "Punkte": 0
            }
            
            response = requests.post(webhook_url, json=payload)
            if response.status_code == 200:
                st.success(f"Aufstellung für Week {spieltag} erfolgreich gespeichert!")
                st.balloons()
                st.cache_data.clear()
            else:
                st.error("Fehler beim Speichern in Google Sheets.")

# ==========================================
# SLEEPER API SCHNITTSTELLE & MATCHING
# ==========================================

@st.cache_data(ttl=86400)
def fetch_sleeper_players_map():
    """Lädt einmal täglich die komplette Sleeper-Spielerdatenbank (ID -> Name & ID -> Team)."""
    try:
        url = "https://api.sleeper.app/v1/players/nfl"
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            name_to_id = {}
            id_to_team = {}
            for p_id, p_info in data.items():
                full_name = p_info.get("full_name")
                team = p_info.get("team")
                if full_name:
                    name_to_id[full_name.strip().lower()] = p_id
                if team:
                    id_to_team[p_id] = team.upper()
            return name_to_id, id_to_team
    except Exception:
        pass
    return {}, {}


def get_team_aggregated_offense_stats(team_abbr, stats_json, id_to_team_map):
    """
    Summiert alle Pass- und Rush-Stats aller Spieler eines bestimmten Teams für die Woche auf.
    """
    total_p_yd = 0
    total_p_td = 0
    total_r_yd = 0
    total_r_td = 0

    for p_id, p_stats in stats_json.items():
        # Prpfe, ob dieser Spieler zum gesuchten Team gehört
        if id_to_team_map.get(str(p_id)) == team_abbr.upper():
            total_p_yd += p_stats.get("pass_yd", 0)
            total_p_td += p_stats.get("pass_td", 0)
            total_r_yd += p_stats.get("rush_yd", 0)
            total_r_td += p_stats.get("rush_td", 0)

    return total_p_yd, total_p_td, total_r_yd, total_r_td


def calculate_row_points_with_breakdown(row, stats_json, name_to_id_map, id_to_team_map):
    total_pts = 0
    breakdown = []
    jokers = [j.strip() for j in str(row.get("Joker_Slot", "")).split(",") if j.strip()]

    # 1. Pass Offense Team (Aggregiert aus allen Teamspielern)
    pass_team = str(row.get("Pass_Offense", "")).strip()
    team_abbr_p = TEAM_MAPPING.get(pass_team, pass_team)
    p_yd, p_td, _, _ = get_team_aggregated_offense_stats(team_abbr_p, stats_json, id_to_team_map)
    
    pts_pass = calculate_pass_offense_points(p_yd, p_td)
    if "Pass_Offense" in jokers: pts_pass *= 2
    total_pts += pts_pass
    breakdown.append({
        "Kategorie": "Pass Offense",
        "Auswahl": pass_team,
        "Sleeper-Key/ID": team_abbr_p,
        "Stats": f"{p_yd} Yds, {p_td} TDs",
        "Joker": "Pass_Offense" in jokers,
        "Punkte": pts_pass
    })

    # 2. Rush Offense Team (Aggregiert aus allen Teamspielern)
    rush_team = str(row.get("Rush_Offense", "")).strip()
    team_abbr_r = TEAM_MAPPING.get(rush_team, rush_team)
    _, _, r_yd, r_td = get_team_aggregated_offense_stats(team_abbr_r, stats_json, id_to_team_map)
    
    pts_rush = calculate_rush_offense_points(r_yd, r_td)
    if "Rush_Offense" in jokers: pts_rush *= 2
    total_pts += pts_rush
    breakdown.append({
        "Kategorie": "Rush Offense",
        "Auswahl": rush_team,
        "Sleeper-Key/ID": team_abbr_r,
        "Stats": f"{r_yd} Yds, {r_td} TDs",
        "Joker": "Rush_Offense" in jokers,
        "Punkte": pts_rush
    })

    # 3. Defense Team
    def_team = str(row.get("Defense", "")).strip()
    team_abbr_d = TEAM_MAPPING.get(def_team, def_team)
    def_stats = stats_json.get(team_abbr_d, {})
    sacks = def_stats.get("sack", 0) or stats_json.get(f"{team_abbr_d}_sack", 0)
    ints = def_stats.get("int", 0) or stats_json.get(f"{team_abbr_d}_int", 0)
    def_td = def_stats.get("def_td", 0) or stats_json.get(f"{team_abbr_d}_def_td", 0)
    opp_pts = def_stats.get("pts_allow", -1)
    pts_def = calculate_def_points(sacks, ints, def_td, opp_pts if opp_pts != -1 else 99)
    if "Defense" in jokers: pts_def *= 2
    total_pts += pts_def
    breakdown.append({
        "Kategorie": "Defense",
        "Auswahl": def_team,
        "Sleeper-Key/ID": team_abbr_d,
        "Stats": f"{sacks} Sacks, {ints} INTs, {def_td} TDs, {opp_pts} Pts Allowed",
        "Joker": "Defense" in jokers,
        "Punkte": pts_def
    })

    # 4-6. Einzelspieler (QB, WR, RB)
    for pos_key in ["QB", "WR", "RB"]:
        raw_name = row.get(pos_key, "")
        if raw_name and str(raw_name) != "nan":
            clean_name = get_clean_player_name(raw_name).lower()
            player_id = name_to_id_map.get(clean_name)
            
            p_stats = stats_json.get(player_id, {}) if player_id else {}
            
            pass_yd = p_stats.get("pass_yd", 0)
            rush_yd = p_stats.get("rush_yd", 0)
            rec_yd = p_stats.get("rec_yd", 0)
            pass_td = p_stats.get("pass_td", 0)
            rush_td = p_stats.get("rush_td", 0)
            rec_td = p_stats.get("rec_td", 0)
            pass_int = p_stats.get("pass_int", 0)
            
            p_pts = calculate_player_points(pass_yd, rush_yd, rec_yd, pass_td, rush_td, rec_td, pass_int)
            if pos_key in jokers: p_pts *= 2
            total_pts += p_pts
            
            breakdown.append({
                "Kategorie": pos_key,
                "Auswahl": raw_name,
                "Sleeper-Key/ID": player_id if player_id else "❌ NOT FOUND",
                "Stats": f"P_Yd:{pass_yd}, R_Yd:{rush_yd}, Rec_Yd:{rec_yd}, TDs:{pass_td+rush_td+rec_td}, INT:{pass_int}",
                "Joker": pos_key in jokers,
                "Punkte": p_pts
            })

    return total_pts, pd.DataFrame(breakdown)

# ==========================================
# TAB 2: RANGLISTE & LIVE BERECHNUNG
# ==========================================
with tab2:
    st.subheader("🏆 Saison-Gesamtwertung")
    
    if not df_picks.empty:
        df_calc = df_picks.copy()
        
        # Punkte-Spalte sicherstellen und numerisch formatieren
        if "Punkte" not in df_calc.columns:
            df_calc["Punkte"] = 0
        df_calc["Punkte"] = pd.to_numeric(df_calc["Punkte"], errors="coerce").fillna(0)
        
        st.markdown("### 📊 Wöchentliche Punkte-Auswertung")
        selected_week_calc = st.selectbox("Punkte-Auswertung für Week:", list(range(1, 19)), index=0)
        
        if st.button("🔄 NFL-Punkte für ausgewählte Week live abrufen"):
            with st.spinner("Lade NFL-Statistiken von Sleeper..."):
                stats = fetch_nfl_week_stats(2026, selected_week_calc)
                players_map, id_to_team_map = fetch_sleeper_players_map()
                
                if stats:
                    breakdowns = {}
                    for idx, row in df_calc.iterrows():
                        if int(row.get("Week", 0)) == int(selected_week_calc):
                            computed_pts, df_bd = calculate_row_points_with_breakdown(row, stats, players_map, id_to_team_map)
                            df_calc.at[idx, "Punkte"] = computed_pts
                            breakdowns[f"{row.get('Spieler_Name')} (Week {selected_week_calc})"] = df_bd
                    
                    st.session_state["breakdowns"] = breakdowns
                    st.session_state["df_calc_active"] = df_calc
                    st.success(f"NFL-Boxscores für Week {selected_week_calc} erfolgreich berechnet!")
                else:
                    st.warning(f"Keine Statistiken für Week {selected_week_calc} von der API erhalten.")

        # Falls Live-Daten abgerufen wurden, nehmen wir diesen Stand für die Anzeige
        df_display = st.session_state.get("df_calc_active", df_calc)

        # 1. Gesamtwertung über alle bisherigen Wochen anzeigen
        season_leaderboard = df_display.groupby("Spieler_Name")["Punkte"].sum().reset_index()
        season_leaderboard = season_leaderboard.sort_values(by="Punkte", ascending=False)
        season_leaderboard.rename(columns={"Punkte": "Gesamtpunkte Saison"}, inplace=True)
        
        # Große Kennzahlen-Karten (Metrics) ganz oben anzeigen
        col1, col2 = st.columns(2)
        cols = [col1, col2]
        for idx, row in season_leaderboard.iterrows():
            if idx < len(cols):
                cols[idx].metric(
                    label=f"Platz {idx+1}: {row['Spieler_Name']}", 
                    value=f"{int(row['Gesamtpunkte Saison'])} Pkt"
                )

        # 2. Detaillierte Fehlerdiagnose / Aufschlüsselung anzeigen
        if "breakdowns" in st.session_state:
            st.markdown("---")
            st.subheader("🔍 Detail-Analyse der Punkteberechnung")
            for name, df_bd in st.session_state["breakdowns"].items():
                with st.expander(f"📊 Detail-Punkte für {name}"):
                    st.dataframe(df_bd, use_container_width=True, hide_index=True)

        # 3. Tabelle mit den bisherigen Picks & Punkten
        st.markdown("---")
        st.subheader("📋 Bisherige Picks & Punkteübersicht")
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    else:
        st.info("Noch keine Picks in Google Sheets vorhanden.")
