"""DataFrame -> JSON serialization for dashboard API responses."""

import math
from typing import Any

import numpy as np
import pandas as pd

from src.features.builder import FEATURE_COLUMNS


def _clean(value: Any) -> Any:
    """Make a value JSON-safe (NaN/Inf -> None, numpy scalars -> native)."""
    if isinstance(value, (np.floating, float)):
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if value is pd.NA:
        return None
    return value


def _records(df: pd.DataFrame) -> list[dict]:
    cleaned = []
    for row in df.to_dict(orient="records"):
        cleaned.append({k: _clean(v) for k, v in row.items()})
    return cleaned


def serialize_prediction(df: pd.DataFrame) -> dict:
    """Convert a predict_race() DataFrame (+ attrs) into a JSON-ready dict."""
    if df.empty:
        return {
            "predictions": [],
            "feature_importance": [],
            "features_by_driver": {},
            "metadata": {},
        }

    first = df.iloc[0]
    metadata = {
        "race_name": first.get("race_name", ""),
        "year": int(first.get("year", 0)) if pd.notna(first.get("year")) else None,
        "round": int(first.get("round", 0)) if pd.notna(first.get("round")) else None,
        "sessions_used": first.get("sessions_used", ""),
        "confidence": first.get("confidence", ""),
    }

    importance_df = df.attrs.get("feature_importance")
    importance_records: list[dict] = []
    if isinstance(importance_df, pd.DataFrame) and not importance_df.empty:
        total = float(importance_df["importance"].sum()) or 1.0
        for _, row in importance_df.iterrows():
            importance_records.append({
                "feature": row["feature"],
                "importance": _clean(row["importance"]),
                "pct": round(float(row["importance"]) / total * 100, 2),
            })

    # Per-driver raw feature values (only the FEATURE_COLUMNS subset)
    features_by_driver: dict[str, dict] = {}
    features_df = df.attrs.get("features_df")
    if isinstance(features_df, pd.DataFrame) and not features_df.empty:
        cols_present = [c for c in FEATURE_COLUMNS if c in features_df.columns]
        for _, row in features_df.iterrows():
            driver_id = row.get("driver_id")
            if driver_id is None:
                continue
            features_by_driver[str(driver_id)] = {
                col: _clean(row[col]) for col in cols_present
            }

    # Per-driver SHAP top contributions (from xgboost TreeExplainer)
    shap_by_driver: dict[str, list[dict]] = {}
    raw_shap = df.attrs.get("shap_by_driver")
    if isinstance(raw_shap, dict):
        for driver_id, contribs in raw_shap.items():
            items: list[dict] = []
            for entry in contribs or []:
                # entry is either (feature, value) tuple or list
                try:
                    feat, value = entry
                except (TypeError, ValueError):
                    continue
                items.append({"feature": str(feat), "shap_value": _clean(value)})
            shap_by_driver[str(driver_id)] = items

    # Per-driver finish-position histogram from the Monte Carlo simulator.
    # simulated_positions is (n_sims, n_drivers). Collapse to per-driver
    # counts so the UI can render a distribution without shipping 100k floats.
    position_histograms: dict[str, list[int]] = {}
    sim_positions = df.attrs.get("simulated_positions")
    if sim_positions is not None and isinstance(sim_positions, np.ndarray) \
            and sim_positions.ndim == 2:
        n_drivers = sim_positions.shape[1]
        # df rows aren't guaranteed to share order with simulated_positions.
        # ensemble.py builds sim_positions using the pre-sort driver_ids list,
        # which is the same order as features_df. We use features_df to map.
        if isinstance(features_df, pd.DataFrame) \
                and "driver_id" in features_df.columns \
                and len(features_df) == n_drivers:
            driver_order = features_df["driver_id"].tolist()
            for idx, driver_id in enumerate(driver_order):
                col = sim_positions[:, idx]
                # positions are 1..n_drivers
                hist = np.bincount(col, minlength=n_drivers + 1)[1:].tolist()
                position_histograms[str(driver_id)] = [int(c) for c in hist]

    return {
        "predictions": _records(df),
        "feature_importance": importance_records,
        "features_by_driver": features_by_driver,
        "shap_by_driver": shap_by_driver,
        "position_histograms": position_histograms,
        "metadata": metadata,
    }


def serialize_races(races: list[dict]) -> list[dict]:
    """Normalize race rows into the minimal shape the UI needs."""
    out = []
    for r in races:
        out.append({
            "year": int(r.get("year", 0)),
            "round": int(r.get("round", 0)),
            "name": r.get("name", ""),
            "date": r.get("date", ""),
            "country": r.get("country", ""),
        })
    return out
