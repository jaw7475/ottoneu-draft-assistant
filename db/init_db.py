"""One-time database population script."""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.load import load_all
from data.merge import merge_hitters, merge_pitchers
from db.connection import DB_PATH, get_connection
from db.schema import create_tables
from valuation.dollar_value import DEFAULT_CONFIG, calculate_dollar_values


def _seed_default_config(conn):
    """Insert default valuation config if not present."""
    for key, value in DEFAULT_CONFIG.items():
        conn.execute(
            "INSERT OR IGNORE INTO valuation_config (key, value) VALUES (?, ?)",
            (key, str(value)),
        )
    conn.commit()


def _load_config(conn) -> dict:
    """Load valuation config from DB."""
    rows = conn.execute("SELECT key, value FROM valuation_config").fetchall()
    return {r["key"]: r["value"] for r in rows}


def init_db():
    """Run the full pipeline: load → clean → merge → value → write to SQLite."""
    print("Loading source files...")
    files = load_all()
    for name, df in files.items():
        print(f"  {name}: {len(df)} rows, {len(df.columns)} columns")

    print("\nMerging hitters...")
    hitters = merge_hitters(files)
    print(f"  Merged hitters: {len(hitters)} rows, {len(hitters.columns)} columns")

    print("\nMerging pitchers...")
    pitchers = merge_pitchers(files)
    print(f"  Merged pitchers: {len(pitchers)} rows, {len(pitchers.columns)} columns")

    # Remove old DB if it exists
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"\nRemoved existing {DB_PATH}")

    print(f"\nWriting to {DB_PATH}...")
    conn = get_connection()
    create_tables(conn)
    _seed_default_config(conn)

    # Calculate dollar values if projections are available
    config = _load_config(conn)
    has_proj = "proj_fpts" in hitters.columns or "proj_fpts" in pitchers.columns
    if has_proj:
        print("\nCalculating dollar values from projections...")
        hitters, pitchers = calculate_dollar_values(hitters, pitchers, config)
        h_valued = hitters["dollar_value"].notna().sum()
        p_valued = pitchers["dollar_value"].notna().sum()
        print(f"  Valued {h_valued} hitters, {p_valued} pitchers")
    else:
        print("\nNo projection data found — skipping dollar value calculation.")

    hitters.to_sql("hitters", conn, if_exists="replace", index=False)
    pitchers.to_sql("pitchers", conn, if_exists="replace", index=False)

    # Verify
    h_count = conn.execute("SELECT COUNT(*) FROM hitters").fetchone()[0]
    p_count = conn.execute("SELECT COUNT(*) FROM pitchers").fetchone()[0]
    print(f"\nDone! Hitters: {h_count}, Pitchers: {p_count}")

    conn.close()


if __name__ == "__main__":
    init_db()
