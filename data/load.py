"""Load and clean source CSV/XLSX files."""

import re
import unicodedata
from pathlib import Path

import pandas as pd

# Parent directory where source files live
DATA_DIR = Path(__file__).resolve().parent.parent.parent

# Column rename mapping: original name → SQL-friendly name
COLUMN_RENAMES = {
    "#": "rank",
    "Name": "name",
    "Fantasy": "ottoneu_team",
    "$": "salary",
    # Hitter advanced
    "PA": "pa",
    "BB%": "bb_pct",
    "K%": "k_pct",
    "BB/K": "bb_per_k",
    "AVG": "avg",
    "OBP": "obp",
    "SLG": "slg",
    "OPS": "ops",
    "ISO": "iso",
    "BABIP": "babip",
    "wOBA": "woba",
    "wRC+": "wrc_plus",
    # Hitter batted ball
    "GB/FB": "gb_per_fb",
    "LD%": "ld_pct",
    "GB%": "gb_pct",
    "FB%": "fb_pct",
    "IFFB%": "iffb_pct",
    "HR/FB": "hr_per_fb",
    "IFH": "ifh",
    "IFH%": "ifh_pct",
    "BUH": "buh",
    "BUH%": "buh_pct",
    "Pull%": "pull_pct",
    "Cent%": "cent_pct",
    "Oppo%": "oppo_pct",
    "Soft%": "soft_pct",
    "Med%": "med_pct",
    "Hard%": "hard_pct",
    # Hitter fantasy
    "AB": "ab",
    "H": "h",
    "2B": "doubles",
    "3B": "triples",
    "HR": "hr",
    "BB": "bb",
    "HBP": "hbp",
    "SB": "sb",
    "CS": "cs",
    "FPTS/G": "fpts_per_g",
    "FPTS": "fpts",
    # Pitcher fantasy
    "IP": "ip",
    "SO": "so",
    "SV": "sv",
    "K/9": "k_per_9",
    "HLD": "hld",
    "FPTS/IP": "fpts_per_ip",
    # Pitcher advanced
    "W": "w",
    "L": "l",
    "G": "g",
    "GS": "gs",
    "BB/9": "bb_per_9",
    "HR/9": "hr_per_9",
    "LOB%": "lob_pct",
    "vFA (pi)": "vfa",
    "ERA": "era",
    "xERA": "xera",
    "FIP": "fip",
    "xFIP": "xfip",
    "WAR": "war",
    # Pitcher batted ball
    "Events": "events",
    "EV": "ev",
    "EV90": "ev90",
    "maxEV": "max_ev",
    "LA": "la",
    "Barrels": "barrels",
    "Barrel%": "barrel_pct",
    "HardHit": "hard_hit",
    "HardHit%": "hard_hit_pct",
    # Pitcher modeling
    "Stuff+": "stuff_plus",
    "Location+": "location_plus",
    "Pitching+": "pitching_plus",
}

# Columns that contain percentage strings (with % sign)
PCT_COLUMNS = {
    "BB%", "K%", "LOB%", "GB%", "FB%", "HR/FB", "LD%", "IFFB%",
    "IFH%", "BUH%", "Pull%", "Cent%", "Oppo%", "Soft%", "Med%", "Hard%",
    "Barrel%", "HardHit%",
}


def normalize_name(name: str) -> str:
    """Normalize a player name for consistent joins across data sources."""
    if not isinstance(name, str):
        return name
    # Strip whitespace
    name = name.strip()
    # Remove accent marks (é → e, ñ → n, etc.)
    name = "".join(
        c for c in unicodedata.normalize("NFD", name)
        if unicodedata.category(c) != "Mn"
    )
    # Remove periods (J.D. → JD)
    name = name.replace(".", "")
    # Remove common suffixes
    name = re.sub(r",?\s+(?:Jr|Sr|II|III|IV)\.?$", "", name)
    # Collapse multiple spaces
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _is_xlsx(path: Path) -> bool:
    """Check if a file is actually XLSX by reading magic bytes."""
    with open(path, "rb") as f:
        return f.read(4) == b"PK\x03\x04"


def _parse_salary(val):
    """Parse salary column: strip '$' and whitespace → nullable int."""
    if pd.isna(val):
        return pd.NA
    s = str(val).strip().lstrip("$").strip()
    if s == "":
        return pd.NA
    try:
        return int(s)
    except ValueError:
        return pd.NA


def _parse_pct(val):
    """Parse percentage string: strip '%' → float."""
    if pd.isna(val):
        return pd.NA
    s = str(val).strip().rstrip("%").strip()
    if s == "":
        return pd.NA
    try:
        return float(s)
    except ValueError:
        return pd.NA


def load_file(filename: str) -> pd.DataFrame:
    """Load a single source file, clean it, and return a DataFrame."""
    path = DATA_DIR / filename

    # Detect XLSX masquerading as CSV
    if _is_xlsx(path):
        df = pd.read_excel(path, engine="openpyxl")
    else:
        df = pd.read_csv(path, encoding="utf-8-sig")

    # Drop trailing empty rows (where Name is NaN)
    if "Name" in df.columns:
        df = df.dropna(subset=["Name"])

    # Drop trailing unnamed empty columns
    unnamed_cols = [c for c in df.columns if str(c).startswith("Unnamed")]
    if unnamed_cols:
        df = df.drop(columns=unnamed_cols)

    # Parse salary column
    if "$" in df.columns:
        df["$"] = df["$"].apply(_parse_salary)

    # Parse percentage columns
    for col in df.columns:
        if col in PCT_COLUMNS:
            df[col] = df[col].apply(_parse_pct)

    # Drop the rank column — not meaningful after merge
    if "#" in df.columns:
        df = df.drop(columns=["#"])

    # Rename columns to SQL-friendly names
    rename_map = {c: COLUMN_RENAMES[c] for c in df.columns if c in COLUMN_RENAMES}
    df = df.rename(columns=rename_map)

    # Normalize player names for consistent joins
    if "name" in df.columns:
        df["name"] = df["name"].apply(normalize_name)

    # Coerce numeric columns that may have pd.NA keeping them as object dtype
    for col in df.columns:
        if col not in ("name", "ottoneu_team", "position"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def load_projections(filename: str) -> pd.DataFrame:
    """Load a projection CSV and prefix stat columns with 'proj_'."""
    path = DATA_DIR / filename
    if not path.exists():
        return pd.DataFrame()

    if _is_xlsx(path):
        df = pd.read_excel(path, engine="openpyxl")
    else:
        df = pd.read_csv(path, encoding="utf-8-sig")

    if "Name" in df.columns:
        df = df.dropna(subset=["Name"])

    unnamed_cols = [c for c in df.columns if str(c).startswith("Unnamed")]
    if unnamed_cols:
        df = df.drop(columns=unnamed_cols)

    if "$" in df.columns:
        df["$"] = df["$"].apply(_parse_salary)

    for col in df.columns:
        if col in PCT_COLUMNS:
            df[col] = df[col].apply(_parse_pct)

    if "#" in df.columns:
        df = df.drop(columns=["#"])

    # Rename using standard mapping
    rename_map = {c: COLUMN_RENAMES[c] for c in df.columns if c in COLUMN_RENAMES}
    df = df.rename(columns=rename_map)

    # Normalize player names for consistent joins
    if "name" in df.columns:
        df["name"] = df["name"].apply(normalize_name)

    # Coerce numeric columns
    for col in df.columns:
        if col not in ("name", "ottoneu_team", "position"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Prefix all stat columns with 'proj_' (keep 'name' as join key)
    proj_rename = {c: f"proj_{c}" for c in df.columns if c != "name"}
    df = df.rename(columns=proj_rename)

    return df


def load_expert_rankings():
    """Load expert rankings from Excel and return (hitter_rankings, pitcher_rankings).

    Each DataFrame has columns: name, expert1_rank, expert1_tier, expert2_rank, expert2_tier.
    When a player appears in multiple position tabs, the best (lowest) rank is kept.
    """
    path = DATA_DIR / "expert_rankings.xlsx"
    if not path.exists():
        return pd.DataFrame(), pd.DataFrame()

    HITTER_TABS_E1 = ["C", "1B", "MI", "3B", "OF"]
    HITTER_TABS_E2 = ["C 2", "1B 2", "MI 2", "3B 2", "OF 2"]
    PITCHER_TABS_E1 = ["SP", "RP"]
    PITCHER_TABS_E2 = ["SP 2", "RP 2"]

    def _read_tabs(tabs):
        """Read and concat rankings from a list of sheet tabs."""
        frames = []
        for tab in tabs:
            try:
                df = pd.read_excel(path, sheet_name=tab, engine="openpyxl")
            except (ValueError, KeyError):
                continue
            # Keep only Tier, Rank, Player columns
            if "Player" not in df.columns:
                continue
            cols = [c for c in ["Tier", "Rank", "Player"] if c in df.columns]
            df = df[cols].dropna(subset=["Player"])
            df = df.rename(columns={"Player": "name"})
            df["name"] = df["name"].apply(normalize_name)
            if "Rank" in df.columns:
                df["Rank"] = pd.to_numeric(df["Rank"], errors="coerce")
            if "Tier" in df.columns:
                df["Tier"] = pd.to_numeric(df["Tier"], errors="coerce")
            frames.append(df)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    def _best_rank(df, rank_col, tier_col):
        """Keep the best (lowest) rank per player, with associated tier."""
        if df.empty or "Rank" not in df.columns:
            return pd.DataFrame(columns=["name", rank_col, tier_col])
        df = df.dropna(subset=["Rank"])
        best = df.loc[df.groupby("name")["Rank"].idxmin()][["name", "Rank", "Tier"]].copy()
        best = best.rename(columns={"Rank": rank_col, "Tier": tier_col})
        return best.reset_index(drop=True)

    # Hitters
    h_e1 = _best_rank(_read_tabs(HITTER_TABS_E1), "expert1_rank", "expert1_tier")
    h_e2 = _best_rank(_read_tabs(HITTER_TABS_E2), "expert2_rank", "expert2_tier")
    if h_e1.empty and h_e2.empty:
        hitter_rankings = pd.DataFrame()
    elif h_e1.empty:
        hitter_rankings = h_e2
    elif h_e2.empty:
        hitter_rankings = h_e1
    else:
        hitter_rankings = h_e1.merge(h_e2, on="name", how="outer")

    # Pitchers
    p_e1 = _best_rank(_read_tabs(PITCHER_TABS_E1), "expert1_rank", "expert1_tier")
    p_e2 = _best_rank(_read_tabs(PITCHER_TABS_E2), "expert2_rank", "expert2_tier")
    if p_e1.empty and p_e2.empty:
        pitcher_rankings = pd.DataFrame()
    elif p_e1.empty:
        pitcher_rankings = p_e2
    elif p_e2.empty:
        pitcher_rankings = p_e1
    else:
        pitcher_rankings = p_e1.merge(p_e2, on="name", how="outer")

    return hitter_rankings, pitcher_rankings


def load_all():
    """Load all source files and return them as a dict."""
    result = {
        "hitters_advanced": load_file("hitters_advanced.csv"),
        "hitters_batted_ball": load_file("hitters_batted_ball.csv"),
        "hitters_fantasy": load_file("hitters_fantasy.csv"),
        "pitchers_advanced": load_file("pitchers_advanced.csv"),
        "pitchers_batted_ball": load_file("pitchers_batted_ball.csv"),
        "pitchers_fantasy": load_file("pitchers_fantasy.csv"),
        "pitchers_modeling": load_file("pitchers_modeling.csv"),
    }

    # Load projection files if they exist
    hitter_proj = load_projections("proj_hitters.csv")
    pitcher_proj = load_projections("proj_pitchers.csv")
    if not hitter_proj.empty:
        result["hitters_projections"] = hitter_proj
    if not pitcher_proj.empty:
        result["pitchers_projections"] = pitcher_proj

    # Load position CSVs if they exist
    from data.positions import load_position_universe

    hitter_pos = DATA_DIR / "hitter_positions.csv"
    pitcher_pos = DATA_DIR / "pitcher_positions.csv"
    if hitter_pos.exists():
        result["hitters_positions"] = load_position_universe(hitter_pos)
    if pitcher_pos.exists():
        result["pitchers_positions"] = load_position_universe(pitcher_pos)

    # Load expert rankings if available
    hitter_rankings, pitcher_rankings = load_expert_rankings()
    if not hitter_rankings.empty:
        result["hitters_expert_rankings"] = hitter_rankings
    if not pitcher_rankings.empty:
        result["pitchers_expert_rankings"] = pitcher_rankings

    return result
