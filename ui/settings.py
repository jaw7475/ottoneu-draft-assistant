"""Settings page for data upload, league config, and model training."""

import streamlit as st

from data.positions import load_position_universe
from db.queries import (
    get_historical_prices,
    get_valuation_config,
    recalculate_values,
    set_valuation_config,
    update_from_position_csv,
)
from valuation.dollar_value import DEFAULT_CONFIG


def render_settings():
    """Render the settings tab."""
    _render_league_config()
    st.divider()
    _render_position_upload()
    st.divider()
    _render_historical_upload()
    st.divider()
    _render_reload()


def _render_league_config():
    """League configuration for valuation calculations."""
    st.subheader("League Configuration")

    config = get_valuation_config()

    col1, col2 = st.columns(2)
    with col1:
        num_teams = st.number_input(
            "Number of teams",
            min_value=4, max_value=30,
            value=int(config.get("num_teams", DEFAULT_CONFIG["num_teams"])),
            key="cfg_num_teams",
        )
        budget_per_team = st.number_input(
            "Budget per team ($)",
            min_value=100, max_value=1000,
            value=int(config.get("budget_per_team", DEFAULT_CONFIG["budget_per_team"])),
            key="cfg_budget",
        )
    with col2:
        hitter_budget_pct = st.slider(
            "Hitter budget %",
            min_value=30, max_value=80,
            value=int(config.get("hitter_budget_pct", DEFAULT_CONFIG["hitter_budget_pct"])),
            key="cfg_hitter_pct",
        )
        hitters_per_team = st.number_input(
            "Hitters per team",
            min_value=5, max_value=30,
            value=int(config.get("hitters_per_team", DEFAULT_CONFIG["hitters_per_team"])),
            key="cfg_hitters_per",
        )
        pitchers_per_team = st.number_input(
            "Pitchers per team",
            min_value=5, max_value=30,
            value=int(config.get("pitchers_per_team", DEFAULT_CONFIG["pitchers_per_team"])),
            key="cfg_pitchers_per",
        )

    if st.button("Recalculate Values"):
        new_config = {
            "num_teams": str(num_teams),
            "budget_per_team": str(budget_per_team),
            "hitter_budget_pct": str(hitter_budget_pct),
            "hitters_per_team": str(hitters_per_team),
            "pitchers_per_team": str(pitchers_per_team),
        }
        set_valuation_config(new_config)
        with st.spinner("Recalculating..."):
            recalculate_values()
        st.success("Dollar values recalculated.")
        st.rerun()


def _render_position_upload():
    """Position data upload."""
    st.subheader("Position Data")
    st.write("Upload an Ottoneu average values CSV export to update position, team, salary, and ownership data.")

    uploaded_file = st.file_uploader("Ottoneu average values CSV", type=["csv"])

    if uploaded_file is not None:
        if st.button("Load positions"):
            try:
                pos_df = load_position_universe(uploaded_file)
                h_updated = update_from_position_csv("hitters", pos_df)
                p_updated = update_from_position_csv("pitchers", pos_df)
                st.success(f"Updated {h_updated} hitters and {p_updated} pitchers.")
            except Exception as e:
                st.error(f"Error parsing file: {e}")


def _render_historical_upload():
    """Draft data display and model training."""
    st.subheader("Draft Data")
    st.write("Draft data is loaded automatically from `draft_results.csv` during database init.")

    # Show existing draft data count
    hist = get_historical_prices()
    if not hist.empty:
        seasons = hist["season"].unique()
        st.write(f"Draft data loaded: {len(hist)} records across seasons {sorted(seasons.tolist())}")

        if st.button("Train Price Model"):
            from valuation.price_model import train_and_predict

            with st.spinner("Training model..."):
                try:
                    result = train_and_predict()
                    st.success(
                        f"Model trained! R²={result['r2']:.3f}, "
                        f"matched {result['matched_count']} players."
                    )
                    if result.get("feature_weights"):
                        st.write("**Feature weights:**")
                        for feat, weight in sorted(
                            result["feature_weights"].items(),
                            key=lambda x: abs(x[1]),
                            reverse=True,
                        ):
                            st.write(f"  {feat}: {weight:+.3f}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error training model: {e}")
    else:
        st.info("No draft data loaded. Place `draft_results.csv` in the data directory and reload.")


def _render_reload():
    """Database reload."""
    st.subheader("Reload Data")
    st.write("Re-run the data pipeline to rebuild the database from source files.")

    if st.button("Reload data"):
        from db.init_db import init_db
        with st.spinner("Reloading..."):
            init_db()
        st.success("Database rebuilt successfully.")
        st.rerun()
