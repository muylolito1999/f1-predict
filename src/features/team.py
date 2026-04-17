"""Team/car feature extraction including upgrade tracking."""

import numpy as np
import pandas as pd

from src.data.storage import Storage


def extract_team_features(storage: Storage, team: str,
                           year: int, round_num: int,
                           as_of_date: str | None = None) -> dict:
    """Extract all team-level features.

    Args:
        storage: Database storage instance.
        team: Team name.
        year: Season year.
        round_num: Race round number.
        as_of_date: ISO date cutoff. Required for leakage-safe training.

    Returns:
        Dict of feature name -> value.
    """
    features = {}

    # Team Elo rating (strictly before race)
    features["team_elo"] = storage.get_latest_elo("team", team, before_date=as_of_date)

    # Constructor championship position
    c_standings = storage.get_constructor_standings_before_race(year, round_num)
    if not c_standings.empty:
        team_standing = c_standings[c_standings["team"] == team]
        if not team_standing.empty:
            features["team_constructor_pos"] = team_standing.iloc[0]["position"]
            features["team_constructor_points"] = team_standing.iloc[0]["points"]
    features.setdefault("team_constructor_pos", 5)
    features.setdefault("team_constructor_points", 0.0)

    # Recent form (team points over last 5 races)
    features["team_recent_form"] = _compute_team_form(
        storage, team, year, round_num, as_of_date=as_of_date
    )

    # Development trajectory (slope of performance)
    features["team_development_trajectory"] = _compute_dev_trajectory(
        storage, team, year, round_num, as_of_date=as_of_date
    )

    # Pit stop performance
    pit_stats = _compute_pit_stats(storage, team, as_of_date=as_of_date)
    features["team_pit_stop_avg"] = pit_stats["avg"]
    features["team_pit_stop_consistency"] = pit_stats["std"]

    # Reliability score
    features["team_reliability_score"] = _compute_reliability(
        storage, team, year, round_num, as_of_date=as_of_date
    )

    return features


def _compute_team_form(storage: Storage, team: str,
                        year: int, round_num: int,
                        window: int = 5,
                        as_of_date: str | None = None) -> float:
    """Compute weighted average team performance over recent races."""
    races = storage.get_races_for_season(year)

    # Also include previous season if early in the year
    if round_num <= 3:
        prev_races = storage.get_races_for_season(year - 1)
        races = prev_races + races

    # Get races before current round (and before as_of_date if provided)
    recent_race_ids = []
    for race in reversed(races):
        before_round = (
            race["year"] < year or (race["year"] == year and race["round"] < round_num)
        )
        before_cutoff = (
            as_of_date is None or (race.get("date") and race["date"] < as_of_date)
        )
        if before_round and before_cutoff:
            recent_race_ids.append(race["id"])
        if len(recent_race_ids) >= window:
            break

    if not recent_race_ids:
        return 10.0  # Default mid-field

    positions = []
    decay = 0.85
    for i, race_id in enumerate(recent_race_ids):
        results = storage.get_results(race_id)
        if results.empty:
            continue

        team_results = results[results["team"] == team]
        if team_results.empty:
            continue

        # Average finish position of both drivers
        avg_pos = team_results["finish_position"].dropna().mean()
        if not np.isnan(avg_pos):
            positions.append((avg_pos, decay ** i))

    if positions:
        vals, weights = zip(*positions)
        return np.average(vals, weights=weights)
    return 10.0


def _compute_dev_trajectory(storage: Storage, team: str,
                             year: int, round_num: int,
                             window: int = 8,
                             as_of_date: str | None = None) -> float:
    """Compute slope of team performance over recent races.

    Negative slope = improving, positive = declining.
    """
    races = storage.get_races_for_season(year)
    prev_races = storage.get_races_for_season(year - 1)
    all_races = prev_races + races

    recent = []
    for race in reversed(all_races):
        before_round = (
            race["year"] < year or (race["year"] == year and race["round"] < round_num)
        )
        before_cutoff = (
            as_of_date is None or (race.get("date") and race["date"] < as_of_date)
        )
        if before_round and before_cutoff:
            results = storage.get_results(race["id"])
            if not results.empty:
                team_results = results[results["team"] == team]
                if not team_results.empty:
                    avg_pos = team_results["finish_position"].dropna().mean()
                    if not np.isnan(avg_pos):
                        recent.append(avg_pos)
        if len(recent) >= window:
            break

    if len(recent) < 3:
        return 0.0

    # Reverse so index 0 = oldest
    recent = list(reversed(recent))
    x = np.arange(len(recent))
    slope = np.polyfit(x, recent, 1)[0]
    return slope  # Negative = improving


def _compute_pit_stats(storage: Storage, team: str,
                        as_of_date: str | None = None) -> dict:
    """Compute team pit stop statistics."""
    pit_data = storage.get_team_pit_stops(team, limit=40, before_date=as_of_date)

    if pit_data.empty or "duration" not in pit_data.columns:
        return {"avg": 25.0, "std": 2.0}

    durations = pit_data["duration"].dropna()
    # Filter out obvious outliers (pit lane issues)
    durations = durations[durations < 60]

    if durations.empty:
        return {"avg": 25.0, "std": 2.0}

    return {
        "avg": durations.mean(),
        "std": durations.std() if len(durations) > 1 else 2.0,
    }


def _compute_reliability(storage: Storage, team: str,
                          year: int, round_num: int,
                          window: int = 10,
                          as_of_date: str | None = None) -> float:
    """Compute team mechanical reliability score (0 = perfect, 1 = terrible)."""
    races = storage.get_races_for_season(year)
    prev_races = storage.get_races_for_season(year - 1)
    all_races = prev_races + races

    mechanical_dnfs = 0
    total_entries = 0

    count = 0
    for race in reversed(all_races):
        before_round = (
            race["year"] < year or (race["year"] == year and race["round"] < round_num)
        )
        before_cutoff = (
            as_of_date is None or (race.get("date") and race["date"] < as_of_date)
        )
        if before_round and before_cutoff:
            results = storage.get_results(race["id"])
            if results.empty:
                continue

            team_results = results[results["team"] == team]
            for _, r in team_results.iterrows():
                total_entries += 1
                status = str(r.get("status", "")).lower()
                if status and status not in ("finished", "+1 lap", "+2 laps",
                                              "+3 laps", "collision",
                                              "accident", "spun off"):
                    mechanical_dnfs += 1

            count += 1
            if count >= window:
                break

    if total_entries == 0:
        return 0.1  # Default low DNF rate

    return mechanical_dnfs / total_entries


def update_team_elo(storage: Storage, race_id: int, year: int,
                    round_num: int, k_factor: float = 24):
    """Update team Elo ratings after a race."""
    results = storage.get_results(race_id)
    if results.empty:
        return

    # Aggregate team performance (best finisher per team)
    team_best = {}
    for _, r in results.iterrows():
        team = r["team"]
        pos = r["finish_position"]
        if pd.notna(pos):
            if team not in team_best or pos < team_best[team]:
                team_best[team] = int(pos)

    teams = [{"team": t, "position": p, "elo": storage.get_latest_elo("team", t)}
             for t, p in team_best.items()]

    if len(teams) < 2:
        return

    new_ratings = {t["team"]: t["elo"] for t in teams}

    for i, t1 in enumerate(teams):
        for j, t2 in enumerate(teams):
            if i >= j:
                continue

            e1 = 1.0 / (1.0 + 10 ** ((t2["elo"] - t1["elo"]) / 400))
            s1 = 1.0 if t1["position"] < t2["position"] else 0.0

            scale = k_factor / (len(teams) - 1)
            new_ratings[t1["team"]] += scale * (s1 - e1)
            new_ratings[t2["team"]] += scale * ((1 - s1) - (1 - e1))

    for team, rating in new_ratings.items():
        storage.save_elo("team", team, year, round_num, rating)
