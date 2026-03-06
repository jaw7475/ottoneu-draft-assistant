"""Pitchers tab view."""

import streamlit as st

from db.queries import draft_player, get_teams, query_players

# Default columns to display (key stats)
DEFAULT_COLUMNS = [
    "avail", "name", "ottoneu_team", "salary", "position", "fpts",
    "dollar_value", "surplus_value", "expert1_rank", "expert2_rank",
    "ip", "era", "fip", "xera", "k_per_9", "bb_per_9",
    "sv", "hld", "war", "stuff_plus", "pitching_plus",
]

COLUMN_CONFIG = {
    "avail": st.column_config.TextColumn("", width=47),
    "dollar_value": st.column_config.NumberColumn("$Value", format="$%d"),
    "surplus_value": st.column_config.NumberColumn("Surplus", format="%+d"),
    "predicted_price": st.column_config.NumberColumn("Pred$", format="$%d"),
    "ownership_pct": st.column_config.NumberColumn("Own%", format="%.1f%%"),
    "expert1_rank": st.column_config.NumberColumn("E1 Rank", format="%d"),
    "expert1_tier": st.column_config.NumberColumn("E1 Tier", format="%d"),
    "expert2_rank": st.column_config.NumberColumn("E2 Rank", format="%d"),
    "expert2_tier": st.column_config.NumberColumn("E2 Tier", format="%d"),
}


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


def render_pitchers(filters: dict):
    """Render the pitchers tab."""
    df = query_players(
        table="pitchers",
        search=filters["search"],
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

    # Select display columns
    all_cols = df.columns.tolist()
    hidden = {"is_drafted", "draft_price", "is_keeper", "avail"}
    display_cols = [c for c in DEFAULT_COLUMNS if c in all_cols]

    with st.expander("Column selection"):
        extra_cols = [c for c in all_cols if c not in display_cols and c not in hidden]
        selected_extra = st.multiselect("Additional columns", extra_cols, key="pitcher_extra_cols")
        display_cols = display_cols + selected_extra

    display_df = df[display_cols].copy()

    # Style salary and avail columns
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
            if player["is_drafted"] == 1:
                st.warning(f"{player['name']} has already been drafted.")
            elif player["salary"] and player["salary"] > 0:
                st.warning(f"{player['name']} is already owned (${int(player['salary'])}).")
            else:
                _draft_pitcher_dialog(player["name"])
