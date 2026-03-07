"""Shared sidebar filters for the draft assistant."""

import streamlit as st


HITTER_POSITIONS = ["C", "1B", "2B", "SS", "3B", "OF", "DH", "Util"]
PITCHER_POSITIONS = ["SP", "RP"]

HITTER_KEY_STATS = [
    "fpts", "dollar_value", "surplus_value",
    "wrc_plus", "ops", "woba", "iso", "avg", "obp", "slg", "hr", "sb", "bb_pct", "k_pct",
]
PITCHER_KEY_STATS = [
    "fpts", "dollar_value", "surplus_value",
    "era", "fip", "xera", "k_per_9", "bb_per_9", "ip", "sv", "war", "stuff_plus", "pitching_plus",
]


def render_sidebar(active_tab: str, available_columns: list[str],
                   hitter_column_groups: dict | None = None,
                   pitcher_column_groups: dict | None = None,
                   hitter_all_cols: list[str] | None = None,
                   pitcher_all_cols: list[str] | None = None,
                   hidden: set | None = None) -> dict:
    """Render sidebar filters and return filter config."""
    with st.sidebar:
        st.header("Filters")

        click_mode = st.radio(
            "Row click mode",
            ["Draft", "Tag"],
            horizontal=True,
            key="click_mode",
        )

        show_kept = st.checkbox("Show kept players", value=True, key="show_kept")
        show_drafted = st.checkbox("Show drafted players", key="show_drafted")

        # Position filter (separate keys per tab to avoid stale widget state)
        hitter_positions = st.multiselect("Hitter positions", HITTER_POSITIONS, key="hitter_pos_filter")
        pitcher_positions = st.multiselect("Pitcher positions", PITCHER_POSITIONS, key="pitcher_pos_filter")

        # Sort controls
        st.subheader("Sort")
        sort_options = [c for c in available_columns if c not in ("name", "ottoneu_team", "position", "is_drafted", "is_keeper")]
        default_sort = "proj_fpts" if "proj_fpts" in sort_options else "fpts" if "fpts" in sort_options else sort_options[0] if sort_options else "name"
        sort_by = st.selectbox("Sort by", sort_options, index=sort_options.index(default_sort) if default_sort in sort_options else 0, key="sort_by")
        sort_asc = st.checkbox("Ascending", key="sort_asc")

        # Stat range filters
        key_stats = HITTER_KEY_STATS if active_tab == "Hitters" else PITCHER_KEY_STATS
        stat_filters = {}
        with st.expander("Stat filters"):
            for stat in key_stats:
                if stat in available_columns:
                    col1, col2 = st.columns(2)
                    with col1:
                        min_val = st.number_input(f"{stat} min", value=None, key=f"{stat}_min")
                    with col2:
                        max_val = st.number_input(f"{stat} max", value=None, key=f"{stat}_max")
                    if min_val is not None or max_val is not None:
                        stat_filters[stat] = (min_val, max_val)

        # Column selection by group (for hitters and pitchers)
        _hidden = hidden or set()
        hitter_selected = {}
        pitcher_selected = {}

        if hitter_column_groups and hitter_all_cols is not None:
            with st.expander("Hitter columns"):
                for group_name, group_cols in hitter_column_groups.items():
                    available = [c for c in group_cols if c in hitter_all_cols and c not in _hidden]
                    if not available:
                        continue
                    selected = st.multiselect(
                        group_name,
                        available,
                        default=available,
                        key=f"hitter_group_{group_name}",
                    )
                    hitter_selected[group_name] = selected

        if pitcher_column_groups and pitcher_all_cols is not None:
            with st.expander("Pitcher columns"):
                for group_name, group_cols in pitcher_column_groups.items():
                    available = [c for c in group_cols if c in pitcher_all_cols and c not in _hidden]
                    if not available:
                        continue
                    selected = st.multiselect(
                        group_name,
                        available,
                        default=available,
                        key=f"pitcher_group_{group_name}",
                    )
                    pitcher_selected[group_name] = selected

    return {
        "click_mode": click_mode.lower(),
        "search": "",
        "hitter_positions": hitter_positions if hitter_positions else None,
        "pitcher_positions": pitcher_positions if pitcher_positions else None,
        "show_kept": show_kept,
        "show_drafted": show_drafted,
        "sort_by": sort_by,
        "sort_asc": sort_asc,
        "stat_filters": stat_filters if stat_filters else None,
        "hitter_selected_groups": hitter_selected,
        "pitcher_selected_groups": pitcher_selected,
    }
