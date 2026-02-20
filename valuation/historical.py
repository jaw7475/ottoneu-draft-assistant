"""Parse Ottoneu FA auction export CSVs."""

import pandas as pd


def parse_auction_csv(file, season: int) -> list[dict]:
    """Parse an uploaded FA auction CSV into a list of dicts.

    Expected columns (flexible matching): player name, price, position, date.
    """
    df = pd.read_csv(file, encoding="utf-8-sig")

    # Normalize column names to lowercase for flexible matching
    df.columns = [c.strip().lower() for c in df.columns]

    # Find the name column
    name_col = _find_column(df.columns, ["name", "player", "player_name", "player name"])
    if name_col is None:
        raise ValueError("Could not find player name column. Expected: Name, Player, or Player Name")

    # Find the price column
    price_col = _find_column(df.columns, ["price", "salary", "cost", "$", "winning bid"])
    if price_col is None:
        raise ValueError("Could not find price column. Expected: Price, Salary, Cost, or $")

    # Optional columns
    pos_col = _find_column(df.columns, ["position", "pos", "positions"])
    date_col = _find_column(df.columns, ["date", "auction_date", "auction date"])

    rows = []
    for _, row in df.iterrows():
        name = str(row[name_col]).strip()
        if not name or name.lower() == "nan":
            continue

        price_val = row[price_col]
        if pd.isna(price_val):
            price = None
        else:
            price_str = str(price_val).strip().lstrip("$").strip()
            try:
                price = int(float(price_str))
            except (ValueError, TypeError):
                price = None

        position = str(row[pos_col]).strip() if pos_col and pd.notna(row[pos_col]) else None
        auction_date = str(row[date_col]).strip() if date_col and pd.notna(row[date_col]) else None

        rows.append({
            "player_name": name,
            "season": season,
            "price": price,
            "position": position,
            "auction_date": auction_date,
        })

    return rows


def _find_column(columns, candidates: list[str]) -> str | None:
    """Find the first matching column name from a list of candidates."""
    col_list = list(columns)
    for candidate in candidates:
        for col in col_list:
            if col == candidate:
                return col
    return None
