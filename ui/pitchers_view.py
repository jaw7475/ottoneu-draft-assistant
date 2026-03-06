"""Pitchers tab view."""

import streamlit as st

from db.queries import draft_player, get_teams, query_players

# Default columns to display (key stats)
DEFAULT_COLUMNS = [
    "avail", "name", "ottoneu_team", "salary", "position", "fpts",
    "dollar_value", "surplus_value",
    "ip", "era", "fip", "xera", "k_per_9", "bb_per_9",
    "sv", "hld", "war", "stuff_plus", "pitching_plus",
]

COLUMN_CONFIG = {
    "avail": st.column_config.CheckboxColumn("Avail", disabled=True),
    "dollar_value": st.column_config.NumberColumn("$Value", format="$%d"),
    "surplus_value": st.column_config.NumberColumn("Surplus", format="%+d"),
    "predicted_price": st.column_config.NumberColumn("Pred$", format="$%d"),
    "ownership_pct": st.column_config.NumberColumn("Own%", format="%.1f%%"),
}


@st.dialog("Draft Player")
def _draft_pitcher_dialog(player_name: str):
    """Dialog overlay for drafting a pitcher."""
    st.markdown(f"**{player_name}**")
    teams = get_teams("pitchers")
    price = st.number_input("Draft price ($)", min_value=1, value=1, step=1, key="draft_pitcher_price")
    team = st.selectbox("Drafting team", [""] + teams, key="draft_pitcher_team")
    if st.button("Confirm Draft", key="draft_pitcher_confirm"):
        draft_player("pitchers", player_name, price, team)
        st.rerun()


def render_pitchers(filters: dict):
    """Render the pitchers tab."""
    df = query_players(
        table="pitchers",
        search=filters["search"],
        positions=filters["positions"],
        show_drafted=filters["show_drafted"],
        show_kept=filters["show_kept"],
        sort_by=filters["sort_by"],
        sort_asc=filters["sort_asc"],
        stat_filters=filters["stat_filters"],
    )

    # Compute availability indicator
    df["avail"] = (df["salary"].fillna(0) == 0) & (df["is_drafted"] == 0)

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

    # Style salary cells with blue background for drafted players
    def highlight_drafted_salary(col):
        styles = [""] * len(col)
        if col.name == "salary":
            for i, idx in enumerate(col.index):
                if df.loc[idx, "is_drafted"] == 1:
                    styles[i] = "background-color: #cce5ff"
        return styles

    styled = display_df.style.apply(highlight_drafted_salary)

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
