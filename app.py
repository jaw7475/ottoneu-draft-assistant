"""Ottoneu Draft Assistant — Streamlit entry point."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from db.connection import db_exists
from db.queries import get_column_names
from ui.hitters_view import COLUMN_GROUPS as HITTER_COLUMN_GROUPS, render_hitters
from ui.pitchers_view import COLUMN_GROUPS as PITCHER_COLUMN_GROUPS, render_pitchers
from ui.roster_view import render_roster
from ui.settings import render_settings
from ui.sidebar import render_sidebar

st.set_page_config(
    page_title="Ottoneu Draft Assistant",
    layout="wide",
)

# Initialize DB if needed
if not db_exists():
    with st.spinner("Building database from source files..."):
        from db.init_db import init_db
        init_db()
    st.rerun()

st.title("Ottoneu Draft Assistant")

# Track active tab
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "Hitters"

# Render sidebar with context-appropriate columns
active = st.session_state.active_tab
table = "hitters" if active == "Hitters" else "pitchers"
columns = get_column_names(table)
hitter_cols = get_column_names("hitters")
pitcher_cols = get_column_names("pitchers")
hidden = {"is_drafted", "draft_price", "is_keeper", "avail", "_tag"}
filters = render_sidebar(
    active, columns,
    hitter_column_groups=HITTER_COLUMN_GROUPS,
    pitcher_column_groups=PITCHER_COLUMN_GROUPS,
    hitter_all_cols=hitter_cols,
    pitcher_all_cols=pitcher_cols,
    hidden=hidden,
)

# Tabs
tab_roster, tab_hitters, tab_pitchers, tab_settings = st.tabs(
    ["Roster", "Hitters", "Pitchers", "Settings"]
)

with tab_roster:
    render_roster()

with tab_hitters:
    st.session_state.active_tab = "Hitters"
    render_hitters(filters)

with tab_pitchers:
    st.session_state.active_tab = "Pitchers"
    render_pitchers(filters)

with tab_settings:
    render_settings()
