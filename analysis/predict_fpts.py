"""
FPTS Predictiveness Analysis

Joins 2024 stats (Excel) → 2025 FPTS (DB) to discover which prior-year stats
best predict next-year fantasy points, then applies insights to 2025 stats
to identify undervalued targets for the 2026 draft.
"""

import sys
import sqlite3
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.linear_model import Ridge
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from db.queries import save_model_targets

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXCEL_PATH = PROJECT_ROOT.parent / "2025 Stats.xlsx"
DB_PATH = PROJECT_ROOT / "draft.db"

# ---------------------------------------------------------------------------
# Column mappings: Excel name → internal name
# ---------------------------------------------------------------------------
HITTER_COL_MAP = {
    "Name": "name", "AVG": "avg", "OBP": "obp", "SLG": "slg", "OPS": "ops",
    "HR": "hr", "ISO": "iso", "wRC+": "wrc_plus", "xwOBA": "xwoba",
    "BB%": "bb_pct", "K%": "k_pct", "BABIP": "babip", "SB": "sb", "CS": "cs",
    "Barrel%": "barrel_pct", "HardHit%": "hard_hit_pct", "EV": "ev",
    "maxEV": "max_ev", "GB%": "gb_pct", "FB%": "fb_pct",
    "O-Swing%": "o_swing_pct", "Z-Swing%": "z_swing_pct",
    "O-Contact%": "o_contact_pct", "Z-Contact%": "z_contact_pct",
}

PITCHER_COL_MAP = {
    "Name": "name", "WHIP": "whip", "ERA": "era", "xERA": "xera",
    "xFIP": "xfip", "K/9": "k_per_9", "BB/9": "bb_per_9", "HR/9": "hr_per_9",
    "HR": "hr", "HR/FB": "hr_per_fb", "SV": "sv", "HLD": "hld",
    "Stuff+": "stuff_plus", "Location+": "location_plus",
    "Pitching+": "pitching_plus", "Barrel%": "barrel_pct",
    "HardHit%": "hard_hit_pct", "EV": "ev", "SwStr%": "swstr_pct",
    "Zone%": "zone_pct", "GB%": "gb_pct", "FB%": "fb_pct",
    "vFA (pi)": "vfa", "BABIP": "babip",
}

# Percentage columns that need ×100 to match DB scale
HITTER_PCT_COLS = [
    "bb_pct", "k_pct", "barrel_pct", "hard_hit_pct", "gb_pct", "fb_pct",
    "o_swing_pct", "z_swing_pct", "o_contact_pct", "z_contact_pct",
]
PITCHER_PCT_COLS = [
    "hr_per_fb", "barrel_pct", "hard_hit_pct", "swstr_pct", "zone_pct",
    "gb_pct", "fb_pct",
]

# Features for modeling (Excel-only cols excluded)
HITTER_FEATURES = [
    "avg", "obp", "slg", "ops", "hr", "iso", "wrc_plus", "xwoba",
    "bb_pct", "k_pct", "babip", "sb", "cs", "barrel_pct", "hard_hit_pct",
    "ev", "max_ev", "gb_pct", "fb_pct",
]
# Extra cols in Excel only — used for correlation but not prediction
HITTER_EXTRA_CORR = ["o_swing_pct", "z_swing_pct", "o_contact_pct", "z_contact_pct"]

PITCHER_FEATURES_SP = [
    "whip", "era", "xera", "xfip", "k_per_9", "bb_per_9", "hr_per_9",
    "hr_per_fb", "stuff_plus", "location_plus", "pitching_plus",
    "barrel_pct", "hard_hit_pct", "ev", "gb_pct", "fb_pct", "vfa", "babip",
]
PITCHER_FEATURES_RP = PITCHER_FEATURES_SP + ["sv", "hld"]
PITCHER_EXTRA_CORR = ["swstr_pct", "zone_pct"]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_excel_stats(path: Path):
    """Load 2024 stats from Excel, rename columns, scale percentages."""
    hitters = pd.read_excel(path, sheet_name="MLB Hitters")
    hitters = hitters.rename(columns=HITTER_COL_MAP)
    for col in HITTER_PCT_COLS:
        if col in hitters.columns:
            hitters[col] = hitters[col] * 100

    pitchers = pd.read_excel(path, sheet_name="MLB Pitchers")
    pitchers = pitchers.rename(columns=PITCHER_COL_MAP)
    for col in PITCHER_PCT_COLS:
        if col in pitchers.columns:
            pitchers[col] = pitchers[col] * 100

    # Drop rows that are all empty (like Ohtani's pitcher row)
    pitchers = pitchers.dropna(subset=["era", "whip"], how="all")
    hitters = hitters.dropna(subset=["avg", "obp"], how="all")

    # Coerce numeric
    for df in [hitters, pitchers]:
        for col in df.columns:
            if col != "name":
                df[col] = pd.to_numeric(df[col], errors="coerce")

    return hitters, pitchers


def load_db_data(db_path: Path):
    """Load 2025 stats from SQLite."""
    conn = sqlite3.connect(db_path)
    hitters = pd.read_sql("SELECT * FROM hitters", conn)
    pitchers = pd.read_sql("SELECT * FROM pitchers", conn)
    conn.close()

    # Compute fpts_per_ip for pitchers if not present
    if "fpts_per_ip" not in pitchers.columns:
        pitchers["fpts_per_ip"] = pitchers["fpts"] / pitchers["ip"]

    return hitters, pitchers


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------
def build_matched_set(excel_df, db_df, suffix_excel="_prev", suffix_db="_curr"):
    """Inner join on player name. Returns merged df with suffixed columns."""
    merged = excel_df.merge(db_df, on="name", suffixes=(suffix_excel, suffix_db))
    return merged


# ---------------------------------------------------------------------------
# Correlation analysis
# ---------------------------------------------------------------------------
def correlation_analysis(df, features, target):
    """Compute Pearson and Spearman correlations of prior-year features vs target."""
    results = []
    for feat in features:
        col = feat + "_prev" if feat + "_prev" in df.columns else feat
        if col not in df.columns:
            continue
        valid = df[[col, target]].dropna()
        if len(valid) < 20:
            continue
        pearson = valid[col].corr(valid[target])
        spearman = valid[col].corr(valid[target], method="spearman")
        results.append({
            "feature": feat,
            "pearson": round(pearson, 3),
            "spearman": round(spearman, 3),
            "abs_pearson": round(abs(pearson), 3),
            "n": len(valid),
        })
    results_df = pd.DataFrame(results).sort_values("abs_pearson", ascending=False)
    return results_df


# ---------------------------------------------------------------------------
# Model building
# ---------------------------------------------------------------------------
def build_model(df, features, target, alpha=1.0, max_features=8):
    """Build Ridge regression with 5-fold CV and automatic feature selection.

    Uses correlation-based feature selection: picks the top `max_features` by
    absolute Pearson correlation with target to avoid overfitting with many
    collinear features on small samples.
    """
    # Resolve column names (prefer _prev suffix for features from Excel)
    feat_map = {}  # internal name → actual column name
    for f in features:
        if f + "_prev" in df.columns:
            feat_map[f] = f + "_prev"
        elif f in df.columns:
            feat_map[f] = f
    if not feat_map:
        print("  WARNING: No features found in dataframe.")
        return None, None, None, [], []

    all_feat_cols = list(feat_map.values())
    subset = df[all_feat_cols + [target]].dropna()
    if len(subset) < 30:
        print(f"  WARNING: Only {len(subset)} samples after dropping NaN — too few.")
        return None, None, None, [], []

    # Feature selection: rank by |correlation| with target, take top N
    corrs = {}
    for fname, col in feat_map.items():
        corrs[fname] = abs(subset[col].corr(subset[target]))
    ranked = sorted(corrs.items(), key=lambda x: x[1], reverse=True)
    selected = [f for f, _ in ranked[:max_features]]
    selected_cols = [feat_map[f] for f in selected]

    print(f"  Selected {len(selected)} features (from {len(feat_map)} candidates):")
    print(f"    {', '.join(selected)}")

    X = subset[selected_cols].values
    y = subset[target].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Try multiple alpha values and pick the best
    best_r2 = -np.inf
    best_alpha = alpha
    for a in [0.1, 0.5, 1.0, 5.0, 10.0, 50.0]:
        m = Ridge(alpha=a)
        scores = cross_val_score(m, X_scaled, y, cv=5, scoring="r2")
        if np.mean(scores) > best_r2:
            best_r2 = np.mean(scores)
            best_alpha = a
    print(f"  Best alpha: {best_alpha} (CV R² = {best_r2:.3f})")

    model = Ridge(alpha=best_alpha)
    r2_scores = cross_val_score(model, X_scaled, y, cv=5, scoring="r2")
    mae_scores = -cross_val_score(model, X_scaled, y, cv=5, scoring="neg_mean_absolute_error")

    # Fit on full data for coefficients
    model.fit(X_scaled, y)

    # Feature importances (standardized coefficients)
    importances = sorted(
        zip(selected, model.coef_),
        key=lambda x: abs(x[1]),
        reverse=True,
    )

    metrics = {
        "r2_mean": round(np.mean(r2_scores), 3),
        "r2_std": round(np.std(r2_scores), 3),
        "mae_mean": round(np.mean(mae_scores), 3),
        "mae_std": round(np.std(mae_scores), 3),
        "n_samples": len(subset),
    }

    return model, scaler, metrics, importances, selected


# ---------------------------------------------------------------------------
# Prediction & target finding
# ---------------------------------------------------------------------------
def predict_targets(model, scaler, db_df, features, proj_fpts_col, proj_playing_time_col,
                    rate_col, player_type="hitter"):
    """Predict rate-based FPTS, scale by projected playing time, find edges."""
    feat_cols = [f for f in features if f in db_df.columns]
    if len(feat_cols) != len(features):
        missing = set(features) - set(feat_cols)
        print(f"  Warning: missing features in DB: {missing}")

    # Need proj_fpts and projected playing time
    needed = feat_cols + [proj_fpts_col, proj_playing_time_col, "name", "position",
                          "salary", "ottoneu_team", "ownership_pct"]
    # Only keep rows that have all features + projections
    subset = db_df[needed].dropna(subset=feat_cols + [proj_fpts_col, proj_playing_time_col])
    if len(subset) == 0:
        print("  No rows with complete data for prediction.")
        return pd.DataFrame()

    X = subset[feat_cols].values
    X_scaled = scaler.transform(X)
    pred_rate = model.predict(X_scaled)

    subset = subset.copy()
    subset["pred_rate"] = pred_rate
    subset["pred_fpts"] = pred_rate * subset[proj_playing_time_col]
    subset["proj_fpts"] = subset[proj_fpts_col]
    subset["edge"] = subset["pred_fpts"] - subset["proj_fpts"]

    # Include key info
    result = subset[["name", "position", "ottoneu_team", "salary", "ownership_pct",
                      "pred_rate", "pred_fpts", "proj_fpts", "edge"]].copy()
    result = result.sort_values("edge", ascending=False)
    return result


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
def print_section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_correlation_table(corr_df, top_n=25):
    print(f"\n{'Feature':<20} {'Pearson':>8} {'Spearman':>9} {'N':>5}")
    print("-" * 45)
    for _, row in corr_df.head(top_n).iterrows():
        print(f"{row['feature']:<20} {row['pearson']:>8.3f} {row['spearman']:>9.3f} {int(row['n']):>5}")


def print_importances(importances, top_n=15):
    print(f"\n{'Feature':<20} {'Coefficient':>12}")
    print("-" * 35)
    for feat, coef in importances[:top_n]:
        print(f"{feat:<20} {coef:>12.4f}")


def print_targets(targets_df, top_n=20, label=""):
    if targets_df.empty:
        print("  No targets found.")
        return
    print(f"\n{'Name':<25} {'Pos':<6} {'Team':<12} {'Sal':>5} {'Own%':>5} "
          f"{'Pred':>6} {'Proj':>6} {'Edge':>6}")
    print("-" * 80)
    for _, row in targets_df.head(top_n).iterrows():
        team = str(row['ottoneu_team'])[:10] if pd.notna(row['ottoneu_team']) else "FA"
        sal = f"{row['salary']:.0f}" if pd.notna(row['salary']) else "-"
        own = f"{row['ownership_pct']:.0f}" if pd.notna(row['ownership_pct']) else "-"
        print(f"{row['name']:<25} {str(row['position']):<6} {team:<12} {sal:>5} {own:>5} "
              f"{row['pred_fpts']:>6.0f} {row['proj_fpts']:>6.0f} {row['edge']:>+6.0f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Loading data...")
    excel_hitters, excel_pitchers = load_excel_stats(EXCEL_PATH)
    db_hitters, db_pitchers = load_db_data(DB_PATH)

    print(f"  Excel: {len(excel_hitters)} hitters, {len(excel_pitchers)} pitchers")
    print(f"  DB:    {len(db_hitters)} hitters, {len(db_pitchers)} pitchers")

    # -----------------------------------------------------------------------
    # HITTERS
    # -----------------------------------------------------------------------
    print_section("HITTERS ANALYSIS")

    # Filter DB hitters: PA >= 200
    db_h_filtered = db_hitters[db_hitters["pa"] >= 200].copy()
    print(f"  DB hitters with PA >= 200: {len(db_h_filtered)}")

    matched_h = build_matched_set(excel_hitters, db_h_filtered)
    print(f"  Matched hitters (Excel 2024 ↔ DB 2025): {len(matched_h)}")

    # Correlation analysis
    print_section("Hitter Correlations: Prior-Year Stats → 2025 FPTS/G")
    all_h_features = HITTER_FEATURES + HITTER_EXTRA_CORR
    h_corr = correlation_analysis(matched_h, all_h_features, "fpts_per_g")
    print_correlation_table(h_corr)

    # Model
    print_section("Hitter Model (Ridge Regression)")
    h_model, h_scaler, h_metrics, h_importances, h_selected = build_model(
        matched_h, HITTER_FEATURES, "fpts_per_g"
    )
    if h_metrics:
        print(f"  Samples: {h_metrics['n_samples']}")
        print(f"  5-Fold CV R²: {h_metrics['r2_mean']:.3f} ± {h_metrics['r2_std']:.3f}")
        print(f"  5-Fold CV MAE: {h_metrics['mae_mean']:.3f} ± {h_metrics['mae_std']:.3f}")
        print_section("Hitter Feature Importance")
        print_importances(h_importances)

        # Predictions on 2025 stats → 2026 targets
        print_section("Hitter Targets (Model Pred > Consensus Projection)")
        h_targets = predict_targets(
            h_model, h_scaler, db_hitters, h_selected,
            "proj_fpts", "proj_g", "fpts_per_g", "hitter"
        )
        print_targets(h_targets, top_n=20)

        # Also show free agent / cheap targets
        print_section("Hitter Targets — Free Agents / Salary ≤ $10")
        fa_targets = h_targets[
            (h_targets["ottoneu_team"].isna()) |
            (h_targets["ottoneu_team"] == "Free Agent") |
            (h_targets["salary"].fillna(0) <= 10)
        ]
        print_targets(fa_targets, top_n=20)

    # -----------------------------------------------------------------------
    # PITCHERS — STARTERS
    # -----------------------------------------------------------------------
    print_section("STARTING PITCHER ANALYSIS")

    db_sp = db_pitchers[(db_pitchers["ip"] >= 40) & (db_pitchers["gs"] > 5)].copy()
    print(f"  DB starters (IP >= 40, GS > 5): {len(db_sp)}")

    matched_sp = build_matched_set(excel_pitchers, db_sp)
    print(f"  Matched SPs: {len(matched_sp)}")

    # Correlation
    print_section("SP Correlations: Prior-Year Stats → 2025 FPTS/IP")
    all_sp_features = PITCHER_FEATURES_SP + PITCHER_EXTRA_CORR
    sp_corr = correlation_analysis(matched_sp, all_sp_features, "fpts_per_ip")
    print_correlation_table(sp_corr)

    # Model
    print_section("SP Model (Ridge Regression)")
    sp_model, sp_scaler, sp_metrics, sp_importances, sp_selected = build_model(
        matched_sp, PITCHER_FEATURES_SP, "fpts_per_ip"
    )
    if sp_metrics:
        print(f"  Samples: {sp_metrics['n_samples']}")
        print(f"  5-Fold CV R²: {sp_metrics['r2_mean']:.3f} ± {sp_metrics['r2_std']:.3f}")
        print(f"  5-Fold CV MAE: {sp_metrics['mae_mean']:.3f} ± {sp_metrics['mae_std']:.3f}")
        print_section("SP Feature Importance")
        print_importances(sp_importances)

        # SP targets — use starters from DB
        db_sp_all = db_pitchers[db_pitchers["proj_gs"].fillna(0) > 5].copy()
        print_section("SP Targets (Model Pred > Consensus Projection)")
        sp_targets = predict_targets(
            sp_model, sp_scaler, db_sp_all, sp_selected,
            "proj_fpts", "proj_ip", "fpts_per_ip", "pitcher"
        )
        print_targets(sp_targets, top_n=20)

        print_section("SP Targets — Free Agents / Salary ≤ $10")
        fa_sp = sp_targets[
            (sp_targets["ottoneu_team"].isna()) |
            (sp_targets["ottoneu_team"] == "Free Agent") |
            (sp_targets["salary"].fillna(0) <= 10)
        ]
        print_targets(fa_sp, top_n=20)

    # -----------------------------------------------------------------------
    # PITCHERS — RELIEVERS
    # -----------------------------------------------------------------------
    print_section("RELIEF PITCHER ANALYSIS")

    db_rp = db_pitchers[(db_pitchers["ip"] >= 40) & (db_pitchers["gs"] <= 5)].copy()
    print(f"  DB relievers (IP >= 40, GS <= 5): {len(db_rp)}")

    matched_rp = build_matched_set(excel_pitchers, db_rp)
    print(f"  Matched RPs: {len(matched_rp)}")

    # Correlation
    print_section("RP Correlations: Prior-Year Stats → 2025 FPTS/IP")
    all_rp_features = PITCHER_FEATURES_RP + PITCHER_EXTRA_CORR
    rp_corr = correlation_analysis(matched_rp, all_rp_features, "fpts_per_ip")
    print_correlation_table(rp_corr)

    # Model
    print_section("RP Model (Ridge Regression)")
    rp_model, rp_scaler, rp_metrics, rp_importances, rp_selected = build_model(
        matched_rp, PITCHER_FEATURES_RP, "fpts_per_ip"
    )
    if rp_metrics:
        print(f"  Samples: {rp_metrics['n_samples']}")
        print(f"  5-Fold CV R²: {rp_metrics['r2_mean']:.3f} ± {rp_metrics['r2_std']:.3f}")
        print(f"  5-Fold CV MAE: {rp_metrics['mae_mean']:.3f} ± {rp_metrics['mae_std']:.3f}")
        print_section("RP Feature Importance")
        print_importances(rp_importances)

        # RP targets
        db_rp_all = db_pitchers[db_pitchers["proj_gs"].fillna(0) <= 5].copy()
        # For RPs, use proj_ip for playing time
        print_section("RP Targets (Model Pred > Consensus Projection)")
        rp_targets = predict_targets(
            rp_model, rp_scaler, db_rp_all, rp_selected,
            "proj_fpts", "proj_ip", "fpts_per_ip", "pitcher"
        )
        print_targets(rp_targets, top_n=20)

        print_section("RP Targets — Free Agents / Salary ≤ $10")
        fa_rp = rp_targets[
            (rp_targets["ottoneu_team"].isna()) |
            (rp_targets["ottoneu_team"] == "Free Agent") |
            (rp_targets["salary"].fillna(0) <= 10)
        ]
        print_targets(fa_rp, top_n=20)

    # -----------------------------------------------------------------------
    # Save top model targets to DB for app highlighting
    # Top 40 hitters, top 20 SPs, top 20 RPs by edge
    # -----------------------------------------------------------------------
    all_targets = []
    if h_metrics and not h_targets.empty:
        top_h = h_targets[h_targets["edge"] > 0].head(40)
        for _, row in top_h.iterrows():
            all_targets.append({
                "player_name": row["name"],
                "player_type": "hitter",
                "pred_fpts": row["pred_fpts"],
                "proj_fpts": row["proj_fpts"],
                "edge": row["edge"],
            })
    if sp_metrics and not sp_targets.empty:
        top_sp = sp_targets[sp_targets["edge"] > 0].head(20)
        for _, row in top_sp.iterrows():
            all_targets.append({
                "player_name": row["name"],
                "player_type": "pitcher",
                "pred_fpts": row["pred_fpts"],
                "proj_fpts": row["proj_fpts"],
                "edge": row["edge"],
            })
    if rp_metrics and not rp_targets.empty:
        top_rp = rp_targets[rp_targets["edge"] > 0].head(20)
        for _, row in top_rp.iterrows():
            all_targets.append({
                "player_name": row["name"],
                "player_type": "pitcher",
                "pred_fpts": row["pred_fpts"],
                "proj_fpts": row["proj_fpts"],
                "edge": row["edge"],
            })

    saved = save_model_targets(all_targets)
    print(f"\nSaved {saved} model targets to DB.")
    print("Done.")


if __name__ == "__main__":
    main()
