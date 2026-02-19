"""Parse Ottoneu average values export to extract player positions."""

import pandas as pd


def parse_positions(uploaded_file) -> dict[str, str]:
    """Parse an Ottoneu average values CSV export.

    Returns a dict of {player_name: position_string}.
    Position string is comma-separated, e.g. "1B,OF" or "SP,RP".
    """
    df = pd.read_csv(uploaded_file, encoding="utf-8-sig")

    # The export has columns like: Name, Position(s), ...
    # Find the position column (may vary in exact naming)
    pos_col = None
    for col in df.columns:
        if "pos" in col.lower():
            pos_col = col
            break

    name_col = None
    for col in df.columns:
        if "name" in col.lower():
            name_col = col
            break

    if pos_col is None or name_col is None:
        raise ValueError(
            f"Could not find Name/Position columns. Found: {list(df.columns)}"
        )

    df = df.dropna(subset=[name_col])
    return dict(zip(df[name_col].str.strip(), df[pos_col].str.strip()))
