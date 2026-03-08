"""Roster planning and budget tracking view."""

import streamlit as st
import pandas as pd

from db.queries import get_roster_plan, update_roster_plan, get_position_targets, save_position_targets

TOTAL_BUDGET = 400
TARGET_POSITIONS = ["C", "1B", "2B", "3B", "SS", "OF", "SP", "RP"]
TARGET_ROLES = ["Starter", "Bench", "Prospect"]


def render_roster():
    """Render the roster planning tab."""
    df = get_roster_plan()

    # Budget summary
    budgeted = int(df["budgeted_salary"].sum())
    spent = int(df["actual_salary"].sum())
    filled = int((df["actual_salary"] > 0).sum())
    total_slots = len(df)

    budget_remaining = TOTAL_BUDGET - budgeted
    salary_remaining = TOTAL_BUDGET - spent
    spots_remaining = total_slots - filled

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Budget Remaining", f"${budget_remaining}", delta=f"${budgeted} budgeted")
    c2.metric("Salary Remaining", f"${salary_remaining}", delta=f"${spent} spent")
    c3.metric("Roster Spots Left", f"{spots_remaining}", delta=f"{filled} / {total_slots} filled")
    c4.metric("Budget / Spot", f"${budget_remaining // spots_remaining if spots_remaining else 0}")
    c5.metric("Salary / Spot", f"${salary_remaining // spots_remaining if spots_remaining else 0}")

    st.divider()

    left_col, right_col = st.columns([2, 3])

    with left_col:
        _render_roster_table(df)

    with right_col:
        _render_position_targets()


def _render_roster_table(df: pd.DataFrame):
    """Render the roster plan as an editable table."""
    # Build display label column
    df["slot"] = df.apply(
        lambda r: f"{r['slot_position']}" if _slot_count(df, r["slot_position"]) == 1
        else f"{r['slot_position']} {r['slot_number']}", axis=1
    )

    edit_df = df[["slot", "player_name", "budgeted_salary", "actual_salary"]].copy()
    edit_df = edit_df.reset_index(drop=True)

    table_height = len(edit_df) * 35 + 38

    edited = st.data_editor(
        edit_df,
        use_container_width=False,
        hide_index=True,
        height=table_height,
        key="roster_table",
        num_rows="fixed",
        column_config={
            "slot": st.column_config.TextColumn("Pos", disabled=True, width=55),
            "player_name": st.column_config.TextColumn("Player", width=270),
            "budgeted_salary": st.column_config.NumberColumn("Budget $", min_value=0, format="$%d", width=120),
            "actual_salary": st.column_config.NumberColumn("Actual $", min_value=0, format="$%d", width=120),
        },
    )

    if not edit_df.equals(edited):
        updates = []
        for i, row in edited.iterrows():
            original_row = df.iloc[i]
            updates.append({
                "id": int(original_row["id"]),
                "player_name": row["player_name"] if pd.notna(row["player_name"]) else "",
                "budgeted_salary": int(row["budgeted_salary"]) if pd.notna(row["budgeted_salary"]) else 0,
                "actual_salary": int(row["actual_salary"]) if pd.notna(row["actual_salary"]) else 0,
            })
        update_roster_plan(updates)
        st.rerun()


def _render_position_targets():
    """Render draft target lists by position."""
    for pos in TARGET_POSITIONS:
        with st.expander(pos, expanded=True):
            targets = get_position_targets(pos)

            # Ensure a few empty rows for adding new targets
            empty_rows = 3
            if targets.empty:
                edit_df = pd.DataFrame({"player_name": [""] * empty_rows, "role": ["Starter"] * empty_rows})
            else:
                edit_df = targets[["player_name", "role"]].copy()

            edited = st.data_editor(
                edit_df,
                use_container_width=True,
                hide_index=True,
                key=f"targets_{pos}",
                num_rows="dynamic",
                column_config={
                    "player_name": st.column_config.TextColumn("Player", width=200),
                    "role": st.column_config.SelectboxColumn("Role", options=TARGET_ROLES, width=100),
                },
            )

            if not edit_df.equals(edited):
                rows = [{"player_name": r["player_name"], "role": r["role"]}
                        for _, r in edited.iterrows()
                        if pd.notna(r["player_name"]) and str(r["player_name"]).strip()]
                save_position_targets(pos, rows)


def _slot_count(df: pd.DataFrame, pos: str) -> int:
    return int((df["slot_position"] == pos).sum())
