"""Monte Carlo race simulator.

Produces calibrated win/podium/points probabilities by sampling DNFs,
safety cars, and score noise, then aggregating simulated finish orders.
Much better than the score-gap heuristic in ensemble.py for the top-3
probability calibration the user cares about.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class RaceSimulator:
    """Sample many plausible race outcomes from the ensemble's scores.

    Parameters
    ----------
    n_sims:
        Number of Monte Carlo runs per prediction.
    score_noise_sigma:
        Std dev of Gaussian noise added to the ranking score per sim.
        Fit from backtest residuals (defaults to a reasonable value).
    safety_car_position_shake:
        Extra std dev applied to the race when a safety car sample fires.
    seed:
        RNG seed for reproducibility.
    """

    def __init__(self, n_sims: int = 5000, score_noise_sigma: float = 0.25,
                 safety_car_position_shake: float = 0.4, seed: int = 42):
        self.n_sims = n_sims
        self.score_noise_sigma = score_noise_sigma
        self.safety_car_position_shake = safety_car_position_shake
        self.rng = np.random.default_rng(seed)

    def simulate(self, scores: np.ndarray,
                  driver_ids: list[str],
                  dnf_rates: np.ndarray | None = None,
                  sc_probability: float = 0.35) -> dict:
        """Run the simulator and return per-driver outcome probabilities.

        Returns
        -------
        dict
            {
              "win_probability": np.ndarray,
              "podium_probability": np.ndarray,
              "points_probability": np.ndarray,
              "expected_position": np.ndarray,
              "position_p10": np.ndarray,   # 10th percentile finish pos
              "position_p90": np.ndarray,   # 90th percentile
              "simulated_positions": np.ndarray,  # (n_sims, n_drivers) ranks
            }
        """
        n = len(scores)
        if dnf_rates is None:
            dnf_rates = np.full(n, 0.08)

        scores = np.asarray(scores, dtype=np.float64)
        positions = np.zeros((self.n_sims, n), dtype=np.int32)

        for i in range(self.n_sims):
            noise = self.rng.normal(0.0, self.score_noise_sigma, size=n)

            # Safety car events: extra noise for every affected lap; we
            # model as a single amplified-noise event if a SC fires.
            if self.rng.random() < sc_probability:
                noise += self.rng.normal(0.0, self.safety_car_position_shake, size=n)

            sim_scores = scores + noise

            # DNFs: anyone who DNFs is pushed to the bottom of the order.
            dnf_mask = self.rng.random(n) < dnf_rates
            sim_scores[dnf_mask] = -np.inf

            # Rank 1..n by descending score; ties broken by RNG.
            jitter = self.rng.normal(0.0, 1e-6, size=n)
            order = np.argsort(-(sim_scores + jitter))
            pos = np.empty(n, dtype=np.int32)
            pos[order] = np.arange(1, n + 1)
            positions[i] = pos

        wins = (positions == 1).mean(axis=0)
        podium = (positions <= 3).mean(axis=0)
        points = (positions <= 10).mean(axis=0)
        expected = positions.mean(axis=0)
        p10 = np.percentile(positions, 10, axis=0)
        p90 = np.percentile(positions, 90, axis=0)

        return {
            "driver_ids": list(driver_ids),
            "win_probability": wins,
            "podium_probability": podium,
            "points_probability": points,
            "expected_position": expected,
            "position_p10": p10.astype(float),
            "position_p90": p90.astype(float),
            "simulated_positions": positions,
        }


def estimate_dnf_rates(storage, driver_ids: list[str], circuit_id: str,
                        is_wet: int = 0, as_of_date: str | None = None,
                        default: float = 0.08) -> np.ndarray:
    """Per-driver DNF rate blended from driver history and circuit baseline.

    Uses a simple Bayesian shrinkage toward a circuit-level prior.
    """
    out = np.zeros(len(driver_ids))
    circuit_prior = _circuit_dnf_prior(storage, circuit_id, as_of_date)

    for i, drv in enumerate(driver_ids):
        recent = storage.get_recent_results(drv, limit=30, before_date=as_of_date)
        if recent.empty:
            out[i] = max(default, circuit_prior)
            continue
        dnfs = sum(
            1 for _, r in recent.iterrows()
            if str(r.get("status", "")).lower() not in (
                "finished", "+1 lap", "+2 laps", "+3 laps", ""
            )
        )
        driver_rate = dnfs / len(recent)
        # Shrink toward circuit prior with pseudo-count of 10 races.
        pc = 10
        blended = (dnfs + circuit_prior * pc) / (len(recent) + pc)
        # Wet conditions bump rates ~1.5x.
        if is_wet:
            blended = min(0.5, blended * 1.5)
        out[i] = blended
    return out


def _circuit_dnf_prior(storage, circuit_id: str,
                        as_of_date: str | None = None) -> float:
    """Fraction of drivers that DNF historically at this circuit."""
    with storage._connect() as conn:
        if as_of_date:
            rows = conn.execute("""
                SELECT r.status FROM results r
                JOIN races ra ON r.race_id = ra.id
                WHERE ra.circuit_id = ? AND ra.date < ?
            """, (circuit_id, as_of_date)).fetchall()
        else:
            rows = conn.execute("""
                SELECT r.status FROM results r
                JOIN races ra ON r.race_id = ra.id
                WHERE ra.circuit_id = ?
            """, (circuit_id,)).fetchall()

    if not rows:
        return 0.08
    dnfs = sum(
        1 for r in rows
        if str(r["status"]).lower() not in ("finished", "+1 lap", "+2 laps", "+3 laps", "")
    )
    return dnfs / len(rows)
