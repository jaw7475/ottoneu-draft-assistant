"""Ridge regression model for FA auction price prediction."""

from pathlib import Path

import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
import joblib

from data.load import normalize_name
from db.connection import get_connection
from valuation.surplus import update_surplus_values

MODEL_DIR = Path(__file__).resolve().parent / "models"

HITTER_FEATURES = ["proj_fpts", "proj_wrc_plus", "proj_hr", "proj_sb", "proj_ops"]
PITCHER_FEATURES = ["proj_fpts", "proj_ip", "proj_era", "proj_k_per_9", "is_closer"]


def _derive_pitcher_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute derived pitcher features like proj_k_per_9."""
    df = df.copy()
    if "proj_so" in df.columns and "proj_ip" in df.columns:
        ip = df["proj_ip"].fillna(0)
        df["proj_k_per_9"] = ((df["proj_so"].fillna(0) / ip) * 9).where(ip > 0, 0)
    elif "proj_k_per_9" not in df.columns:
        df["proj_k_per_9"] = 0
    return df


def train_and_predict() -> dict:
    """Train Ridge regression on draft data, write predictions to DB.

    Returns dict with r2, matched_count, feature_weights.
    """
    conn = get_connection()

    hist = pd.read_sql("SELECT * FROM historical_prices WHERE price IS NOT NULL", conn)
    hitters = pd.read_sql("SELECT * FROM hitters", conn)
    pitchers = pd.read_sql("SELECT * FROM pitchers", conn)

    if hist.empty:
        conn.close()
        raise ValueError("No draft data available. Place draft_results.csv in the data directory.")

    # Derive pitcher features
    pitchers = _derive_pitcher_features(pitchers)

    # Add is_closer feature for pitchers
    if "proj_sv" in pitchers.columns:
        pitchers["is_closer"] = (pitchers["proj_sv"].fillna(0) > 10).astype(int)
    else:
        pitchers["is_closer"] = 0

    # Match historical players to current projections
    h_matched = _match_players(hist, hitters, HITTER_FEATURES)
    p_matched = _match_players(hist, pitchers, PITCHER_FEATURES)

    all_features = []
    all_prices = []

    if not h_matched.empty:
        feats = h_matched[[f for f in HITTER_FEATURES if f in h_matched.columns]].copy()
        # Pad missing feature columns with 0
        for f in HITTER_FEATURES:
            if f not in feats.columns:
                feats[f] = 0
        feats = feats[HITTER_FEATURES]
        all_features.append(feats)
        all_prices.append(h_matched["hist_price"])

    if not p_matched.empty:
        feats = p_matched[[f for f in PITCHER_FEATURES if f in p_matched.columns]].copy()
        for f in PITCHER_FEATURES:
            if f not in feats.columns:
                feats[f] = 0
        feats = feats[PITCHER_FEATURES]
        all_features.append(feats)
        all_prices.append(p_matched["hist_price"])

    if not all_features:
        conn.close()
        raise ValueError("No players matched between historical data and current projections.")

    # Use a unified feature set (union of hitter + pitcher features)
    all_feature_names = list(dict.fromkeys(HITTER_FEATURES + PITCHER_FEATURES))

    X_parts = []
    for feat_df in all_features:
        expanded = pd.DataFrame(0.0, index=feat_df.index, columns=all_feature_names)
        for col in feat_df.columns:
            expanded[col] = feat_df[col].values
        X_parts.append(expanded)

    X = pd.concat(X_parts, ignore_index=True)
    y = pd.concat(all_prices, ignore_index=True)

    # Drop rows with NaN features
    mask = X.notna().all(axis=1) & y.notna()
    X = X[mask].reset_index(drop=True)
    y = y[mask].reset_index(drop=True)

    if len(X) < 10:
        conn.close()
        raise ValueError(f"Only {len(X)} valid training samples. Need at least 10.")

    # Train: StandardScaler → Ridge
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = Ridge(alpha=1.0)
    model.fit(X_scaled, y)

    r2 = model.score(X_scaled, y)

    # Save model artifacts
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(scaler, MODEL_DIR / "scaler.joblib")
    joblib.dump(model, MODEL_DIR / "ridge_model.joblib")
    joblib.dump(all_feature_names, MODEL_DIR / "feature_names.joblib")

    # Predict for all current players
    _predict_table(conn, hitters, "hitters", scaler, model, all_feature_names)
    _predict_table(conn, pitchers, "pitchers", scaler, model, all_feature_names)

    # Update surplus
    update_surplus_values()

    feature_weights = dict(zip(all_feature_names, model.coef_))
    matched_count = len(X)

    conn.close()

    return {
        "r2": r2,
        "matched_count": matched_count,
        "feature_weights": feature_weights,
    }


def _match_players(
    hist: pd.DataFrame,
    players: pd.DataFrame,
    features: list[str],
) -> pd.DataFrame:
    """Match historical auction players to current player projections by name."""
    if players.empty or hist.empty:
        return pd.DataFrame()

    # Normalize names for matching
    hist_copy = hist.copy()
    players_copy = players.copy()
    hist_copy["_match_name"] = hist_copy["player_name"].apply(normalize_name).str.lower()
    players_copy["_match_name"] = players_copy["name"].apply(normalize_name).str.lower()

    # Use most recent season price per player
    hist_copy = hist_copy.sort_values("season", ascending=False).drop_duplicates("_match_name")

    merged = players_copy.merge(
        hist_copy[["_match_name", "price"]],
        on="_match_name",
        how="inner",
    )
    merged = merged.rename(columns={"price": "hist_price"})

    # Only keep rows with at least some projection data
    available = [f for f in features if f in merged.columns]
    if not available:
        return pd.DataFrame()

    return merged


def _predict_table(
    conn,
    players: pd.DataFrame,
    table: str,
    scaler: StandardScaler,
    model: Ridge,
    feature_names: list[str],
) -> None:
    """Write predicted prices for a player table."""
    if players.empty:
        return

    df = players.copy()

    # Derive features and add is_closer for pitchers
    if table == "pitchers":
        df = _derive_pitcher_features(df)
        if "proj_sv" in df.columns:
            df["is_closer"] = (df["proj_sv"].fillna(0) > 10).astype(int)
        else:
            df["is_closer"] = 0

    # Build feature matrix
    X = pd.DataFrame(0.0, index=df.index, columns=feature_names)
    for col in feature_names:
        if col in df.columns:
            X[col] = df[col].fillna(0)

    # Only predict for players with proj_fpts
    has_proj = df["proj_fpts"].notna() if "proj_fpts" in df.columns else pd.Series(False, index=df.index)

    if has_proj.any():
        X_pred = X[has_proj]
        X_scaled = scaler.transform(X_pred)
        predictions = model.predict(X_scaled)
        # Ensure non-negative, round to int
        predictions = predictions.clip(min=0).round(0).astype(int)

        # Write predictions back to DB
        names = df.loc[has_proj, "name"].tolist()
        for name, pred in zip(names, predictions):
            conn.execute(
                f"UPDATE {table} SET predicted_price = ? WHERE name = ?",
                (int(pred), name),
            )

    conn.commit()
