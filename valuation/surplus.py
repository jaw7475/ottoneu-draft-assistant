"""Surplus value calculation: dollar_value - predicted_price."""

import pandas as pd

from db.connection import get_connection


def update_surplus_values() -> None:
    """Recalculate surplus_value = dollar_value - predicted_price for all players."""
    conn = get_connection()

    for table in ("hitters", "pitchers"):
        conn.execute(f"""
            UPDATE {table}
            SET surplus_value = dollar_value - predicted_price
            WHERE dollar_value IS NOT NULL AND predicted_price IS NOT NULL
        """)

    conn.commit()
    conn.close()
