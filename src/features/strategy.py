"""Strategy and tyre-related feature extraction."""

import numpy as np
import pandas as pd

from src.data.storage import Storage


def extract_strategy_features(storage: Storage, race_id: int,
                                driver_id: str,
                                sessions: list[str] = None) -> dict:
    """Extract strategy-related features from FP data.

    Args:
        storage: Database storage instance.
        race_id: Race ID.
        driver_id: Driver abbreviation.
        sessions: FP sessions to use.

    Returns:
        Dict of feature name -> value.
    """
    if sessions is None:
        sessions = ["FP1", "FP2", "FP3"]

    features = {}

    # Collect tyre degradation data from FP long runs
    all_degs = []
    compound_paces = {}

    for sess in sessions:
        fp_data = storage.get_fp_data(race_id, sess)
        if fp_data.empty:
            continue

        driver_fp = fp_data[fp_data["driver_id"] == driver_id]
        if driver_fp.empty:
            continue

        row = driver_fp.iloc[0]

        # Collect degradation
        if pd.notna(row.get("long_run_degradation")):
            all_degs.append(row["long_run_degradation"])

        # Collect compound paces
        for compound in ["soft", "medium", "hard"]:
            col = f"compound_{compound}_pace"
            if pd.notna(row.get(col)):
                compound_paces.setdefault(compound, []).append(row[col])

    # Tyre degradation relative to field
    field_degs = _get_field_degradation(storage, race_id, sessions)
    driver_avg_deg = np.mean(all_degs) if all_degs else 0.0
    field_avg_deg = np.mean(field_degs) if field_degs else 0.0

    features["tyre_deg_relative"] = driver_avg_deg - field_avg_deg

    # Expected pit stops (based on deg rate and compound gaps)
    features["expected_pit_stops"] = _estimate_pit_stops(
        driver_avg_deg, compound_paces
    )

    # Did the driver test the likely optimal strategy?
    features["optimal_compound_advantage"] = _check_compound_coverage(
        compound_paces
    )

    # Undercut potential (circuit-dependent, approximated)
    features["undercut_potential"] = _estimate_undercut_potential(
        storage, race_id, driver_avg_deg
    )

    # Starting compound prediction (based on FP data)
    features["starting_tyre_compound"] = _predict_starting_compound(
        compound_paces
    )

    return features


def _get_field_degradation(storage: Storage, race_id: int,
                            sessions: list[str]) -> list[float]:
    """Get all drivers' degradation values for comparison."""
    degs = []
    for sess in sessions:
        fp_data = storage.get_fp_data(race_id, sess)
        if fp_data.empty:
            continue

        for _, row in fp_data.iterrows():
            if pd.notna(row.get("long_run_degradation")):
                degs.append(row["long_run_degradation"])

    return degs


def _estimate_pit_stops(avg_degradation: float,
                         compound_paces: dict) -> float:
    """Estimate number of pit stops based on degradation data."""
    if avg_degradation <= 0:
        return 1.0  # Default 1-stop

    # Higher degradation = more stops
    # Typical: <0.05 s/lap = 1 stop, 0.05-0.10 = 1-2 stops, >0.10 = 2+ stops
    if avg_degradation < 0.03:
        return 1.0
    elif avg_degradation < 0.07:
        return 1.5
    elif avg_degradation < 0.12:
        return 2.0
    else:
        return 2.5


def _check_compound_coverage(compound_paces: dict) -> float:
    """Check if the driver tested enough compounds for strategy flexibility.

    Returns 1.0 if tested all 3 compounds, lower otherwise.
    """
    tested = len(compound_paces)
    if tested >= 3:
        return 1.0
    elif tested == 2:
        return 0.6
    elif tested == 1:
        return 0.3
    return 0.0


def _estimate_undercut_potential(storage: Storage, race_id: int,
                                  driver_deg: float) -> float:
    """Estimate undercut effectiveness.

    Based on tyre degradation and circuit characteristics.
    Higher deg = stronger undercut potential.
    """
    # Base on degradation
    if driver_deg <= 0:
        return 0.5

    # Higher deg circuits have stronger undercuts
    return min(1.0, driver_deg * 10)


def _predict_starting_compound(compound_paces: dict) -> int:
    """Predict starting tyre compound.

    Returns encoded value: 0=soft, 1=medium, 2=hard.
    Most F1 races start on medium in modern era.
    """
    # If we have pace data, the compound with best pace on longer runs
    # is likely the starting compound
    if "medium" in compound_paces:
        return 1  # Medium most common start
    elif "soft" in compound_paces:
        return 0
    elif "hard" in compound_paces:
        return 2
    return 1  # Default medium
