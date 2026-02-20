"""Pitchers tab view."""

import streamlit as st

from db.queries import draft_player, get_teams, query_players

# Default columns to display (key stats)
DEFAULT_COLUMNS = [
    "name", "ottoneu_team", "salary", "position", "fpts",
    "dollar_value", "surplus_value",
    "ip", "era", "fip", "xera", "k_per_9", "bb_per_9",
    "sv", "hld", "war", "stuff_plus", "pitching_plus",
    "draft_price",
]

COLUMN_CONFIG = {
    "dollar_value": st.column_config.NumberColumn("$Value", format="$%d"),
    "surplus_value": st.column_config.NumberColumn("Surplus", format="%+d"),
    "predicted_price": st.column_config.NumberColumn("Pred$", format="$%d"),
}


def render_pitchers(filters: dict):
    """Render the pitchers tab."""
    df = query_players(
        table="pitchers",
        search=filters["search"],
        positions=filters["positions"],
        show_drafted=filters["show_drafted"],
        sort_by=filters["sort_by"],
        sort_asc=filters["sort_asc"],
        stat_filters=filters["stat_filters"],
    )

    # Select display columns
    all_cols = df.columns.tolist()
    display_cols = [c for c in DEFAULT_COLUMNS if c in all_cols]

    with st.expander("Column selection"):
        extra_cols = [c for c in all_cols if c not in display_cols and c != "is_drafted"]
        selected_extra = st.multiselect("Additional columns", extra_cols, key="pitcher_extra_cols")
        display_cols = display_cols + selected_extra

    display_df = df[display_cols].copy()

    col_cfg = {k: v for k, v in COLUMN_CONFIG.items() if k in display_cols}
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=600,
        on_select="rerun",
        selection_mode="single-row",
        key="pitchers_table",
        column_config=col_cfg,
    )

    # Draft action form
    selection = st.session_state.get("pitchers_table", {})
    selected_rows = selection.get("selection", {}).get("rows", [])

    if selected_rows:
        idx = selected_rows[0]
        if idx < len(df):
            player = df.iloc[idx]
            st.subheader(f"Draft: {player['name']}")

            teams = get_teams("pitchers")
            with st.form("draft_pitcher_form"):
                col1, col2 = st.columns(2)
                with col1:
                    price = st.number_input("Draft price ($)", min_value=1, value=1, step=1)
                with col2:
                    team = st.selectbox("Drafting team", [""] + teams)

                if st.form_submit_button("Confirm Draft"):
                    draft_player("pitchers", player["name"], price, team)
                    st.rerun()
