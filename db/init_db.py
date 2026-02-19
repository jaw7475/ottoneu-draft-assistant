"""One-time database population script."""

import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.load import load_all
from data.merge import merge_hitters, merge_pitchers
from db.connection import DB_PATH, get_connection
from db.schema import create_tables


def init_db():
    """Run the full pipeline: load → clean → merge → write to SQLite."""
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

    hitters.to_sql("hitters", conn, if_exists="replace", index=False)
    pitchers.to_sql("pitchers", conn, if_exists="replace", index=False)

    # Verify
    h_count = conn.execute("SELECT COUNT(*) FROM hitters").fetchone()[0]
    p_count = conn.execute("SELECT COUNT(*) FROM pitchers").fetchone()[0]
    print(f"\nDone! Hitters: {h_count}, Pitchers: {p_count}")

    conn.close()


if __name__ == "__main__":
    init_db()
