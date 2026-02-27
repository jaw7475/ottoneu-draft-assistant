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


ROSTER_PLAN_DDL = """
CREATE TABLE IF NOT EXISTS roster_plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_position TEXT NOT NULL,
    slot_number INTEGER NOT NULL,
    player_name TEXT DEFAULT '',
    budgeted_salary INTEGER DEFAULT 0,
    actual_salary INTEGER DEFAULT 0,
    UNIQUE(slot_position, slot_number)
)
"""

ROSTER_SLOTS = [
    ("C", 2), ("1B", 1), ("2B", 1), ("SS", 1), ("3B", 1),
    ("MI", 1), ("OF", 5), ("Util", 1),
    ("SP", 5), ("RP", 5),
    ("BE", 17),
]


def create_tables(conn):
    """Create supporting tables. Hitters/pitchers tables are created by pandas to_sql."""
    conn.execute(DRAFT_LOG_DDL)
    conn.execute(VALUATION_CONFIG_DDL)
    conn.execute(HISTORICAL_PRICES_DDL)
    conn.execute(ROSTER_PLAN_DDL)
    _seed_roster_plan(conn)
    conn.commit()


def _seed_roster_plan(conn):
    """Insert empty roster slots if they don't exist yet."""
    for position, count in ROSTER_SLOTS:
        for num in range(1, count + 1):
            conn.execute(
                "INSERT OR IGNORE INTO roster_plan (slot_position, slot_number) VALUES (?, ?)",
                (position, num),
            )
