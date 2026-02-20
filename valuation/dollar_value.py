"""Replacement-level projected FPTS → dollar value conversion."""

import pandas as pd


# Default league configuration
DEFAULT_CONFIG = {
    "num_teams": 12,
    "budget_per_team": 400,
    "hitter_budget_pct": 65,
    "hitters_per_team": 20,
    "pitchers_per_team": 20,
}


def calculate_dollar_values(
    hitters: pd.DataFrame,
    pitchers: pd.DataFrame,
    config: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate dollar values from projected FPTS using replacement-level methodology.

    Returns modified copies of hitters and pitchers DataFrames with
    dollar_value, predicted_price, and surplus_value columns populated.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    num_teams = int(cfg["num_teams"])
    budget_per_team = int(cfg["budget_per_team"])
    hitter_budget_pct = int(cfg["hitter_budget_pct"]) / 100
    hitters_per_team = int(cfg["hitters_per_team"])
    pitchers_per_team = int(cfg["pitchers_per_team"])

    total_budget = num_teams * budget_per_team
    hitter_budget = total_budget * hitter_budget_pct
    pitcher_budget = total_budget * (1 - hitter_budget_pct)

    hitters = _calc_values(hitters, num_teams, hitters_per_team, hitter_budget)
    pitchers = _calc_values(pitchers, num_teams, pitchers_per_team, pitcher_budget)

    return hitters, pitchers


def _calc_values(
    df: pd.DataFrame,
    num_teams: int,
    players_per_team: int,
    available_budget: float,
) -> pd.DataFrame:
    """Calculate dollar values for a single player pool."""
    df = df.copy()

    if "proj_fpts" not in df.columns:
        df["dollar_value"] = pd.NA
        df["predicted_price"] = pd.NA
        df["surplus_value"] = pd.NA
        return df

    # Replacement level = rank at (num_teams × players_per_team)
    replacement_rank = num_teams * players_per_team
    sorted_fpts = df["proj_fpts"].dropna().sort_values(ascending=False)

    if len(sorted_fpts) == 0:
        df["dollar_value"] = pd.NA
        df["predicted_price"] = pd.NA
        df["surplus_value"] = pd.NA
        return df

    if replacement_rank <= len(sorted_fpts):
        replacement_fpts = sorted_fpts.iloc[replacement_rank - 1]
    else:
        replacement_fpts = sorted_fpts.iloc[-1]

    # Marginal FPTS above replacement
    df["_marginal_fpts"] = (df["proj_fpts"] - replacement_fpts).clip(lower=0)

    total_marginal = df["_marginal_fpts"].sum()

    if total_marginal > 0:
        dollar_per_marginal = available_budget / total_marginal
        df["dollar_value"] = (df["_marginal_fpts"] * dollar_per_marginal).round(0)
        # Minimum $1 for above-replacement, $0 for below
        df.loc[df["_marginal_fpts"] > 0, "dollar_value"] = df.loc[
            df["_marginal_fpts"] > 0, "dollar_value"
        ].clip(lower=1)
        df.loc[df["_marginal_fpts"] == 0, "dollar_value"] = 0
    else:
        df["dollar_value"] = 0

    # Handle players with no proj_fpts
    df.loc[df["proj_fpts"].isna(), "dollar_value"] = pd.NA

    # Default predicted_price = dollar_value, surplus = 0 (until model is trained)
    df["predicted_price"] = df["dollar_value"]
    df["surplus_value"] = 0
    df.loc[df["dollar_value"].isna(), "predicted_price"] = pd.NA
    df.loc[df["dollar_value"].isna(), "surplus_value"] = pd.NA

    df = df.drop(columns=["_marginal_fpts"])
    return df
