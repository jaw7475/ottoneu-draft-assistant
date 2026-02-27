"""Roster planning and budget tracking view."""

import streamlit as st
import pandas as pd

from db.queries import get_roster_plan, update_roster_plan

TOTAL_BUDGET = 400

SECTION_LABELS = {
    "C": "Hitters",
    "SP": "Pitchers",
    "BE": "Bench",
}


def render_roster():
    """Render the roster planning tab."""
    df = get_roster_plan()

    # Budget summary
    budgeted = int(df["budgeted_salary"].sum())
    spent = int(df["actual_salary"].sum())
    filled = int((df["actual_salary"] > 0).sum())
    total_slots = len(df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Budget", f"${TOTAL_BUDGET}")
    c2.metric("Budgeted", f"${budgeted}", delta=f"${TOTAL_BUDGET - budgeted} remaining")
    c3.metric("Spent", f"${spent}", delta=f"${TOTAL_BUDGET - spent} remaining")
    c4.metric("Roster Filled", f"{filled} / {total_slots}")

    st.divider()

    # Build display label column
    df["slot"] = df.apply(
        lambda r: f"{r['slot_position']}" if _slot_count(df, r["slot_position"]) == 1
        else f"{r['slot_position']} {r['slot_number']}", axis=1
    )

    # Render editable sections
    hitter_pos = ["C", "1B", "2B", "SS", "3B", "MI", "OF", "Util"]
    pitcher_pos = ["SP", "RP"]
    bench_pos = ["BE"]

    _render_section("Hitters", df, hitter_pos)
    _render_section("Pitchers", df, pitcher_pos)
    _render_section("Bench", df, bench_pos)


def _slot_count(df: pd.DataFrame, pos: str) -> int:
    return int((df["slot_position"] == pos).sum())


def _render_section(label: str, df: pd.DataFrame, positions: list[str]):
    """Render one section of the roster plan as an editable table."""
    section_df = df[df["slot_position"].isin(positions)].copy()
    if section_df.empty:
        return

    st.subheader(label)

    budget_total = int(section_df["budgeted_salary"].sum())
    actual_total = int(section_df["actual_salary"].sum())
    st.caption(f"Budgeted: ${budget_total} | Spent: ${actual_total}")

    edit_df = section_df[["slot", "player_name", "budgeted_salary", "actual_salary"]].copy()
    edit_df = edit_df.reset_index(drop=True)

    edited = st.data_editor(
        edit_df,
        use_container_width=True,
        hide_index=True,
        key=f"roster_{label}",
        num_rows="fixed",
        column_config={
            "slot": st.column_config.TextColumn("Pos", disabled=True, width="small"),
            "player_name": st.column_config.TextColumn("Player", width="medium"),
            "budgeted_salary": st.column_config.NumberColumn("Budget $", min_value=0, format="$%d", width="small"),
            "actual_salary": st.column_config.NumberColumn("Actual $", min_value=0, format="$%d", width="small"),
        },
    )

    # Detect changes and save
    if not edit_df.equals(edited):
        updates = []
        for i, row in edited.iterrows():
            original_row = section_df.iloc[i]
            updates.append({
                "id": int(original_row["id"]),
                "player_name": row["player_name"] if pd.notna(row["player_name"]) else "",
                "budgeted_salary": int(row["budgeted_salary"]) if pd.notna(row["budgeted_salary"]) else 0,
                "actual_salary": int(row["actual_salary"]) if pd.notna(row["actual_salary"]) else 0,
            })
        update_roster_plan(updates)
        st.rerun()
