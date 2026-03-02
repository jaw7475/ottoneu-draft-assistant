"""Projected FPTS → dollar value conversion."""

import pandas as pd


# Default league configuration
DEFAULT_CONFIG = {
    "num_teams": 12,
    "budget_per_team": 400,
    "hitter_budget_pct": 60,
    "hitters_per_team": 13,     # starting lineup: C×2, 1B, 2B, SS, 3B, MI, OF×5, Util
    "pitchers_per_team": 10,    # starting lineup: SP×5, RP×5
}


def calculate_dollar_values(
    hitters: pd.DataFrame,
    pitchers: pd.DataFrame,
    config: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate dollar values based on projected production.

    Uses a replacement-level methodology: the full league budget is
    distributed across all players based on marginal FPTS above
    replacement. Replacement level is set at the Nth-ranked player
    where N = num_teams × starters_per_team.

    Returns modified copies of hitters and pitchers DataFrames with
    dollar_value, predicted_price, and surplus_value columns populated.
    """
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    num_teams = int(cfg["num_teams"])
    budget_per_team = int(cfg["budget_per_team"])
    hitter_budget_pct = int(cfg["hitter_budget_pct"]) / 100

    total_budget = num_teams * budget_per_team
    h_budget = total_budget * hitter_budget_pct
    p_budget = total_budget * (1 - hitter_budget_pct)

    h_slots = num_teams * int(cfg["hitters_per_team"])
    p_slots = num_teams * int(cfg["pitchers_per_team"])

    hitters = _calc_values(hitters.copy(), h_slots, h_budget)
    pitchers = _calc_values(pitchers.copy(), p_slots, p_budget)

    return hitters, pitchers


def _calc_values(
    df: pd.DataFrame,
    roster_slots: int,
    available_budget: float,
) -> pd.DataFrame:
    """Calculate dollar values for a single player pool.

    Sets replacement level at the roster_slots-th ranked player,
    then distributes available_budget across all players with
    projections based on marginal FPTS above replacement.
    """
    if "proj_fpts" not in df.columns:
        df["dollar_value"] = pd.NA
        df["predicted_price"] = pd.NA
        df["surplus_value"] = pd.NA
        return df

    has_proj = df["proj_fpts"].notna()
    projected = df[has_proj].sort_values("proj_fpts", ascending=False)

    if len(projected) == 0:
        df["dollar_value"] = pd.NA
        df["predicted_price"] = pd.NA
        df["surplus_value"] = pd.NA
        return df

    # Replacement level = player at the roster cutoff rank
    if roster_slots <= len(projected):
        replacement_fpts = projected.iloc[roster_slots - 1]["proj_fpts"]
    else:
        replacement_fpts = projected.iloc[-1]["proj_fpts"]

    # Distribute budget across starter-tier players
    starters = projected.head(roster_slots)
    marginal = (starters["proj_fpts"] - replacement_fpts).clip(lower=0)
    total_marginal = marginal.sum()

    min_cost = 1 * len(starters)
    marginal_budget = max(0, available_budget - min_cost)

    if total_marginal > 0:
        dpp = marginal_budget / total_marginal
    else:
        dpp = 0

    # Above replacement: $1 + marginal × dpp
    df["_marginal_fpts"] = (df["proj_fpts"] - replacement_fpts).clip(lower=0)
    above_rep = has_proj & (df["proj_fpts"] > replacement_fpts)
    df.loc[above_rep, "dollar_value"] = (1 + df.loc[above_rep, "_marginal_fpts"] * dpp).round(0)

    # Below replacement with projections: proportional value
    at_or_below = has_proj & ~above_rep
    if replacement_fpts > 0:
        df.loc[at_or_below, "dollar_value"] = (
            df.loc[at_or_below, "proj_fpts"] / replacement_fpts
        ).clip(lower=0).round(0)
    else:
        df.loc[at_or_below, "dollar_value"] = 0

    # No projections = no value
    df.loc[~has_proj, "dollar_value"] = pd.NA

    # Default predicted_price = dollar_value, surplus = 0 (until model is trained)
    df["predicted_price"] = df["dollar_value"]
    df["surplus_value"] = 0
    df.loc[df["dollar_value"].isna(), "predicted_price"] = pd.NA
    df.loc[df["dollar_value"].isna(), "surplus_value"] = pd.NA

    df = df.drop(columns=["_marginal_fpts"])
    return df
