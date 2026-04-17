"""Bayesian updater for handling regulation changes and cold starts."""

import logging
from dataclasses import dataclass, field

import numpy as np

from src.data.storage import Storage

logger = logging.getLogger(__name__)


@dataclass
class TeamPrior:
    """Bayesian prior for team strength."""
    mean: float = 0.0           # Expected team strength
    variance: float = 100.0     # Uncertainty (high = unknown)
    observations: int = 0       # Number of race results incorporated


@dataclass
class SeasonState:
    """Tracks Bayesian state across a season."""
    team_priors: dict[str, TeamPrior] = field(default_factory=dict)
    fp_weight_boost: float = 2.0  # Extra weight for FP features early in season
    races_completed: int = 0
    regulation_year: bool = False


class BayesianUpdater:
    """Manages Bayesian priors for cold-start and regulation changes."""

    # Years with major regulation changes
    REGULATION_CHANGE_YEARS = {2022, 2026}

    # Teams known for strong regulation adaptation (historical)
    ADAPTATION_PRIORS = {
        "Red Bull": 0.7,
        "Ferrari": 0.6,
        "Mercedes": 0.65,
        "McLaren": 0.5,
        "Aston Martin": 0.45,
        "Alpine": 0.4,
        "Williams": 0.35,
        "RB": 0.4,
        "Haas": 0.35,
        "Sauber": 0.35,
    }

    def __init__(self, storage: Storage,
                 cold_start_races: int = 5,
                 learning_rate: float = 0.3):
        """
        Args:
            storage: Database storage.
            cold_start_races: Number of races for cold-start period.
            learning_rate: How fast priors update (higher = faster adaptation).
        """
        self.storage = storage
        self.cold_start_races = cold_start_races
        self.learning_rate = learning_rate
        self.state = SeasonState()

    def initialize_season(self, year: int, teams: list[str]):
        """Initialize priors for a new season.

        For regulation change years, reset team priors with high uncertainty.
        For normal years, carry forward from previous season.
        """
        is_reg_change = year in self.REGULATION_CHANGE_YEARS
        self.state.regulation_year = is_reg_change
        self.state.races_completed = 0

        for team in teams:
            if is_reg_change:
                # High uncertainty, use adaptation prior
                adaptation = self.ADAPTATION_PRIORS.get(team, 0.4)
                prev_elo = self.storage.get_latest_elo("team", team)
                # Regress toward mean, scaled by adaptation ability
                prior_mean = 1500 + (prev_elo - 1500) * adaptation * 0.3
                prior_variance = 200.0  # Very high uncertainty

                logger.info(
                    f"Regulation change: {team} prior={prior_mean:.0f} "
                    f"(prev={prev_elo:.0f}, adaptation={adaptation:.2f})"
                )
            else:
                # Normal year: carry forward with some regression to mean
                prev_elo = self.storage.get_latest_elo("team", team)
                prior_mean = 1500 + (prev_elo - 1500) * 0.85
                prior_variance = 50.0  # Lower uncertainty

            self.state.team_priors[team] = TeamPrior(
                mean=prior_mean,
                variance=prior_variance,
            )

    def initialize_from_preseason_test(self, year: int,
                                          regression_weight: float = 0.4):
        """Pre-seed team priors using Bahrain pre-season test pace.

        Pre-season data is noisier than real races (different fuel loads,
        setups, programs), so it's worth less than one real race. We
        rank teams by best long-run intercept across PRE1/PRE2/PRE3 and
        nudge each team prior partially toward the pre-season order.

        Args:
            year: the regulation year (e.g. 2026).
            regression_weight: how strongly to pull priors toward the
                pre-season ordering, 0..1.
        """
        import pandas as pd
        # Pull all PRE* rows for the year.
        pre_races = [r for r in self.storage.get_races_for_season(year)
                      if r["round"] < 0]
        if not pre_races:
            logger.info("No pre-season test data stored for %d — skipping", year)
            return

        team_paces: dict[str, list[float]] = {}
        for r in pre_races:
            fp = self.storage.get_fp_data(r["id"])
            for _, row in fp.iterrows():
                pace = row.get("long_run_pace")
                slope = row.get("long_run_degradation") or 0.0
                if pd.isna(pace):
                    continue
                intercept = float(pace) - float(slope) * 5.0
                team_paces.setdefault(row["team"], []).append(intercept)

        if not team_paces:
            return

        # Faster (smaller intercept) = stronger. Map ranks to ELO-like
        # perturbations: rank 1 → +80, last → -80, linearly.
        team_mean = {t: float(np.mean(v)) for t, v in team_paces.items()}
        order = sorted(team_mean.items(), key=lambda kv: kv[1])
        n = len(order)
        for i, (team, _) in enumerate(order):
            # Rank 0 = fastest. Normalize to [-1, +1], invert so fastest is positive.
            rank_norm = 1.0 - 2.0 * i / max(n - 1, 1)
            perturb = 80.0 * rank_norm
            prior = self.state.team_priors.get(team) or TeamPrior(mean=1500.0, variance=200.0)
            prior.mean += regression_weight * perturb
            self.state.team_priors[team] = prior
            logger.info(
                "Pre-season prior %s: rank %d/%d → perturb %+.0f → mean=%.0f",
                team, i + 1, n, perturb, prior.mean
            )

    def update_after_race(self, race_results: dict[str, int]):
        """Update priors after observing a race result.

        Args:
            race_results: Dict of team -> best finish position.
        """
        self.state.races_completed += 1

        for team, position in race_results.items():
            if team not in self.state.team_priors:
                self.state.team_priors[team] = TeamPrior()

            prior = self.state.team_priors[team]

            # Convert position to performance score
            observed_strength = self._position_to_strength(position)

            # Bayesian update (Kalman-filter style)
            # Gain = prior_variance / (prior_variance + observation_noise)
            observation_noise = 30.0  # Race results are noisy
            gain = prior.variance / (prior.variance + observation_noise)

            # Update mean
            prior.mean += gain * (observed_strength - prior.mean)

            # Update variance (decreases with each observation)
            prior.variance *= (1 - gain)
            prior.variance = max(prior.variance, 5.0)  # Floor

            prior.observations += 1

        # Update FP weight boost (decreases as season progresses)
        if self.state.regulation_year:
            progress = min(1.0, self.state.races_completed / self.cold_start_races)
            self.state.fp_weight_boost = 2.0 * (1 - progress) + 1.0 * progress
        else:
            self.state.fp_weight_boost = 1.0

    def get_team_strength(self, team: str) -> float:
        """Get current Bayesian estimate of team strength."""
        prior = self.state.team_priors.get(team)
        if prior is None:
            return 1500.0
        return prior.mean

    def get_team_uncertainty(self, team: str) -> float:
        """Get current uncertainty in team strength estimate."""
        prior = self.state.team_priors.get(team)
        if prior is None:
            return 200.0
        return prior.variance

    def get_fp_weight_boost(self) -> float:
        """Get current FP feature weight boost factor.

        > 1.0 during cold-start period, approaches 1.0 as season progresses.
        """
        return self.state.fp_weight_boost

    def get_confidence_level(self) -> str:
        """Get overall prediction confidence level."""
        if self.state.races_completed == 0:
            return "VERY LOW"
        elif self.state.races_completed < 3:
            return "LOW"
        elif self.state.races_completed < self.cold_start_races:
            return "MEDIUM"
        else:
            return "HIGH"

    def adjust_features(self, features: np.ndarray,
                         feature_names: list[str],
                         team: str) -> np.ndarray:
        """Adjust feature values based on Bayesian state.

        Boosts FP features during cold-start period.
        """
        adjusted = features.copy()
        boost = self.get_fp_weight_boost()

        if boost <= 1.0:
            return adjusted

        # Identify FP feature indices
        fp_indices = [
            i for i, name in enumerate(feature_names)
            if name.startswith("fp_")
        ]

        # Scale FP features by boost factor
        for idx in fp_indices:
            if idx < len(adjusted):
                adjusted[idx] *= boost

        return adjusted

    def _position_to_strength(self, position: int) -> float:
        """Convert finish position to a strength score."""
        # Non-linear mapping: winning is much more significant
        if position <= 0:
            return 1500.0

        # Approximate mapping using sigmoid-like function
        max_strength = 1700
        min_strength = 1300
        return max_strength - (max_strength - min_strength) * (position - 1) / 19
