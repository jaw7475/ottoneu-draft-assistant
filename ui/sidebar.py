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


def render_sidebar(active_tab: str, available_columns: list[str]) -> dict:
    """Render sidebar filters and return filter config."""
    with st.sidebar:
        st.header("Filters")

        search = st.text_input("Search player", key="search")
        show_drafted = st.checkbox("Show drafted players", key="show_drafted")

        # Position filter
        if active_tab == "Hitters":
            positions = st.multiselect("Position", HITTER_POSITIONS, key="pos_filter")
        else:
            positions = st.multiselect("Position", PITCHER_POSITIONS, key="pos_filter")

        # Sort controls
        st.subheader("Sort")
        sort_options = [c for c in available_columns if c not in ("name", "ottoneu_team", "position", "is_drafted")]
        default_sort = "fpts" if "fpts" in sort_options else sort_options[0] if sort_options else "name"
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

    return {
        "search": search,
        "positions": positions if positions else None,
        "show_drafted": show_drafted,
        "sort_by": sort_by,
        "sort_asc": sort_asc,
        "stat_filters": stat_filters if stat_filters else None,
    }
