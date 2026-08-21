import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="NFL Fantasy League", page_icon="🏈", layout="wide")
st.title("🏈 Unser NFL Fantasy Game")

# Verbindung zu Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df_picks = conn.read(worksheet="Picks", ttl=0)
    df_kader = conn.read(worksheet="NFL_Kader", ttl=0)
    # Entferne Leerzeichen in Spaltennamen
    df_kader.columns = [str(c).strip() for c in df_kader.columns]
    if not df_picks.empty:
        df_picks.columns = [str(c).strip() for c in df_picks.columns]
except Exception as e:
    st.error(f"Fehler beim Laden der Google Sheet Daten: {e}")
    df_picks = pd.DataFrame()
    df_kader = pd.DataFrame()

# Sidebar: Mitspieler & Spieltag
st.sidebar.header("Einstellungen")
mitspieler = st.sidebar.selectbox("Wer bist du?", ["Spieler 1", "Spieler 2"])
spieltag = st.sidebar.number_input("Spieltag (Week)", min_value=1, max_value=18, value=1)

# Bisherige Picks des Nutzers laden
user_picks = df_picks[df_picks["Spieler_Name"] == mitspieler] if not df_picks.empty and "Spieler_Name" in df_picks.columns else pd.DataFrame()

# Helper zum sicheren Auslesen von Listen aus dem Kader-Sheet
def get_clean_list(df, col_name):
    if col_name in df.columns:
        return [str(x).strip() for x in df[col_name].dropna().tolist() if str(x).strip() != "" and str(x) != "nan"]
    return []

# Helper zum Erstellen von Player -> Team Mappings
def get_clean_map(df, player_col, team_col):
    if player_col in df.columns and team_col in df.columns:
        sub_df = df[[player_col, team_col]].dropna()
        return {str(r[player_col]).strip(): str(r[team_col]).strip() for _, r in sub_df.iterrows() if str(r[player_col]).strip() != "" and str(r[player_col]) != "nan"}
    return {}

all_teams = get_clean_list(df_kader, "Teams")
qb_map = get_clean_map(df_kader, "QBs", "QB_Team")
wr_map = get_clean_map(df_kader, "WRs", "WR_Team")
rb_map = get_clean_map(df_kader, "RBs", "RB_Team")

# SAISON-SPERREN
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

# SPIELTAGS-SPERREN
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

used_jokers = user_picks["Joker_Slot"].dropna().tolist() if not user_picks.empty and "Joker_Slot" in user_picks.columns else []

j1, j2, j3, j4, j5, j6 = st.columns(6)
joker_pass = j1.checkbox("Pass Offense", disabled=("Pass_Offense" in used_jokers))
joker_rush = j2.checkbox("Rush Offense", disabled=("Rush_Offense" in used_jokers))
joker_def = j3.checkbox("Defense", disabled=("Defense" in used_jokers))
joker_qb = j4.checkbox("QB", disabled=("QB" in used_jokers))
joker_wr = j5.checkbox("WR", disabled=("WR" in used_jokers))
joker_rb = j6.checkbox("RB", disabled=("RB" in used_jokers))

# SPEICHERN
if st.button("Aufstellung speichern", type="primary"):
    if "-- Bitte wählen --" in [pass_sel, rush_sel, def_sel, qb_sel, wr_sel, rb_sel]:
        st.error("Bitte wähle für alle 6 Slots ein Team bzw. einen Spieler aus!")
    else:
        jokers_set = []
        if joker_pass: jokers_set.append("Pass_Offense")
        if joker_rush: jokers_set.append("Rush_Offense")
        if joker_def: jokers_set.append("Defense")
        if joker_qb: jokers_set.append("QB")
        if joker_wr: jokers_set.append("WR")
        if joker_rb: jokers_set.append("RB")
        
        new_entry = pd.DataFrame([{
            "Spieler_Name": mitspieler,
            "Week": spieltag,
            "Pass_Offense": pass_sel,
            "Rush_Offense": rush_sel,
            "Defense": def_sel,
            "QB": qb_sel,
            "WR": wr_sel,
            "RB": rb_sel,
            "Joker_Slot": ", ".join(jokers_set),
            "Punkte": 0
        }])
        
        updated_df = pd.concat([df_picks, new_entry], ignore_index=True)
        conn.update(worksheet="Picks", data=updated_df)
        st.success(f"Aufstellung für Week {spieltag} erfolgreich gespeichert!")
        st.balloons()
