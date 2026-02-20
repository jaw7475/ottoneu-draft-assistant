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


def _merge_projections(df: pd.DataFrame, proj: pd.DataFrame) -> pd.DataFrame:
    """Left-merge projection columns onto the main DataFrame."""
    if proj.empty:
        return df
    proj = proj.drop_duplicates(subset="name", keep="first")
    return df.merge(proj, on="name", how="left")


def merge_hitters(files: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Merge hitter files. Priority: fantasy > advanced > batted_ball."""
    df = _dedup(files["hitters_fantasy"].copy())
    df = _merge_pair(df, files["hitters_advanced"])
    df = _merge_pair(df, files["hitters_batted_ball"])

    # Merge projections if available
    if "hitters_projections" in files:
        df = _merge_projections(df, files["hitters_projections"])

    df["is_drafted"] = False
    df["draft_price"] = pd.NA
    df["position"] = pd.NA
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

    # Merge projections if available
    if "pitchers_projections" in files:
        df = _merge_projections(df, files["pitchers_projections"])

    df["is_drafted"] = False
    df["draft_price"] = pd.NA
    df["position"] = pd.NA
    df["dollar_value"] = pd.NA
    df["predicted_price"] = pd.NA
    df["surplus_value"] = pd.NA
    return df
