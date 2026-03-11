"""Driver-level feature extraction."""

import numpy as np
import pandas as pd

from src.data.storage import Storage


def extract_driver_features(storage: Storage, driver_id: str,
                             team: str, year: int, round_num: int,
                             circuit_id: str) -> dict:
    """Extract all driver-level features.

    Args:
        storage: Database storage instance.
        driver_id: Driver abbreviation (e.g., "VER").
        team: Team name.
        year: Season year.
        round_num: Race round number.
        circuit_id: Circuit identifier.

    Returns:
        Dict of feature name -> value.
    """
    features = {}

    # Elo rating
    features["driver_elo"] = storage.get_latest_elo("driver", driver_id)

    # Circuit-specific history
    circuit_results = storage.get_driver_results_at_circuit(driver_id, circuit_id)
    if not circuit_results.empty:
        positions = circuit_results["finish_position"].dropna()
        if not positions.empty:
            features["driver_circuit_history"] = positions.mean()
            features["driver_circuit_best"] = positions.min()
    features.setdefault("driver_circuit_history", 10.0)  # Default mid-field
    features.setdefault("driver_circuit_best", 10.0)

    # Recent form (weighted average of last N races)
    recent = storage.get_recent_results(driver_id, limit=5)
    if not recent.empty:
        positions = recent["finish_position"].dropna()
        if not positions.empty:
            decay = 0.85
            weights = [decay ** i for i in range(len(positions))]
            features["driver_recent_form"] = np.average(positions.values, weights=weights)

            # DNF rate
            total = len(recent)
            dnfs = sum(1 for _, r in recent.iterrows()
                       if r["status"] not in ("Finished", "+1 Lap", "+2 Laps",
                                               "+3 Laps", ""))
            features["driver_dnf_rate"] = dnfs / total if total > 0 else 0.0

            # Overtaking rate (positions gained from grid to finish)
            overtakes = []
            for _, r in recent.iterrows():
                if pd.notna(r["grid_position"]) and pd.notna(r["finish_position"]):
                    overtakes.append(r["grid_position"] - r["finish_position"])
            if overtakes:
                features["driver_overtake_rate"] = np.mean(overtakes)
    features.setdefault("driver_recent_form", 10.0)
    features.setdefault("driver_dnf_rate", 0.1)
    features.setdefault("driver_overtake_rate", 0.0)

    # Wet weather ability (historical wet races)
    # Approximated from races where weather was wet
    features["driver_wet_ability"] = _compute_wet_ability(storage, driver_id)

    # Championship position
    standings = storage.get_standings_before_race(year, round_num)
    if not standings.empty:
        driver_standing = standings[standings["driver_id"] == driver_id]
        if not driver_standing.empty:
            features["driver_championship_pos"] = driver_standing.iloc[0]["position"]
            features["driver_championship_points"] = driver_standing.iloc[0]["points"]
    features.setdefault("driver_championship_pos", 10)
    features.setdefault("driver_championship_points", 0.0)

    # Teammate delta
    features["driver_teammate_delta"] = _compute_teammate_delta(
        storage, driver_id, team
    )

    # Career stats (approximate from available data)
    all_results = storage.get_recent_results(driver_id, limit=200)
    if not all_results.empty:
        features["driver_starts"] = len(all_results)
        wins = (all_results["finish_position"] == 1).sum()
        features["driver_wins_rate"] = wins / len(all_results) if len(all_results) > 0 else 0.0
        podiums = (all_results["finish_position"] <= 3).sum()
        features["driver_podium_rate"] = podiums / len(all_results) if len(all_results) > 0 else 0.0

        # Podium streak
        streak = 0
        for _, r in all_results.iterrows():
            if pd.notna(r["finish_position"]) and r["finish_position"] <= 3:
                streak += 1
            else:
                break
        features["driver_podium_streak"] = streak
    else:
        features["driver_starts"] = 0
        features["driver_wins_rate"] = 0.0
        features["driver_podium_rate"] = 0.0
        features["driver_podium_streak"] = 0

    return features


def _compute_wet_ability(storage: Storage, driver_id: str) -> float:
    """Compute driver's wet weather performance rating.

    Compares performance in wet vs dry races.
    """
    recent = storage.get_recent_results(driver_id, limit=100)
    if recent.empty:
        return 0.0

    wet_improvements = []
    for _, r in recent.iterrows():
        race_id = r.get("race_id")
        if race_id is None:
            continue

        weather = storage.get_weather(race_id, "R")
        if weather and weather.get("is_wet"):
            if pd.notna(r["grid_position"]) and pd.notna(r["finish_position"]):
                improvement = r["grid_position"] - r["finish_position"]
                wet_improvements.append(improvement)

    if wet_improvements:
        return np.mean(wet_improvements)
    return 0.0


def _compute_teammate_delta(storage: Storage, driver_id: str,
                             team: str) -> float:
    """Compute average finish position delta vs teammate."""
    recent = storage.get_recent_results(driver_id, limit=10)
    if recent.empty:
        return 0.0

    deltas = []
    for _, r in recent.iterrows():
        race_id = r.get("race_id")
        if race_id is None:
            continue

        results = storage.get_results(race_id)
        if results.empty:
            continue

        # Find teammate
        teammates = results[
            (results["team"] == team) & (results["driver_id"] != driver_id)
        ]

        if teammates.empty:
            continue

        driver_pos = r["finish_position"]
        tm_pos = teammates.iloc[0]["finish_position"]

        if pd.notna(driver_pos) and pd.notna(tm_pos):
            deltas.append(tm_pos - driver_pos)  # Positive = ahead of teammate

    return np.mean(deltas) if deltas else 0.0


def update_elo(storage: Storage, race_id: int, year: int, round_num: int,
               k_factor: float = 32):
    """Update Elo ratings after a race result."""
    results = storage.get_results(race_id)
    if results.empty:
        return

    # Get current ratings
    drivers = []
    for _, r in results.iterrows():
        if pd.notna(r["finish_position"]):
            elo = storage.get_latest_elo("driver", r["driver_id"])
            drivers.append({
                "driver_id": r["driver_id"],
                "position": int(r["finish_position"]),
                "elo": elo,
            })

    if len(drivers) < 2:
        return

    # Pairwise Elo updates
    new_ratings = {d["driver_id"]: d["elo"] for d in drivers}

    for i, d1 in enumerate(drivers):
        for j, d2 in enumerate(drivers):
            if i >= j:
                continue

            # Expected score
            e1 = 1.0 / (1.0 + 10 ** ((d2["elo"] - d1["elo"]) / 400))

            # Actual score (1 if d1 finished ahead, 0 otherwise)
            s1 = 1.0 if d1["position"] < d2["position"] else 0.0

            # Update (scaled down by number of comparisons)
            scale = k_factor / (len(drivers) - 1)
            new_ratings[d1["driver_id"]] += scale * (s1 - e1)
            new_ratings[d2["driver_id"]] += scale * ((1 - s1) - (1 - e1))

    # Save new ratings
    for driver_id, rating in new_ratings.items():
        storage.save_elo("driver", driver_id, year, round_num, rating)
