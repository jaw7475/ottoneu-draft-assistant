"""One-time database population script."""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.load import DATA_DIR, load_all
from data.merge import merge_hitters, merge_pitchers
from db.connection import DB_PATH, get_connection
from db.queries import save_historical_prices
from db.schema import create_tables
from valuation.dollar_value import DEFAULT_CONFIG, calculate_dollar_values
from valuation.historical import load_draft_results
from valuation.price_model import train_and_predict


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

    # Load draft results if available
    draft_csv = DATA_DIR / "draft_results.csv"
    if draft_csv.exists():
        print("\nLoading draft results...")
        rows = load_draft_results(draft_csv)
        count = save_historical_prices(rows)
        print(f"  Loaded {count} draft records")
    else:
        print(f"\nNo draft_results.csv found at {draft_csv} — skipping price model.")

    # Train price prediction model if draft data was loaded
    hist_count = conn.execute("SELECT COUNT(*) FROM historical_prices").fetchone()[0]
    if hist_count > 0 and has_proj:
        print("\nTraining price prediction model...")
        conn.close()
        try:
            result = train_and_predict()
            print(f"  R²={result['r2']:.3f}, matched {result['matched_count']} players")
        except Exception as e:
            print(f"  Warning: model training failed: {e}")
        conn = get_connection()

    # Verify
    h_count = conn.execute("SELECT COUNT(*) FROM hitters").fetchone()[0]
    p_count = conn.execute("SELECT COUNT(*) FROM pitchers").fetchone()[0]
    print(f"\nDone! Hitters: {h_count}, Pitchers: {p_count}")

    conn.close()


if __name__ == "__main__":
    init_db()
