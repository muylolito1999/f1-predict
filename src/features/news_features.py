"""NLP-derived upgrade impact features."""

from datetime import datetime

import numpy as np

from src.data.storage import Storage


# Component type encoding
COMPONENT_MAP = {
    "front_wing": 0, "rear_wing": 1, "floor": 2, "sidepods": 3,
    "diffuser": 4, "suspension": 5, "power_unit": 6, "cooling": 7,
    "bodywork": 8, "other": 9, "none": 10,
}


def extract_news_features(storage: Storage, team: str,
                           race_date: str,
                           lookback_days: int = 14) -> dict:
    """Extract NLP-derived upgrade features for a team.

    Args:
        storage: Database storage instance.
        team: Team name.
        race_date: Race date string (YYYY-MM-DD).
        lookback_days: Days to look back for upgrades.

    Returns:
        Dict of feature name -> value.
    """
    features = {}

    # Get recent upgrades
    upgrades = storage.get_team_upgrades(team, race_date, lookback_days)

    if upgrades.empty:
        features["upgrade_impact_score"] = 0.0
        features["upgrade_component_type"] = COMPONENT_MAP["none"]
        features["upgrade_sentiment"] = 0.0
        features["team_media_confidence"] = 0.0
        features["regulation_compliance_flag"] = 0
        features["upgrade_recency_days"] = lookback_days  # No recent upgrade
        features["upgrade_cumulative"] = _get_cumulative_upgrades(storage, team)
        return features

    # Most impactful recent upgrade
    if "impact_score" in upgrades.columns:
        best_upgrade = upgrades.loc[upgrades["impact_score"].abs().idxmax()]
        features["upgrade_impact_score"] = float(best_upgrade.get("impact_score", 0.0))
        features["upgrade_component_type"] = COMPONENT_MAP.get(
            str(best_upgrade.get("component", "none")), 10
        )
    else:
        features["upgrade_impact_score"] = 0.0
        features["upgrade_component_type"] = COMPONENT_MAP["none"]

    # Average sentiment
    if "sentiment" in upgrades.columns:
        features["upgrade_sentiment"] = upgrades["sentiment"].mean()
    else:
        features["upgrade_sentiment"] = 0.0

    # Media confidence (average sentiment, weighted by recency)
    features["team_media_confidence"] = _compute_media_confidence(
        upgrades, race_date
    )

    # Compliance flag (any negative confidence or compliance issues)
    features["regulation_compliance_flag"] = 0  # Default; set by NLP if detected

    # Days since most recent upgrade
    if "date" in upgrades.columns and not upgrades.empty:
        most_recent = upgrades.iloc[0]["date"]
        try:
            race_dt = datetime.strptime(race_date, "%Y-%m-%d")
            upgrade_dt = datetime.strptime(most_recent, "%Y-%m-%d")
            features["upgrade_recency_days"] = (race_dt - upgrade_dt).days
        except (ValueError, TypeError):
            features["upgrade_recency_days"] = lookback_days
    else:
        features["upgrade_recency_days"] = lookback_days

    # Cumulative upgrade score for the season
    features["upgrade_cumulative"] = _get_cumulative_upgrades(storage, team)

    return features


def _compute_media_confidence(upgrades, race_date: str) -> float:
    """Compute weighted media confidence score."""
    if upgrades.empty or "sentiment" not in upgrades.columns:
        return 0.0

    sentiments = upgrades["sentiment"].dropna()
    if sentiments.empty:
        return 0.0

    # Weight by recency (more recent = higher weight)
    if "date" in upgrades.columns:
        try:
            race_dt = datetime.strptime(race_date, "%Y-%m-%d")
            weights = []
            for _, row in upgrades.iterrows():
                try:
                    dt = datetime.strptime(row["date"], "%Y-%m-%d")
                    days_ago = max(1, (race_dt - dt).days)
                    weights.append(1.0 / days_ago)
                except (ValueError, TypeError):
                    weights.append(0.1)

            if weights and len(weights) == len(sentiments):
                return float(np.average(sentiments.values, weights=weights))
        except (ValueError, TypeError):
            pass

    return float(sentiments.mean())


def _get_cumulative_upgrades(storage: Storage, team: str) -> float:
    """Get total cumulative upgrade impact for the current season."""
    all_upgrades = storage.get_team_upgrades(team)
    if all_upgrades.empty or "impact_score" not in all_upgrades.columns:
        return 0.0

    return float(all_upgrades["impact_score"].sum())
