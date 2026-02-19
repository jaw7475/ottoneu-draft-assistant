"""Draft log tab view."""

import streamlit as st

from db.queries import get_draft_log, undo_last_draft


def render_draft_log():
    """Render the draft log tab."""
    df = get_draft_log()

    if df.empty:
        st.info("No players drafted yet. Select a player from the Hitters or Pitchers tab to draft them.")
        return

    # Undo button
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("Undo last draft"):
            player = undo_last_draft()
            if player:
                st.toast(f"Undrafted {player}")
                st.rerun()

    # Display log
    display_cols = ["player_name", "player_type", "projected_salary", "draft_price", "value", "drafting_team", "timestamp"]
    display_cols = [c for c in display_cols if c in df.columns]

    st.dataframe(
        df[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "player_name": "Player",
            "player_type": "Type",
            "projected_salary": st.column_config.NumberColumn("Proj $", format="$%d"),
            "draft_price": st.column_config.NumberColumn("Draft $", format="$%d"),
            "value": st.column_config.NumberColumn("Value", format="%+d"),
            "drafting_team": "Team",
            "timestamp": "Time",
        },
    )

    # Summary stats
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Players drafted", len(df))
    with col2:
        st.metric("Total spent", f"${df['draft_price'].sum()}")
    with col3:
        st.metric("Avg value", f"{df['value'].mean():+.1f}" if "value" in df.columns else "N/A")
