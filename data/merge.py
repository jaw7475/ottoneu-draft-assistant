"""Merge loaded DataFrames into unified hitters and pitchers tables."""

import pandas as pd


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


def merge_hitters(files: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge hitter files. Priority: fantasy > advanced > batted_ball."""
    df = _dedup(files["hitters_fantasy"].copy())
    df = _merge_pair(df, files["hitters_advanced"])
    df = _merge_pair(df, files["hitters_batted_ball"])

    df["is_drafted"] = False
    df["draft_price"] = pd.NA
    df["position"] = pd.NA
    return df


def merge_pitchers(files: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge pitcher files. Priority: fantasy > advanced > batted_ball > modeling."""
    df = _dedup(files["pitchers_fantasy"].copy())
    df = _merge_pair(df, files["pitchers_advanced"])
    df = _merge_pair(df, files["pitchers_batted_ball"])
    df = _merge_pair(df, files["pitchers_modeling"])

    df["is_drafted"] = False
    df["draft_price"] = pd.NA
    df["position"] = pd.NA
    return df
