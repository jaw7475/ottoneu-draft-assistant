"""Pitchers tab view."""

import streamlit as st

from db.queries import clear_player_tag, draft_player, get_player_tags, get_teams, query_players, set_player_tag

# Column groups — ordered dict of group_name -> column list
COLUMN_GROUPS = {
    "Player Info": ["avail", "name", "salary", "position", "mlb_team", "age", "ottoneu_team"],
    "Rankings": ["dollar_value", "predicted_price", "surplus_value", "expert1_rank", "expert2_rank", "expert1_tier", "expert2_tier"],
    "Fantasy": ["fpts", "fpts_per_ip", "proj_fpts", "proj_fpts_per_ip"],
    "Basic Stats": ["ip", "whip", "era", "xera", "xfip", "k_per_9", "bb_per_9", "hr_per_9", "hr", "hr_per_fb", "sv", "hld"],
    "Projections": ["proj_ip", "proj_whip", "proj_era", "proj_hr"],
    "Advanced": ["stuff_plus", "location_plus", "pitching_plus", "barrel_pct", "hard_hit_pct", "ev", "gb_pct", "fb_pct", "max_velo"],
}

# Divider names (unique whitespace strings) between groups
DIVIDERS = [" ", "  ", "   ", "    ", "     "]

COLUMN_CONFIG = {
    "avail": st.column_config.TextColumn("", width=47),
    "dollar_value": st.column_config.NumberColumn("$Value", format="$%d"),
    "surplus_value": st.column_config.NumberColumn("Surplus", format="%+d"),
    "predicted_price": st.column_config.NumberColumn("Pred$", format="$%d"),
    "ownership_pct": st.column_config.NumberColumn("Own%", format="%.1f%%"),
    "expert1_rank": st.column_config.NumberColumn("E1 Rank", format="%d"),
    "expert1_tier": st.column_config.TextColumn("E1 Tier", width=70),
    "expert2_rank": st.column_config.NumberColumn("E2 Rank", format="%d"),
    "expert2_tier": st.column_config.TextColumn("E2 Tier", width=70),
    "mlb_team": st.column_config.TextColumn("Team", width=60),
    "age": st.column_config.NumberColumn("Age", format="%.0f", width=50),
    "whip": st.column_config.NumberColumn("WHIP", format="%.2f"),
    "max_velo": st.column_config.NumberColumn("maxVelo", format="%.1f"),
    "barrel_pct": st.column_config.NumberColumn("Barrel%", format="%.1f"),
    "hard_hit_pct": st.column_config.NumberColumn("HardHit%", format="%.1f"),
    "ev": st.column_config.NumberColumn("EV", format="%.1f"),
}

# Add divider configs
for d in DIVIDERS:
    COLUMN_CONFIG[d] = st.column_config.TextColumn("", width=8, disabled=True)


def _build_display_cols(all_cols, selected_groups):
    """Build display column list with dividers between groups."""
    display_cols = []
    group_names = list(COLUMN_GROUPS.keys())
    divider_idx = 0
    for i, group_name in enumerate(group_names):
        group_cols = selected_groups.get(group_name, [])
        cols = [c for c in group_cols if c in all_cols]
        if not cols:
            continue
        if display_cols and divider_idx < len(DIVIDERS):
            display_cols.append(DIVIDERS[divider_idx])
            divider_idx += 1
        display_cols.extend(cols)
    return display_cols


@st.dialog("Draft Player")
def _draft_pitcher_dialog(player_name: str):
    """Dialog overlay for drafting a pitcher."""
    st.markdown(f"**{player_name}**")
    teams = get_teams("pitchers")
    price = st.number_input("Draft price ($)", min_value=1, value=None, step=1, key="draft_pitcher_price")
    team = st.selectbox("Drafting team", [""] + teams, key="draft_pitcher_team")
    if st.button("Confirm Draft", key="draft_pitcher_confirm"):
        if price is None:
            st.error("Please enter a draft price.")
            return
        draft_player("pitchers", player_name, price, team)
        del st.session_state["pitchers_table"]
        st.rerun()


TAG_COLORS = {
    "target": "color: #28a745; font-weight: bold",
    "avoid": "color: #6f42c1; font-weight: bold",
    "injury": "color: #dc3545; font-weight: bold",
}


@st.dialog("Tag Player")
def _tag_pitcher_dialog(player_name: str):
    """Dialog overlay for tagging a pitcher."""
    st.markdown(f"**{player_name}**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Target", key="tag_pitcher_target", use_container_width=True):
            set_player_tag(player_name, "target")
            st.session_state["pitchers_table"]["selection"]["rows"] = []
            st.rerun()
    with col2:
        if st.button("Avoid", key="tag_pitcher_avoid", use_container_width=True):
            set_player_tag(player_name, "avoid")
            st.session_state["pitchers_table"]["selection"]["rows"] = []
            st.rerun()
    with col3:
        if st.button("Injury", key="tag_pitcher_injury", use_container_width=True):
            set_player_tag(player_name, "injury")
            st.session_state["pitchers_table"]["selection"]["rows"] = []
            st.rerun()
    with col4:
        if st.button("Clear", key="tag_pitcher_clear", use_container_width=True):
            clear_player_tag(player_name)
            st.session_state["pitchers_table"]["selection"]["rows"] = []
            st.rerun()


def render_pitchers(filters: dict):
    """Render the pitchers tab."""
    # Search bar with clear button
    search_col, clear_col = st.columns([5, 1])
    with search_col:
        search = st.text_input("Search player", key="pitcher_search")
    with clear_col:
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("Clear", key="pitcher_search_clear", use_container_width=True,
                  on_click=lambda: st.session_state.update({"pitcher_search": ""}))

    df = query_players(
        table="pitchers",
        search=search,
        positions=filters["pitcher_positions"],
        show_drafted=filters["show_drafted"],
        show_kept=filters["show_kept"],
        sort_by=filters["sort_by"],
        sort_asc=filters["sort_asc"],
        stat_filters=filters["stat_filters"],
    )

    # Compute availability indicator (three states: keeper, drafted, available)
    def _avail_label(row):
        if row["is_drafted"] == 1:
            return "    ✗"
        if row["is_keeper"] == 1:
            return "    ✗"
        return "    ✓"
    df["avail"] = df.apply(_avail_label, axis=1)

    # Merge draft_price into salary for drafted players
    drafted_mask = df["is_drafted"] == 1
    df.loc[drafted_mask, "salary"] = df.loc[drafted_mask, "draft_price"]

    # Load player tags
    tags = get_player_tags()
    df["_tag"] = df["name"].map(tags).fillna("")

    all_cols = df.columns.tolist()

    selected_groups = filters.get("pitcher_selected_groups", {})
    display_cols = _build_display_cols(all_cols, selected_groups)

    # Add divider columns to the dataframe
    for d in DIVIDERS:
        if d in display_cols:
            df[d] = ""

    display_df = df[display_cols].copy()

    # Style salary, avail, and name columns
    def highlight_cells(col):
        styles = [""] * len(col)
        if col.name == "salary":
            for i, idx in enumerate(col.index):
                if df.loc[idx, "is_drafted"] == 1:
                    styles[i] = "background-color: #cce5ff"
        elif col.name == "avail":
            for i, idx in enumerate(col.index):
                if df.loc[idx, "is_drafted"] == 1:
                    styles[i] = "color: #dc3545"
                elif df.loc[idx, "is_keeper"] == 1:
                    styles[i] = "color: #999999"
                else:
                    styles[i] = "color: #28a745; background-color: #d4edda"
        elif col.name == "name":
            for i, idx in enumerate(col.index):
                tag = df.loc[idx, "_tag"]
                if tag in TAG_COLORS:
                    styles[i] = TAG_COLORS[tag]
        return styles

    styled = display_df.style.apply(highlight_cells)

    col_cfg = {k: v for k, v in COLUMN_CONFIG.items() if k in display_cols}
    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=600,
        on_select="rerun",
        selection_mode="single-row",
        key="pitchers_table",
        column_config=col_cfg,
    )

    # Draft action dialog
    selection = st.session_state.get("pitchers_table", {})
    selected_rows = selection.get("selection", {}).get("rows", [])

    if selected_rows:
        idx = selected_rows[0]
        if idx < len(df):
            player = df.iloc[idx]
            if filters["click_mode"] == "tag":
                _tag_pitcher_dialog(player["name"])
            elif player["is_drafted"] == 1:
                st.warning(f"{player['name']} has already been drafted.")
            elif player["salary"] and player["salary"] > 0:
                st.warning(f"{player['name']} is already owned (${int(player['salary'])}).")
            else:
                _draft_pitcher_dialog(player["name"])
