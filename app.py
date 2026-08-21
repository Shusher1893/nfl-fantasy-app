import streamlit as st
import pandas as pd

# App Title & Configuration
st.set_page_config(page_title="NFL Fantasy League", page_icon="🏈", layout="wide")
st.title("🏈 Unser NFL Fantasy Game")

st.markdown("""
### Spieltags-Aufstellung
Wähle deine Teams und Spieler für den aktuellen Spieltag aus. 
*Jedes Team und jeder Spieler darf pro Slot nur einmal in der Saison gewählt werden!*
""")

# Setup Sidebar for Player Selection & Gameweek
st.sidebar.header("Einstellungen")
spieltag = st.sidebar.number_input("Spieltag (Week)", min_value=1, max_value=18, value=1)
mitspieler = st.sidebar.selectbox("Mitspieler", ["Player 1", "Player 2"])

st.subheader(f"Aufstellung für Week {spieltag} - {mitspieler}")

# Layout with Columns
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 🛡️ Teams")
    pass_offense_team = st.text_input("Passing Offense Team", placeholder="z. B. Kansas City Chiefs")
    rush_offense_team = st.text_input("Rushing Offense Team", placeholder="z. B. San Francisco 49ers")
    defense_team = st.text_input("Defense Team", placeholder="z. B. Baltimore Ravens")

with col2:
    st.markdown("#### 🏃 Spieler")
    qb_player = st.text_input("Quarterback (QB)", placeholder="z. B. Patrick Mahomes")
    wr_player = st.text_input("Wide Receiver (WR)", placeholder="z. B. Justin Jefferson")
    rb_player = st.text_input("Running Back (RB)", placeholder="z. B. Christian McCaffrey")

st.markdown("---")
st.markdown("#### 🃏 Joker einsetzen (Verdoppelt die Punkte des Slots)")

# Joker Toggles
j1, j2, j3, j4, j5, j6 = st.columns(6)
joker_pass_off = j1.checkbox("Joker Pass Offense")
joker_rush_off = j2.checkbox("Joker Rush Offense")
joker_def = j3.checkbox("Joker Defense")
joker_qb = j4.checkbox("Joker QB")
joker_wr = j5.checkbox("Joker WR")
joker_rb = j6.checkbox("Joker RB")

if st.button("Aufstellung & Joker speichern", type="primary"):
    st.success(f"Aufstellung für Week {spieltag} erfolgreich gespeichert!")

# Points Calculation Engine (Rulebook)
def calc_offense_player_pts(pass_yds, pass_td, rush_yds, rush_td, rec_yds, rec_td):
    pts = (pass_yds // 25) + (pass_td * 6)
    pts += (rush_yds // 10) + (rush_td * 6)
    pts += (rec_yds // 10) + (rec_td * 6)
    return pts

def calc_defense_pts(sacks, def_td, points_allowed):
    pts = (sacks * 1) + (def_td * 6)
    if points_allowed == 0:
        pts += 10
    elif 2 <= points_allowed <= 9:
        pts += 6
    elif 10 <= points_allowed <= 20:
        pts += 3
    return pts
