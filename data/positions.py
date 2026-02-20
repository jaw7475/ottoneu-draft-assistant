"""Parse Ottoneu average values export to extract player positions and universe."""

import pandas as pd

from data.load import _parse_salary


def _find_column(columns, patterns):
    """Find a column matching any of the given patterns (case-insensitive)."""
    for col in columns:
        lower = col.lower()
        for pattern in patterns:
            if pattern in lower:
                return col
    return None


def _parse_ownership(val):
    """Parse ownership percentage: strip '%' → float (0-100 scale)."""
    if pd.isna(val):
        return pd.NA
    s = str(val).strip().rstrip("%").strip()
    if s == "":
        return pd.NA
    try:
        return float(s)
    except ValueError:
        return pd.NA


def load_position_universe(source) -> pd.DataFrame:
    """Load a position CSV and return a DataFrame with standardized columns.

    Accepts a file path (str/Path) or file-like object (Streamlit upload).
    Returns DataFrame with columns: name, position, ottoneu_team, salary, ownership_pct.
    """
    df = pd.read_csv(source, encoding="utf-8-sig")

    # Drop trailing unnamed empty columns
    unnamed_cols = [c for c in df.columns if str(c).startswith("Unnamed")]
    if unnamed_cols:
        df = df.drop(columns=unnamed_cols)

    # Find columns flexibly by pattern
    name_col = _find_column(df.columns, ["name"])
    pos_col = _find_column(df.columns, ["pos"])
    team_col = _find_column(df.columns, ["fantasy", "team"])
    salary_col = _find_column(df.columns, ["$"])
    own_col = _find_column(df.columns, ["own", "rost"])

    if name_col is None:
        raise ValueError(
            f"Could not find Name column. Found: {list(df.columns)}"
        )

    # Drop rows with no name
    df = df.dropna(subset=[name_col])

    # Build result DataFrame
    result = pd.DataFrame()
    result["name"] = df[name_col].str.strip()

    if pos_col is not None:
        result["position"] = df[pos_col].str.strip()
    else:
        result["position"] = pd.NA

    if team_col is not None:
        result["ottoneu_team"] = df[team_col].apply(
            lambda v: str(v).strip() if pd.notna(v) and str(v).strip() else pd.NA
        )
    else:
        result["ottoneu_team"] = pd.NA

    if salary_col is not None:
        result["salary"] = df[salary_col].apply(_parse_salary)
    else:
        result["salary"] = pd.NA

    if own_col is not None:
        result["ownership_pct"] = df[own_col].apply(_parse_ownership)
    else:
        result["ownership_pct"] = pd.NA

    # Deduplicate on name
    result = result.drop_duplicates(subset="name", keep="first")

    return result


def parse_positions(uploaded_file) -> dict[str, str]:
    """Parse an Ottoneu average values CSV export.

    Returns a dict of {player_name: position_string}.
    Delegates to load_position_universe() for parsing.
    """
    pos_df = load_position_universe(uploaded_file)
    pos_df = pos_df.dropna(subset=["position"])
    return dict(zip(pos_df["name"], pos_df["position"]))
