"""Settings page for data upload and reload."""

import streamlit as st

from data.positions import parse_positions
from db.queries import update_positions


def render_settings():
    """Render the settings tab."""
    st.subheader("Position Data")
    st.write("Upload an Ottoneu average values CSV export to populate position data.")

    uploaded_file = st.file_uploader("Ottoneu average values CSV", type=["csv"])

    if uploaded_file is not None:
        if st.button("Load positions"):
            try:
                positions = parse_positions(uploaded_file)
                h_updated = update_positions("hitters", positions)
                p_updated = update_positions("pitchers", positions)
                st.success(f"Updated positions for {h_updated} hitters and {p_updated} pitchers.")
            except Exception as e:
                st.error(f"Error parsing file: {e}")

    st.divider()
    st.subheader("Reload Data")
    st.write("Re-run the data pipeline to rebuild the database from source files.")

    if st.button("Reload data"):
        from db.init_db import init_db
        with st.spinner("Reloading..."):
            init_db()
        st.success("Database rebuilt successfully.")
        st.rerun()
