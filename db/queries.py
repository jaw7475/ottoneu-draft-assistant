"""Parameterized query builders for the draft database."""

import sqlite3

import pandas as pd

from db.connection import get_connection


def query_players(
    table: str,
    search: str = "",
    positions: list[str] | None = None,
    show_drafted: bool = False,
    sort_by: str = "fpts",
    sort_asc: bool = False,
    stat_filters: dict[str, tuple[float | None, float | None]] | None = None,
) -> pd.DataFrame:
    """Query hitters or pitchers with filters."""
    conn = get_connection()
    conditions = []
    params = []

    if not show_drafted:
        conditions.append("is_drafted = 0")

    if search:
        conditions.append("name LIKE ?")
        params.append(f"%{search}%")

    if positions:
        pos_clauses = []
        for pos in positions:
            pos_clauses.append("position LIKE ?")
            params.append(f"%{pos}%")
        conditions.append(f"({' OR '.join(pos_clauses)})")

    if stat_filters:
        for col, (min_val, max_val) in stat_filters.items():
            if min_val is not None:
                conditions.append(f"{col} >= ?")
                params.append(min_val)
            if max_val is not None:
                conditions.append(f"{col} <= ?")
                params.append(max_val)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Validate sort column against actual table columns
    col_info = pd.read_sql(f"PRAGMA table_info({table})", conn)
    valid_columns = set(col_info["name"].tolist())
    if sort_by not in valid_columns:
        sort_by = "fpts"

    direction = "ASC" if sort_asc else "DESC"
    # Put NULLs last
    query = f"SELECT * FROM {table} {where} ORDER BY {sort_by} IS NULL, {sort_by} {direction}"

    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df


def draft_player(
    table: str,
    player_name: str,
    draft_price: int,
    drafting_team: str = "",
) -> None:
    """Mark a player as drafted and log the action."""
    conn = get_connection()

    # Get projected salary
    row = conn.execute(
        f"SELECT salary FROM {table} WHERE name = ?", (player_name,)
    ).fetchone()
    projected_salary = row["salary"] if row else None

    # Update player
    conn.execute(
        f"UPDATE {table} SET is_drafted = 1, draft_price = ? WHERE name = ?",
        (draft_price, player_name),
    )

    # Log the draft
    player_type = "hitter" if table == "hitters" else "pitcher"
    conn.execute(
        """INSERT INTO draft_log (player_name, player_type, projected_salary, draft_price, drafting_team)
           VALUES (?, ?, ?, ?, ?)""",
        (player_name, player_type, projected_salary, draft_price, drafting_team),
    )
    conn.commit()
    conn.close()


def undo_last_draft() -> str | None:
    """Undo the most recent draft action. Returns the player name or None."""
    conn = get_connection()

    last = conn.execute(
        "SELECT * FROM draft_log ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if not last:
        conn.close()
        return None

    player_name = last["player_name"]
    player_type = last["player_type"]
    table = "hitters" if player_type == "hitter" else "pitchers"

    conn.execute(
        f"UPDATE {table} SET is_drafted = 0, draft_price = NULL WHERE name = ?",
        (player_name,),
    )
    conn.execute("DELETE FROM draft_log WHERE id = ?", (last["id"],))
    conn.commit()
    conn.close()
    return player_name


def get_draft_log() -> pd.DataFrame:
    """Get the full draft log in reverse chronological order."""
    conn = get_connection()
    df = pd.read_sql(
        "SELECT * FROM draft_log ORDER BY id DESC",
        conn,
    )
    conn.close()

    if not df.empty:
        df["value"] = df["projected_salary"].fillna(0) - df["draft_price"]

    return df


def get_teams(table: str) -> list[str]:
    """Get unique team names from a table."""
    conn = get_connection()
    rows = conn.execute(
        f"SELECT DISTINCT ottoneu_team FROM {table} WHERE ottoneu_team IS NOT NULL ORDER BY ottoneu_team"
    ).fetchall()
    conn.close()
    return [r["ottoneu_team"] for r in rows]


def update_positions(table: str, positions: dict[str, str]) -> int:
    """Update position data for players. Returns count of updated rows."""
    conn = get_connection()
    updated = 0
    for name, pos in positions.items():
        cursor = conn.execute(
            f"UPDATE {table} SET position = ? WHERE name = ?",
            (pos, name),
        )
        updated += cursor.rowcount
    conn.commit()
    conn.close()
    return updated


def get_column_names(table: str) -> list[str]:
    """Get column names for a table."""
    conn = get_connection()
    col_info = pd.read_sql(f"PRAGMA table_info({table})", conn)
    conn.close()
    return col_info["name"].tolist()


def get_valuation_config() -> dict[str, str]:
    """Get all valuation config key-value pairs."""
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM valuation_config").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def set_valuation_config(config: dict[str, str]) -> None:
    """Upsert valuation config values."""
    conn = get_connection()
    for key, value in config.items():
        conn.execute(
            "INSERT OR REPLACE INTO valuation_config (key, value) VALUES (?, ?)",
            (key, str(value)),
        )
    conn.commit()
    conn.close()


def save_historical_prices(rows: list[dict]) -> int:
    """Insert historical FA auction prices. Returns count of inserted rows."""
    conn = get_connection()
    inserted = 0
    for row in rows:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO historical_prices
                   (player_name, season, price, position, auction_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (row["player_name"], row["season"], row.get("price"),
                 row.get("position"), row.get("auction_date")),
            )
            inserted += 1
        except Exception:
            continue
    conn.commit()
    conn.close()
    return inserted


def get_historical_prices() -> pd.DataFrame:
    """Get all historical FA auction prices."""
    conn = get_connection()
    df = pd.read_sql("SELECT * FROM historical_prices ORDER BY season, player_name", conn)
    conn.close()
    return df


def recalculate_values() -> None:
    """Recalculate dollar values in-place using current config and projections."""
    from valuation.dollar_value import calculate_dollar_values

    conn = get_connection()
    config = dict(conn.execute("SELECT key, value FROM valuation_config").fetchall())

    hitters = pd.read_sql("SELECT * FROM hitters", conn)
    pitchers = pd.read_sql("SELECT * FROM pitchers", conn)

    if "proj_fpts" not in hitters.columns and "proj_fpts" not in pitchers.columns:
        conn.close()
        return

    hitters, pitchers = calculate_dollar_values(hitters, pitchers, config)

    hitters.to_sql("hitters", conn, if_exists="replace", index=False)
    pitchers.to_sql("pitchers", conn, if_exists="replace", index=False)
    conn.close()
