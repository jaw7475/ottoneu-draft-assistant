"""SQLite DDL for the draft database."""

DRAFT_LOG_DDL = """
CREATE TABLE IF NOT EXISTS draft_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT NOT NULL,
    player_type TEXT NOT NULL,
    projected_salary INTEGER,
    draft_price INTEGER NOT NULL,
    drafting_team TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""


def create_tables(conn):
    """Create the draft_log table. Hitters/pitchers tables are created by pandas to_sql."""
    conn.execute(DRAFT_LOG_DDL)
    conn.commit()
