"""Circuit characteristic features."""

import numpy as np
import pandas as pd

from src.data.storage import Storage

# Circuit metadata that's not available from APIs
# This supplements API data with domain knowledge
CIRCUIT_METADATA = {
    "bahrain": {"type": "technical", "corners": 15, "drs_zones": 3, "altitude": 7, "tyre_stress": "high", "power_sensitivity": 0.5},
    "jeddah": {"type": "street", "corners": 27, "drs_zones": 3, "altitude": 15, "tyre_stress": "medium", "power_sensitivity": 0.7},
    "albert_park": {"type": "hybrid", "corners": 14, "drs_zones": 4, "altitude": 2, "tyre_stress": "medium", "power_sensitivity": 0.5},
    "suzuka": {"type": "technical", "corners": 18, "drs_zones": 2, "altitude": 55, "tyre_stress": "high", "power_sensitivity": 0.4},
    "shanghai": {"type": "technical", "corners": 16, "drs_zones": 2, "altitude": 5, "tyre_stress": "high", "power_sensitivity": 0.5},
    "miami": {"type": "street", "corners": 19, "drs_zones": 3, "altitude": 2, "tyre_stress": "medium", "power_sensitivity": 0.5},
    "imola": {"type": "technical", "corners": 19, "drs_zones": 2, "altitude": 37, "tyre_stress": "medium", "power_sensitivity": 0.4},
    "monaco": {"type": "street", "corners": 19, "drs_zones": 1, "altitude": 30, "tyre_stress": "low", "power_sensitivity": 0.1},
    "villeneuve": {"type": "hybrid", "corners": 14, "drs_zones": 2, "altitude": 13, "tyre_stress": "medium", "power_sensitivity": 0.6},
    "catalunya": {"type": "technical", "corners": 16, "drs_zones": 2, "altitude": 109, "tyre_stress": "high", "power_sensitivity": 0.5},
    "red_bull_ring": {"type": "high_speed", "corners": 10, "drs_zones": 3, "altitude": 677, "tyre_stress": "high", "power_sensitivity": 0.7},
    "silverstone": {"type": "high_speed", "corners": 18, "drs_zones": 2, "altitude": 153, "tyre_stress": "high", "power_sensitivity": 0.5},
    "hungaroring": {"type": "technical", "corners": 14, "drs_zones": 2, "altitude": 264, "tyre_stress": "medium", "power_sensitivity": 0.3},
    "spa": {"type": "high_speed", "corners": 19, "drs_zones": 2, "altitude": 401, "tyre_stress": "high", "power_sensitivity": 0.6},
    "zandvoort": {"type": "technical", "corners": 14, "drs_zones": 2, "altitude": 0, "tyre_stress": "high", "power_sensitivity": 0.3},
    "monza": {"type": "high_speed", "corners": 11, "drs_zones": 2, "altitude": 162, "tyre_stress": "low", "power_sensitivity": 0.9},
    "baku": {"type": "street", "corners": 20, "drs_zones": 2, "altitude": -28, "tyre_stress": "medium", "power_sensitivity": 0.7},
    "marina_bay": {"type": "street", "corners": 23, "drs_zones": 3, "altitude": 5, "tyre_stress": "high", "power_sensitivity": 0.2},
    "americas": {"type": "technical", "corners": 20, "drs_zones": 2, "altitude": 253, "tyre_stress": "high", "power_sensitivity": 0.5},
    "rodriguez": {"type": "high_speed", "corners": 17, "drs_zones": 3, "altitude": 2238, "tyre_stress": "low", "power_sensitivity": 0.7},
    "interlagos": {"type": "technical", "corners": 15, "drs_zones": 2, "altitude": 761, "tyre_stress": "high", "power_sensitivity": 0.5},
    "las_vegas": {"type": "street", "corners": 17, "drs_zones": 2, "altitude": 610, "tyre_stress": "medium", "power_sensitivity": 0.8},
    "losail": {"type": "technical", "corners": 16, "drs_zones": 2, "altitude": 8, "tyre_stress": "high", "power_sensitivity": 0.5},
    "yas_marina": {"type": "hybrid", "corners": 16, "drs_zones": 2, "altitude": 5, "tyre_stress": "medium", "power_sensitivity": 0.5},
}

# Circuit type encoding
CIRCUIT_TYPE_MAP = {"street": 0, "technical": 1, "high_speed": 2, "hybrid": 3}


def extract_circuit_features(storage: Storage, circuit_id: str,
                               race_id: int = None,
                               as_of_date: str | None = None) -> dict:
    """Extract circuit-level features.

    Args:
        storage: Database storage instance.
        circuit_id: Circuit identifier.
        race_id: Optional race ID for historical stats.
        as_of_date: ISO cutoff for historical overtaking/SC computations.

    Returns:
        Dict of feature name -> value.
    """
    features = {}

    # Try database first
    circuit = storage.get_circuit(circuit_id)

    # Supplement with hardcoded metadata
    meta = _find_circuit_metadata(circuit_id)

    if circuit:
        features["circuit_length"] = circuit.get("length_km") or 5.0
        features["circuit_corners"] = circuit.get("corners") or meta.get("corners", 15)
        features["circuit_drs_zones"] = circuit.get("drs_zones") or meta.get("drs_zones", 2)
        features["circuit_altitude"] = circuit.get("altitude") or meta.get("altitude", 100)
        features["circuit_latitude"] = circuit.get("latitude") or 0.0
        features["circuit_longitude"] = circuit.get("longitude") or 0.0

        ctype = circuit.get("circuit_type") or meta.get("type", "hybrid")
        features["circuit_type"] = CIRCUIT_TYPE_MAP.get(ctype, 3)
        features["circuit_power_sensitivity"] = (
            circuit.get("power_sensitivity") or meta.get("power_sensitivity", 0.5)
        )
    else:
        features["circuit_length"] = 5.0
        features["circuit_corners"] = meta.get("corners", 15)
        features["circuit_drs_zones"] = meta.get("drs_zones", 2)
        features["circuit_altitude"] = meta.get("altitude", 100)
        features["circuit_latitude"] = 0.0
        features["circuit_longitude"] = 0.0
        features["circuit_type"] = CIRCUIT_TYPE_MAP.get(meta.get("type", "hybrid"), 3)
        features["circuit_power_sensitivity"] = meta.get("power_sensitivity", 0.5)

    # Tyre stress encoding
    tyre_stress = meta.get("tyre_stress", "medium")
    features["circuit_tyre_stress"] = {"low": 0, "medium": 1, "high": 2}.get(tyre_stress, 1)

    # Historical stats from race data (cutoff-respecting)
    features["circuit_overtaking_difficulty"] = _compute_overtaking_rate(
        storage, circuit_id, as_of_date=as_of_date
    )
    features["circuit_safety_car_prob"] = _compute_sc_probability(
        storage, circuit_id, as_of_date=as_of_date
    )

    return features


def _find_circuit_metadata(circuit_id: str) -> dict:
    """Find circuit metadata by fuzzy matching circuit_id."""
    circuit_lower = circuit_id.lower().replace("-", "_").replace(" ", "_")

    # Direct match
    if circuit_lower in CIRCUIT_METADATA:
        return CIRCUIT_METADATA[circuit_lower]

    # Partial match
    for key, meta in CIRCUIT_METADATA.items():
        if key in circuit_lower or circuit_lower in key:
            return meta

    return {}


def _compute_overtaking_rate(storage: Storage, circuit_id: str,
                              as_of_date: str | None = None) -> float:
    """Compute average positions gained per race at this circuit."""
    with storage._connect() as conn:
        if as_of_date:
            rows = conn.execute("""
                SELECT r.grid_position, r.finish_position
                FROM results r
                JOIN races ra ON r.race_id = ra.id
                WHERE ra.circuit_id = ? AND ra.date < ?
                AND r.grid_position IS NOT NULL
                AND r.finish_position IS NOT NULL
            """, (circuit_id, as_of_date)).fetchall()
        else:
            rows = conn.execute("""
                SELECT r.grid_position, r.finish_position
                FROM results r
                JOIN races ra ON r.race_id = ra.id
                WHERE ra.circuit_id = ?
                AND r.grid_position IS NOT NULL
                AND r.finish_position IS NOT NULL
            """, (circuit_id,)).fetchall()

    if not rows:
        return 0.5  # Default medium overtaking

    total_changes = sum(abs(r["grid_position"] - r["finish_position"]) for r in rows)
    return total_changes / len(rows) if rows else 0.5


def _compute_sc_probability(storage: Storage, circuit_id: str,
                             as_of_date: str | None = None) -> float:
    """Estimate safety car probability based on historical DNFs/incidents."""
    with storage._connect() as conn:
        if as_of_date:
            races = conn.execute("""
                SELECT ra.id FROM races ra
                WHERE ra.circuit_id = ? AND ra.date < ?
            """, (circuit_id, as_of_date)).fetchall()
        else:
            races = conn.execute("""
                SELECT ra.id FROM races ra WHERE ra.circuit_id = ?
            """, (circuit_id,)).fetchall()

    if not races:
        return 0.5

    incident_races = 0
    for race in races:
        results = storage.get_results(race["id"])
        if results.empty:
            continue

        # Count races with collisions/incidents
        incidents = results[
            results["status"].str.lower().isin(
                ["collision", "accident", "spun off", "collision damage"]
            )
        ]
        if len(incidents) >= 2:
            incident_races += 1

    return incident_races / len(races) if races else 0.5
