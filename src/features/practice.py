"""Free Practice session feature extraction."""

import numpy as np
import pandas as pd

from src.data.storage import Storage

# Physics constants for fuel/tyre correction.
# F1 cars burn ~1.8 kg/lap of fuel; each kg = ~0.035 s/lap lap-time penalty.
# Net fuel burn effect: cars get ~0.063 s/lap faster each lap due to fuel
# burn alone. The raw polyfit slope (time ~ stint_lap) therefore contains
# TYRE_DEG + FUEL_EFFECT (negative), so to isolate tyre degradation we add
# the fuel term back.
FUEL_EFFECT_PER_LAP_SEC = 0.063
# Typical FP long-run stint length for intercept back-projection.
ASSUMED_STINT_LENGTH = 10


def extract_practice_features(storage: Storage, race_id: int,
                                driver_id: str,
                                sessions: list[str] = None,
                                team: str | None = None) -> dict:
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

        # Fuel/tyre-age corrected long-run pace.
        # The stored long_run_pace is the MEAN of stint lap times, which
        # mixes raw pace with fuel burn and tyre wear. Project back to
        # lap 0 of the stint: intercept = mean - slope * stint_len/2.
        # Then isolate true tyre deg: deg = slope + fuel_effect (fuel
        # makes the car faster over the stint, so we add it back).
        if pd.notna(row["long_run_pace"]) and pd.notna(row["long_run_degradation"]):
            slope = row["long_run_degradation"]
            intercept = row["long_run_pace"] - slope * (ASSUMED_STINT_LENGTH / 2.0)
            features[f"{sess.lower()}_long_run_intercept"] = intercept
            features[f"{sess.lower()}_tyre_deg_corrected"] = slope + FUEL_EFFECT_PER_LAP_SEC

            # Delta to field leader on the corrected intercept
            lr_pace = fp_data["long_run_pace"].dropna()
            lr_deg = fp_data["long_run_degradation"].dropna()
            if not lr_pace.empty and not lr_deg.empty:
                merged = fp_data[["long_run_pace", "long_run_degradation"]].dropna()
                if not merged.empty:
                    field_intercepts = (
                        merged["long_run_pace"]
                        - merged["long_run_degradation"] * (ASSUMED_STINT_LENGTH / 2.0)
                    )
                    leader_intercept = field_intercepts.min()
                    features[f"{sess.lower()}_long_run_intercept_delta"] = (
                        intercept - leader_intercept
                    )

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

    # Same-weekend teammate delta — strongest single predictor when FP data
    # is available, because it nulls out shared team/car effects.
    if team:
        features["teammate_fp_pace_delta"] = _teammate_fp_pace_delta(
            storage, race_id, driver_id, team, sessions
        )

    return features


def _teammate_fp_pace_delta(storage: Storage, race_id: int, driver_id: str,
                             team: str, sessions: list[str]) -> float:
    """Fuel-corrected long-run pace gap to teammate on the current weekend.

    Negative = faster than teammate, positive = slower. Defaults to 0 when
    teammate data is missing.
    """
    session_priority = ["FP3", "FP2", "FP1"]
    ordered = [s for s in session_priority if s in (sessions or session_priority)]

    for sess in ordered:
        fp_data = storage.get_fp_data(race_id, sess)
        if fp_data.empty:
            continue

        team_rows = fp_data[fp_data["team"] == team]
        if len(team_rows) < 2:
            continue

        # Corrected intercept per driver on this session
        def _intercept(row):
            pace = row["long_run_pace"]
            slope = row["long_run_degradation"]
            if pd.isna(pace) or pd.isna(slope):
                return None
            return pace - slope * (ASSUMED_STINT_LENGTH / 2.0)

        my_row = team_rows[team_rows["driver_id"] == driver_id]
        tm_row = team_rows[team_rows["driver_id"] != driver_id]
        if my_row.empty or tm_row.empty:
            continue

        my_int = _intercept(my_row.iloc[0])
        tm_int = _intercept(tm_row.iloc[0])
        if my_int is None or tm_int is None:
            continue

        return float(my_int - tm_int)

    return 0.0


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

    # Fuel-corrected long-run intercept (best across sessions — FP3 is most
    # representative of qualifying/race fuel). Prefer later sessions.
    session_priority = ["FP3", "FP2", "FP1"]
    for s in session_priority:
        key = f"{s.lower()}_long_run_intercept_delta"
        if key in features:
            features["fp_long_run_pace_fuel_corrected"] = features[key]
            break

    # Corrected tyre degradation (mean across sessions)
    corrected_degs = [
        features[f"{s.lower()}_tyre_deg_corrected"]
        for s in sessions
        if f"{s.lower()}_tyre_deg_corrected" in features
    ]
    if corrected_degs:
        features["fp_tyre_deg_corrected"] = np.mean(corrected_degs)
