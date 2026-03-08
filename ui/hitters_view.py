"""Hitters tab view."""

import pandas as pd
import streamlit as st

from db.queries import clear_player_tag, draft_player, get_full_pool_columns, get_model_targets, get_player_tags, get_teams, query_players, set_player_tag

# Column groups — ordered dict of group_name -> column list
COLUMN_GROUPS = {
    "Player Info": ["avail", "name", "salary", "position", "mlb_team", "age", "ottoneu_team"],
    "Rankings": ["dollar_value", "predicted_price", "surplus_value", "expert1_rank", "expert2_rank", "expert1_tier", "expert2_tier"],
    "Fantasy": ["fpts", "fpts_per_g", "proj_fpts", "proj_fpts_per_g"],
    "Basic Stats": ["avg", "obp", "ops", "hr", "iso", "wrc_plus", "xwoba", "bb_pct", "k_pct", "babip", "sb", "cs"],
    "Projections": ["proj_avg", "proj_ops", "proj_hr", "proj_wrc_plus"],
    "Advanced": ["barrel_pct", "hard_hit_pct", "ev", "max_ev", "gb_pct", "fb_pct", "pull_pct"],
}

# Divider names (unique whitespace strings) between groups
DIVIDERS = [" ", "  ", "   ", "    ", "     "]

COLUMN_CONFIG = {
    # Player Info
    "avail": st.column_config.TextColumn("", width=47),
    "name": st.column_config.TextColumn("Name"),
    "salary": st.column_config.TextColumn("Salary"),
    "position": st.column_config.TextColumn("Position"),
    "mlb_team": st.column_config.TextColumn("Team", width=60),
    "age": st.column_config.NumberColumn("Age", width=50),
    "ottoneu_team": st.column_config.TextColumn("Ottoneu Team"),
    # Rankings
    "dollar_value": st.column_config.NumberColumn("$Value"),
    "predicted_price": st.column_config.NumberColumn("Pred$"),
    "surplus_value": st.column_config.NumberColumn("Surplus"),
    "expert1_rank": st.column_config.NumberColumn("E1 Rank"),
    "expert2_rank": st.column_config.NumberColumn("E2 Rank"),
    "expert1_tier": st.column_config.TextColumn("E1 Tier", width=70),
    "expert2_tier": st.column_config.TextColumn("E2 Tier", width=70),
    "ownership_pct": st.column_config.NumberColumn("Own%"),
    # Fantasy
    "fpts": st.column_config.NumberColumn("FPTS"),
    "fpts_per_g": st.column_config.NumberColumn("PPG"),
    "proj_fpts": st.column_config.NumberColumn("pFPTS"),
    "proj_fpts_per_g": st.column_config.NumberColumn("pPPG"),
    # Basic Stats
    "avg": st.column_config.NumberColumn("AVG"),
    "obp": st.column_config.NumberColumn("OBP"),
    "ops": st.column_config.NumberColumn("OPS"),
    "hr": st.column_config.NumberColumn("HR"),
    "iso": st.column_config.TextColumn("ISO"),
    "wrc_plus": st.column_config.NumberColumn("wRC+"),
    "xwoba": st.column_config.TextColumn("xwOBA"),
    "bb_pct": st.column_config.TextColumn("BB%"),
    "k_pct": st.column_config.TextColumn("K%"),
    "babip": st.column_config.NumberColumn("BABIP"),
    "sb": st.column_config.NumberColumn("SB"),
    "cs": st.column_config.NumberColumn("CS"),
    # Projections
    "proj_avg": st.column_config.NumberColumn("pAVG"),
    "proj_ops": st.column_config.NumberColumn("pOPS"),
    "proj_hr": st.column_config.NumberColumn("pHR"),
    "proj_wrc_plus": st.column_config.NumberColumn("pwRC+"),
    # Advanced
    "barrel_pct": st.column_config.TextColumn("Barrel%"),
    "hard_hit_pct": st.column_config.TextColumn("HardHit%"),
    "ev": st.column_config.TextColumn("EV"),
    "max_ev": st.column_config.TextColumn("MaxEV"),
    "gb_pct": st.column_config.TextColumn("GB%"),
    "fb_pct": st.column_config.TextColumn("FB%"),
    "pull_pct": st.column_config.TextColumn("Pull%"),
}

# Number format strings for Styler (applied instead of column_config format)
NUM_FORMATS = {
    # Rankings
    "dollar_value": "$%.0f",
    "surplus_value": "%+.0f",
    "predicted_price": "$%.0f",
    "expert1_rank": "%.0f",
    "expert2_rank": "%.0f",
    # Player Info
    "ownership_pct": "%.1f%%",
    "age": "%.0f",
    # Fantasy
    "fpts": "%.0f",
    "fpts_per_g": "%.2f",
    "proj_fpts": "%.0f",
    "proj_fpts_per_g": "%.2f",
    # Basic Stats
    "avg": "%.3f",
    "obp": "%.3f",
    "ops": "%.3f",
    "iso": "%.3f",
    "babip": "%.3f",
    "woba": "%.3f",
    "xwoba": "%.3f",
    "bb_pct": "%.1f",
    "k_pct": "%.1f",
    "hr": "%.0f",
    "sb": "%.0f",
    "cs": "%.0f",
    "wrc_plus": "%.0f",
    # Projections
    "proj_avg": "%.3f",
    "proj_ops": "%.3f",
    "proj_hr": "%.0f",
    "proj_wrc_plus": "%.0f",
    # Advanced
    "barrel_pct": "%.1f",
    "hard_hit_pct": "%.1f",
    "ev": "%.1f",
    "max_ev": "%.1f",
    "gb_pct": "%.1f",
    "fb_pct": "%.1f",
    "pull_pct": "%.1f",
}

# Columns where lower is better (sorted ascending) — NaN sentinel is large positive
ASC_COLS = {"expert1_rank", "expert2_rank", "k_pct", "gb_pct"}

# Columns to annotate with percentile emoji indicators
# "higher" = high values are good (🟢), "lower" = low values are good (🟢)
EMOJI_COLS = {
    "iso": "higher",
    "xwoba": "higher",
    "bb_pct": "higher",
    "k_pct": "lower",
    "barrel_pct": "higher",
    "hard_hit_pct": "higher",
    "ev": "higher",
    "max_ev": "higher",
    "gb_pct": "lower",
    "fb_pct": "higher",
    "pull_pct": "higher",
}


def _percentile_emoji(pct, direction):
    """Return emoji for a percentile value given direction preference."""
    if pd.isna(pct):
        return ""
    if direction == "lower":
        pct = 1.0 - pct
    if pct >= 0.9:
        return " 🟢"
    if pct >= 0.7:
        return " 🟡"
    if pct <= 0.1:
        return " 🔴"
    if pct <= 0.3:
        return " 🟠"
    return ""

# Add divider configs
for d in DIVIDERS:
    COLUMN_CONFIG[d] = st.column_config.TextColumn("", width=8, disabled=True)


def _build_display_cols(all_cols, selected_groups):
    """Build display column list with dividers between groups. Returns (cols, col_to_group)."""
    display_cols = []
    col_to_group = {}
    group_names = list(COLUMN_GROUPS.keys())
    divider_idx = 0
    for group_name in group_names:
        group_cols = selected_groups.get(group_name, [])
        cols = [c for c in group_cols if c in all_cols]
        if not cols:
            continue
        if display_cols and divider_idx < len(DIVIDERS):
            display_cols.append(DIVIDERS[divider_idx])
            divider_idx += 1
        for c in cols:
            col_to_group[c] = group_name
        display_cols.extend(cols)
    return display_cols, col_to_group


@st.dialog("Draft Player")
def _draft_hitter_dialog(player_name: str):
    """Dialog overlay for drafting a hitter."""
    st.markdown(f"**{player_name}**")
    teams = get_teams("hitters")
    price = st.number_input("Draft price ($)", min_value=1, value=None, step=1, key="draft_hitter_price")
    team = st.selectbox("Drafting team", [""] + teams, key="draft_hitter_team")
    if st.button("Confirm Draft", key="draft_hitter_confirm"):
        if price is None:
            st.error("Please enter a draft price.")
            return
        draft_player("hitters", player_name, price, team)
        del st.session_state["hitters_table"]
        st.rerun()


TAG_COLORS = {
    "target": "color: #28a745; font-weight: bold",
    "avoid": "color: #6f42c1; font-weight: bold",
    "injury": "color: #dc3545; font-weight: bold",
}


@st.dialog("Tag Player")
def _tag_hitter_dialog(player_name: str):
    """Dialog overlay for tagging a hitter."""
    st.markdown(f"**{player_name}**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Target", key="tag_hitter_target", use_container_width=True):
            set_player_tag(player_name, "target")
            st.session_state["hitters_table"]["selection"]["rows"] = []
            st.rerun()
    with col2:
        if st.button("Avoid", key="tag_hitter_avoid", use_container_width=True):
            set_player_tag(player_name, "avoid")
            st.session_state["hitters_table"]["selection"]["rows"] = []
            st.rerun()
    with col3:
        if st.button("Injury", key="tag_hitter_injury", use_container_width=True):
            set_player_tag(player_name, "injury")
            st.session_state["hitters_table"]["selection"]["rows"] = []
            st.rerun()
    with col4:
        if st.button("Clear", key="tag_hitter_clear", use_container_width=True):
            clear_player_tag(player_name)
            st.session_state["hitters_table"]["selection"]["rows"] = []
            st.rerun()


def render_hitters(filters: dict):
    """Render the hitters tab."""
    # Search bar with clear button
    search_col, clear_col = st.columns([5, 1])
    with search_col:
        search = st.text_input("Search player", key="hitter_search")
    with clear_col:
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("Clear", key="hitter_search_clear", use_container_width=True,
                  on_click=lambda: st.session_state.update({"hitter_search": ""}))

    df = query_players(
        table="hitters",
        search=search,
        positions=filters["hitter_positions"],
        show_drafted=filters["show_drafted"],
        show_kept=filters["show_kept"],
        show_my_team=filters.get("show_my_team", False),
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

    # Format salary as display string
    df["salary"] = df["salary"].apply(lambda v: f"${int(v)}" if pd.notna(v) and v > 0 else "")

    # Load player tags and model targets
    tags = get_player_tags()
    df["_tag"] = df["name"].map(tags).fillna("")
    model_targets = get_model_targets()
    df["_model_target"] = df["name"].isin(model_targets)

    all_cols = df.columns.tolist()

    selected_groups = filters.get("hitter_selected_groups", {})
    display_cols, col_to_group = _build_display_cols(all_cols, selected_groups)

    # Add divider columns to the dataframe with a visible separator
    for d in DIVIDERS:
        if d in display_cols:
            df[d] = "│"

    display_df = df[display_cols].copy()

    # Compute percentile ranks against the FULL player pool (stable across filters)
    full_pool = get_full_pool_columns("hitters", list(EMOJI_COLS.keys()))
    full_pool_pct = {}
    for col_name in EMOJI_COLS:
        if col_name in full_pool.columns:
            full_pool_pct[col_name] = full_pool.set_index("name")[col_name].rank(pct=True)

    percentile_ranks = {}
    for col_name in EMOJI_COLS:
        if col_name in display_df.columns and col_name in full_pool_pct:
            percentile_ranks[col_name] = df["name"].map(full_pool_pct[col_name])

    # Fill NaN with sentinel so nulls sort to the bottom for the expected direction
    _SENTINEL_HIGH = 9999999.0   # for ascending columns (lower is better)
    _SENTINEL_LOW = -9999999.0   # for descending columns (higher is better)
    numeric_cols = display_df.select_dtypes(include="number").columns
    for c in numeric_cols:
        sentinel = _SENTINEL_HIGH if c in ASC_COLS else _SENTINEL_LOW
        display_df[c] = display_df[c].fillna(sentinel)

    # Format emoji columns as strings with indicators appended
    for col_name, direction in EMOJI_COLS.items():
        if col_name not in display_df.columns:
            continue
        fmt_str = NUM_FORMATS.get(col_name)
        pct_series = percentile_ranks[col_name]
        formatted = []
        for idx in display_df.index:
            v = display_df.at[idx, col_name]
            if isinstance(v, (int, float)) and (v >= _SENTINEL_HIGH or v <= _SENTINEL_LOW):
                formatted.append("")
            elif fmt_str:
                formatted.append((fmt_str % v) + _percentile_emoji(pct_series.get(idx), direction))
            else:
                formatted.append(str(v) + _percentile_emoji(pct_series.get(idx), direction))
        display_df[col_name] = formatted

    # Style specialized columns and dividers
    divider_set = set(DIVIDERS)
    style_cols = [c for c in ["avail", "name", "salary"] if c in display_cols]
    style_cols += [d for d in DIVIDERS if d in display_cols]

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
                parts = []
                if df.loc[idx, "_model_target"]:
                    parts.append("background-color: #d4edda")
                tag = df.loc[idx, "_tag"]
                if tag in TAG_COLORS:
                    parts.append(TAG_COLORS[tag])
                styles[i] = "; ".join(parts)
        elif col.name in divider_set:
            styles = ["color: #cccccc; background-color: #f0f0f0"] * len(col)
        return styles

    def _make_fmt(fmt_str):
        def _fmt(v):
            if isinstance(v, (int, float)) and (v >= _SENTINEL_HIGH or v <= _SENTINEL_LOW):
                return ""
            if fmt_str:
                return fmt_str % v
            # Default: drop trailing zeros
            if isinstance(v, float) and v == int(v):
                return str(int(v))
            return v
        return _fmt

    # Build formatters only for numeric cols that aren't already string-formatted emoji cols
    emoji_col_set = set(EMOJI_COLS.keys())
    col_formatters = {}
    for c in numeric_cols:
        if c not in emoji_col_set:
            col_formatters[c] = _make_fmt(NUM_FORMATS.get(c))

    styled = display_df.style.apply(highlight_cells, subset=style_cols).format(
        col_formatters, na_rep=""
    )

    col_cfg = {k: v for k, v in COLUMN_CONFIG.items() if k in display_cols}
    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=600,
        on_select="rerun",
        selection_mode="single-row",
        key="hitters_table",
        column_config=col_cfg,
    )

    # Draft action dialog
    selection = st.session_state.get("hitters_table", {})
    selected_rows = selection.get("selection", {}).get("rows", [])

    if selected_rows:
        idx = selected_rows[0]
        if idx < len(df):
            player = df.iloc[idx]
            if filters["click_mode"] == "tag":
                _tag_hitter_dialog(player["name"])
            elif player["is_drafted"] == 1:
                st.warning(f"{player['name']} has already been drafted.")
            elif player["salary"] and player["salary"] > 0:
                st.warning(f"{player['name']} is already owned (${int(player['salary'])}).")
            else:
                _draft_hitter_dialog(player["name"])
