"""Free Practice session feature extraction."""

import numpy as np
import pandas as pd

from src.data.storage import Storage


def extract_practice_features(storage: Storage, race_id: int,
                                driver_id: str,
                                sessions: list[str] = None) -> dict:
    """Extract all FP-derived features for a driver at a race.

    Args:
        storage: Database storage instance.
        race_id: Race ID to extract features for.
        driver_id: Driver abbreviation.
        sessions: List of FP sessions to use (e.g., ["FP1", "FP2", "FP3"]).
                  Defaults to all available.

    Returns:
        Dict of feature name -> value.
    """
    if sessions is None:
        sessions = ["FP1", "FP2", "FP3"]

    features = {}
    session_data = {}

    for sess in sessions:
        fp_data = storage.get_fp_data(race_id, sess)
        if fp_data.empty:
            continue

        driver_fp = fp_data[fp_data["driver_id"] == driver_id]
        if driver_fp.empty:
            continue

        session_data[sess] = driver_fp.iloc[0]

        # Get session leader time for delta calculations
        all_best = fp_data["best_lap_time"].dropna()
        leader_time = all_best.min() if not all_best.empty else None

        row = driver_fp.iloc[0]

        # Best lap delta
        if leader_time and pd.notna(row["best_lap_time"]):
            features[f"{sess.lower()}_best_lap_delta"] = row["best_lap_time"] - leader_time

        # Median lap delta
        all_median = fp_data["median_lap_time"].dropna()
        leader_median = all_median.min() if not all_median.empty else None
        if leader_median and pd.notna(row["median_lap_time"]):
            features[f"{sess.lower()}_median_lap_delta"] = row["median_lap_time"] - leader_median

        # Consistency
        if pd.notna(row["consistency_stddev"]):
            features[f"{sess.lower()}_consistency"] = row["consistency_stddev"]

        # Long run metrics
        if pd.notna(row["long_run_pace"]):
            all_lr = fp_data["long_run_pace"].dropna()
            lr_leader = all_lr.min() if not all_lr.empty else row["long_run_pace"]
            features[f"{sess.lower()}_long_run_delta"] = row["long_run_pace"] - lr_leader

        if pd.notna(row["long_run_degradation"]):
            features[f"{sess.lower()}_degradation"] = row["long_run_degradation"]

        # Short run pace
        if pd.notna(row["short_run_pace"]):
            all_sr = fp_data["short_run_pace"].dropna()
            sr_leader = all_sr.min() if not all_sr.empty else row["short_run_pace"]
            features[f"{sess.lower()}_short_run_delta"] = row["short_run_pace"] - sr_leader

        # Sector deltas
        for sector in [1, 2, 3]:
            col = f"sector{sector}_best"
            if pd.notna(row[col]):
                all_sector = fp_data[col].dropna()
                sect_leader = all_sector.min() if not all_sector.empty else row[col]
                features[f"{sess.lower()}_sector{sector}_delta"] = row[col] - sect_leader

        # Speed trap
        if pd.notna(row["speed_trap_max"]):
            features[f"{sess.lower()}_speed_trap"] = row["speed_trap_max"]

        # Lap count
        if pd.notna(row["lap_count"]):
            features[f"{sess.lower()}_lap_count"] = row["lap_count"]

        # Compound-specific pace
        for compound in ["soft", "medium", "hard"]:
            col = f"compound_{compound}_pace"
            if pd.notna(row[col]):
                all_comp = fp_data[col].dropna()
                comp_leader = all_comp.min() if not all_comp.empty else row[col]
                features[f"{sess.lower()}_{compound}_delta"] = row[col] - comp_leader

    # Cross-session features
    _add_cross_session_features(features, session_data)

    # Aggregate features (best across all sessions)
    _add_aggregate_features(features, sessions)

    return features


def _add_cross_session_features(features: dict,
                                 session_data: dict[str, pd.Series]):
    """Add features comparing across FP sessions."""
    # Improvement from FP1 to FP3 (setup convergence)
    if "FP1" in session_data and "FP3" in session_data:
        fp1 = session_data["FP1"]
        fp3 = session_data["FP3"]

        if pd.notna(fp1["best_lap_time"]) and pd.notna(fp3["best_lap_time"]):
            features["fp_improvement_fp1_to_fp3"] = fp1["best_lap_time"] - fp3["best_lap_time"]

    # Improvement FP1 to FP2
    if "FP1" in session_data and "FP2" in session_data:
        fp1 = session_data["FP1"]
        fp2 = session_data["FP2"]

        if pd.notna(fp1["best_lap_time"]) and pd.notna(fp2["best_lap_time"]):
            features["fp_improvement_fp1_to_fp2"] = fp1["best_lap_time"] - fp2["best_lap_time"]

    # Total laps across all sessions
    total_laps = 0
    for sess, row in session_data.items():
        if pd.notna(row["lap_count"]):
            total_laps += int(row["lap_count"])
    features["fp_total_laps"] = total_laps


def _add_aggregate_features(features: dict, sessions: list[str]):
    """Compute best-of aggregates across sessions."""
    # Best lap delta across all sessions
    best_deltas = [
        features[f"{s.lower()}_best_lap_delta"]
        for s in sessions
        if f"{s.lower()}_best_lap_delta" in features
    ]
    if best_deltas:
        features["fp_best_lap_delta"] = min(best_deltas)

    # Best long run delta
    lr_deltas = [
        features[f"{s.lower()}_long_run_delta"]
        for s in sessions
        if f"{s.lower()}_long_run_delta" in features
    ]
    if lr_deltas:
        features["fp_long_run_pace"] = min(lr_deltas)

    # Best short run delta
    sr_deltas = [
        features[f"{s.lower()}_short_run_delta"]
        for s in sessions
        if f"{s.lower()}_short_run_delta" in features
    ]
    if sr_deltas:
        features["fp_short_run_pace"] = min(sr_deltas)

    # Best consistency
    consistencies = [
        features[f"{s.lower()}_consistency"]
        for s in sessions
        if f"{s.lower()}_consistency" in features
    ]
    if consistencies:
        features["fp_consistency"] = min(consistencies)

    # Average degradation
    degs = [
        features[f"{s.lower()}_degradation"]
        for s in sessions
        if f"{s.lower()}_degradation" in features
    ]
    if degs:
        features["fp_long_run_degradation"] = np.mean(degs)

    # Max speed trap
    speeds = [
        features[f"{s.lower()}_speed_trap"]
        for s in sessions
        if f"{s.lower()}_speed_trap" in features
    ]
    if speeds:
        features["fp_speed_trap_max"] = max(speeds)
