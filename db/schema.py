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

VALUATION_CONFIG_DDL = """
CREATE TABLE IF NOT EXISTS valuation_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
)
"""

HISTORICAL_PRICES_DDL = """
CREATE TABLE IF NOT EXISTS historical_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT NOT NULL,
    season INTEGER NOT NULL,
    price INTEGER,
    position TEXT,
    auction_date TEXT,
    UNIQUE(player_name, season)
)
"""


def create_tables(conn):
    """Create supporting tables. Hitters/pitchers tables are created by pandas to_sql."""
    conn.execute(DRAFT_LOG_DDL)
    conn.execute(VALUATION_CONFIG_DDL)
    conn.execute(HISTORICAL_PRICES_DDL)
    conn.commit()
