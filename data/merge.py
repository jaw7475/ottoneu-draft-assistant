"""Merge loaded DataFrames into unified hitters and pitchers tables."""

import pandas as pd

# Players with no projections, no historical stats, and ownership at or below
# this threshold are pruned from the database.
OWNERSHIP_PRUNE_THRESHOLD = 5.0


def _dedup(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate names, keeping the first occurrence (highest ranked)."""
    return df.drop_duplicates(subset="name", keep="first")


def _merge_pair(base: pd.DataFrame, other: pd.DataFrame) -> pd.DataFrame:
    """Merge two DataFrames on name, adding only new columns from other.

    Shared metadata columns (ottoneu_team, salary) are filled from other
    where base has NaN.
    """
    other = _dedup(other)

    # Columns to add from other (not already in base)
    new_cols = [c for c in other.columns if c not in base.columns]
    merged = base.merge(
        other[["name"] + new_cols],
        on="name",
        how="outer",
    )

    # Fill gaps in metadata columns
    for col in ["ottoneu_team", "salary"]:
        if col in other.columns and col in merged.columns:
            mask = merged[col].isna()
            if mask.any():
                fill_map = other.drop_duplicates("name").set_index("name")[col]
                merged.loc[mask, col] = merged.loc[mask, "name"].map(fill_map)

    return merged


def _merge_projections(df: pd.DataFrame, proj: pd.DataFrame) -> pd.DataFrame:
    """Outer-merge projection columns onto the main DataFrame."""
    if proj.empty:
        return df
    proj = proj.drop_duplicates(subset="name", keep="first")
    return df.merge(proj, on="name", how="outer")


def _merge_position_universe(df: pd.DataFrame, pos_df: pd.DataFrame) -> pd.DataFrame:
    """Outer-merge position CSV data onto the main DataFrame.

    Position CSV values are preferred for position, ottoneu_team, salary
    as they are the most authoritative source for current ownership.
    ownership_pct comes solely from the position CSV.
    """
    pos_df = pos_df.drop_duplicates(subset="name", keep="first")

    # Determine which columns need suffix-based resolution
    overlap_cols = [c for c in ["position", "ottoneu_team", "salary"] if c in df.columns and c in pos_df.columns]
    non_overlap = [c for c in pos_df.columns if c != "name" and c not in overlap_cols]

    merged = df.merge(
        pos_df,
        on="name",
        how="outer",
        suffixes=("", "_pos"),
    )

    # For overlapping columns, prefer position CSV values where available
    for col in overlap_cols:
        pos_col = f"{col}_pos"
        if pos_col in merged.columns:
            mask = merged[pos_col].notna()
            merged.loc[mask, col] = merged.loc[mask, pos_col]
            merged = merged.drop(columns=[pos_col])

    return merged


def _prune_irrelevant_players(df: pd.DataFrame, threshold: float = OWNERSHIP_PRUNE_THRESHOLD) -> pd.DataFrame:
    """Drop players with no projections, no historical stats, and low ownership.

    A player is pruned if ALL of:
    - proj_fpts is NaN (no projections)
    - fpts is NaN (no historical stats)
    - ownership_pct is NaN or <= threshold
    """
    if "ownership_pct" not in df.columns:
        return df

    no_proj = df.get("proj_fpts", pd.Series(dtype=float)).isna() if "proj_fpts" in df.columns else pd.Series(True, index=df.index)
    no_hist = df["fpts"].isna() if "fpts" in df.columns else pd.Series(True, index=df.index)
    low_own = df["ownership_pct"].isna() | (df["ownership_pct"] <= threshold)

    to_drop = no_proj & no_hist & low_own
    return df[~to_drop].reset_index(drop=True)


def merge_hitters(files: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge hitter files. Priority: fantasy > advanced > batted_ball."""
    df = _dedup(files["hitters_fantasy"].copy())
    df = _merge_pair(df, files["hitters_advanced"])
    df = _merge_pair(df, files["hitters_batted_ball"])

    # Merge projections if available (OUTER join)
    if "hitters_projections" in files:
        df = _merge_projections(df, files["hitters_projections"])

    # Merge position universe if available
    if "hitters_positions" in files:
        df = _merge_position_universe(df, files["hitters_positions"])

    # Prune irrelevant players
    df = _prune_irrelevant_players(df)

    # Initialize draft-state columns
    df["is_drafted"] = False
    df["draft_price"] = pd.NA
    if "position" not in df.columns:
        df["position"] = pd.NA
    if "ownership_pct" not in df.columns:
        df["ownership_pct"] = pd.NA
    df["dollar_value"] = pd.NA
    df["predicted_price"] = pd.NA
    df["surplus_value"] = pd.NA
    return df


def merge_pitchers(files: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge pitcher files. Priority: fantasy > advanced > batted_ball > modeling."""
    df = _dedup(files["pitchers_fantasy"].copy())
    df = _merge_pair(df, files["pitchers_advanced"])
    df = _merge_pair(df, files["pitchers_batted_ball"])
    df = _merge_pair(df, files["pitchers_modeling"])

    # Merge projections if available (OUTER join)
    if "pitchers_projections" in files:
        df = _merge_projections(df, files["pitchers_projections"])

    # Merge position universe if available
    if "pitchers_positions" in files:
        df = _merge_position_universe(df, files["pitchers_positions"])

    # Prune irrelevant players
    df = _prune_irrelevant_players(df)

    # Initialize draft-state columns
    df["is_drafted"] = False
    df["draft_price"] = pd.NA
    if "position" not in df.columns:
        df["position"] = pd.NA
    if "ownership_pct" not in df.columns:
        df["ownership_pct"] = pd.NA
    df["dollar_value"] = pd.NA
    df["predicted_price"] = pd.NA
    df["surplus_value"] = pd.NA
    return df
