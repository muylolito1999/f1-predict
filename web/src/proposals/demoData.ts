// Realistic 2026 F1 demo dataset used by all proposal pages so each
// aesthetic can be evaluated without a running backend. Numbers are
// hand-tuned to look plausible (probabilities sum to ~1 for win, etc.).

import type { PredictResponse } from "../types";

interface Driver {
  id: string;
  name: string;
  team: string;
  abbr: string;
  number: number;
}

const DRIVERS: Driver[] = [
  { id: "VER", name: "Max Verstappen", team: "Red Bull Racing", abbr: "VER", number: 1 },
  { id: "NOR", name: "Lando Norris", team: "McLaren", abbr: "NOR", number: 4 },
  { id: "LEC", name: "Charles Leclerc", team: "Ferrari", abbr: "LEC", number: 16 },
  { id: "PIA", name: "Oscar Piastri", team: "McLaren", abbr: "PIA", number: 81 },
  { id: "RUS", name: "George Russell", team: "Mercedes", abbr: "RUS", number: 63 },
  { id: "SAI", name: "Carlos Sainz", team: "Williams", abbr: "SAI", number: 55 },
  { id: "HAM", name: "Lewis Hamilton", team: "Ferrari", abbr: "HAM", number: 44 },
  { id: "ANT", name: "Kimi Antonelli", team: "Mercedes", abbr: "ANT", number: 12 },
  { id: "TSU", name: "Yuki Tsunoda", team: "Red Bull Racing", abbr: "TSU", number: 22 },
  { id: "ALO", name: "Fernando Alonso", team: "Aston Martin", abbr: "ALO", number: 14 },
  { id: "STR", name: "Lance Stroll", team: "Aston Martin", abbr: "STR", number: 18 },
  { id: "GAS", name: "Pierre Gasly", team: "Alpine", abbr: "GAS", number: 10 },
  { id: "OCO", name: "Esteban Ocon", team: "Haas", abbr: "OCO", number: 31 },
  { id: "HUL", name: "Nico Hülkenberg", team: "Kick Sauber", abbr: "HUL", number: 27 },
  { id: "ALB", name: "Alex Albon", team: "Williams", abbr: "ALB", number: 23 },
  { id: "HAD", name: "Isack Hadjar", team: "Racing Bulls", abbr: "HAD", number: 6 },
  { id: "LAW", name: "Liam Lawson", team: "Racing Bulls", abbr: "LAW", number: 30 },
  { id: "BEA", name: "Oliver Bearman", team: "Haas", abbr: "BEA", number: 87 },
  { id: "BOR", name: "Gabriel Bortoleto", team: "Kick Sauber", abbr: "BOR", number: 5 },
  { id: "DOO", name: "Jack Doohan", team: "Alpine", abbr: "DOO", number: 7 },
];

// Ensemble scores sorted high-to-low; predicted position = index + 1.
const SCORES = [
  0.92, 0.84, 0.78, 0.74, 0.66, 0.58, 0.54, 0.49, 0.44, 0.39,
  0.35, 0.31, 0.27, 0.23, 0.19, 0.15, 0.12, 0.09, 0.06, 0.03,
];

// Hand-tuned probabilities: top of grid gets lion's share of win%
const WIN_PROBS = [
  0.34, 0.21, 0.15, 0.11, 0.07, 0.04, 0.025, 0.015, 0.008, 0.005,
  0.003, 0.002, 0.001, 0.001, 0.0005, 0.0003, 0.0002, 0.0001, 0.0001, 0.0001,
];

const PODIUM_PROBS = [
  0.74, 0.62, 0.54, 0.48, 0.32, 0.18, 0.12, 0.08, 0.05, 0.03,
  0.02, 0.015, 0.01, 0.008, 0.005, 0.003, 0.002, 0.001, 0.001, 0.0005,
];

const POINTS_PROBS = [
  0.98, 0.96, 0.94, 0.92, 0.88, 0.82, 0.78, 0.72, 0.66, 0.58,
  0.48, 0.38, 0.28, 0.20, 0.14, 0.09, 0.06, 0.04, 0.02, 0.01,
];

function makeHistogram(predicted: number, spread: number, nSims = 5000, n = 20): number[] {
  // Sample from a skewed distribution around the predicted position.
  const hist = new Array(n).fill(0);
  let remaining = nSims;
  for (let pos = 1; pos <= n; pos++) {
    const d = Math.abs(pos - predicted);
    const weight = Math.exp(-(d * d) / (2 * spread * spread));
    hist[pos - 1] = weight;
  }
  // Normalize to nSims
  const total = hist.reduce((a, b) => a + b, 0);
  for (let i = 0; i < n; i++) {
    const c = Math.round((hist[i] / total) * nSims);
    hist[i] = c;
    remaining -= c;
  }
  // Drop the rounding remainder on the predicted position bucket
  hist[predicted - 1] += remaining;
  return hist;
}

function percentile(hist: number[], q: number): number {
  const total = hist.reduce((a, b) => a + b, 0);
  const target = total * q;
  let cum = 0;
  for (let i = 0; i < hist.length; i++) {
    cum += hist[i];
    if (cum >= target) return i + 1;
  }
  return hist.length;
}

function expectedPos(hist: number[]): number {
  const total = hist.reduce((a, b) => a + b, 0);
  let sum = 0;
  for (let i = 0; i < hist.length; i++) {
    sum += (i + 1) * hist[i];
  }
  return sum / total;
}

const predictions = DRIVERS.map((d, i) => {
  const pos = i + 1;
  const spread = Math.min(4, 1 + pos * 0.15);
  const hist = makeHistogram(pos, spread);
  return {
    driver_id: d.id,
    driver_name: d.name,
    team: d.team,
    predicted_position: pos,
    ensemble_score: SCORES[i],
    win_probability: WIN_PROBS[i],
    podium_probability: PODIUM_PROBS[i],
    points_probability: POINTS_PROBS[i],
    expected_position: expectedPos(hist),
    position_p10: percentile(hist, 0.1),
    position_p90: percentile(hist, 0.9),
    _hist: hist,
  };
});

const FEATURE_IMPORTANCE = [
  { feature: "fp_long_run_pace", importance: 0.142, pct: 14.2 },
  { feature: "driver_elo", importance: 0.118, pct: 11.8 },
  { feature: "team_elo", importance: 0.096, pct: 9.6 },
  { feature: "fp_best_lap_delta", importance: 0.081, pct: 8.1 },
  { feature: "driver_recent_form", importance: 0.068, pct: 6.8 },
  { feature: "fp_consistency", importance: 0.059, pct: 5.9 },
  { feature: "team_development_trajectory", importance: 0.051, pct: 5.1 },
  { feature: "driver_circuit_history", importance: 0.045, pct: 4.5 },
  { feature: "circuit_power_sensitivity", importance: 0.038, pct: 3.8 },
  { feature: "predicted_grid_position", importance: 0.034, pct: 3.4 },
  { feature: "fp_long_run_degradation", importance: 0.031, pct: 3.1 },
  { feature: "team_pit_stop_avg", importance: 0.029, pct: 2.9 },
  { feature: "race_temp_track", importance: 0.024, pct: 2.4 },
  { feature: "driver_teammate_delta", importance: 0.022, pct: 2.2 },
  { feature: "upgrade_cumulative", importance: 0.019, pct: 1.9 },
  { feature: "driver_wet_ability", importance: 0.017, pct: 1.7 },
  { feature: "circuit_overtaking_difficulty", importance: 0.015, pct: 1.5 },
  { feature: "race_rain_prob", importance: 0.013, pct: 1.3 },
  { feature: "tyre_deg_relative", importance: 0.011, pct: 1.1 },
  { feature: "fp_speed_trap_max", importance: 0.010, pct: 1.0 },
];

// Realistic SHAP contributions — what made the model rank VER P1
const SHAP_BY_DRIVER: Record<string, { feature: string; shap_value: number }[]> = {
  VER: [
    { feature: "driver_elo", shap_value: 0.41 },
    { feature: "fp_long_run_pace", shap_value: 0.28 },
    { feature: "team_elo", shap_value: 0.22 },
    { feature: "driver_circuit_history", shap_value: 0.15 },
    { feature: "fp_consistency", shap_value: -0.08 },
    { feature: "driver_recent_form", shap_value: 0.19 },
    { feature: "upgrade_cumulative", shap_value: 0.11 },
    { feature: "circuit_power_sensitivity", shap_value: 0.07 },
  ],
  NOR: [
    { feature: "fp_long_run_pace", shap_value: 0.38 },
    { feature: "team_development_trajectory", shap_value: 0.24 },
    { feature: "driver_recent_form", shap_value: 0.21 },
    { feature: "team_elo", shap_value: 0.17 },
    { feature: "driver_elo", shap_value: 0.11 },
    { feature: "fp_best_lap_delta", shap_value: 0.09 },
    { feature: "circuit_overtaking_difficulty", shap_value: -0.06 },
    { feature: "race_temp_track", shap_value: 0.04 },
  ],
  LEC: [
    { feature: "fp_best_lap_delta", shap_value: 0.31 },
    { feature: "driver_circuit_history", shap_value: 0.22 },
    { feature: "driver_elo", shap_value: 0.18 },
    { feature: "team_elo", shap_value: 0.14 },
    { feature: "fp_long_run_degradation", shap_value: -0.12 },
    { feature: "upgrade_cumulative", shap_value: 0.08 },
    { feature: "driver_teammate_delta", shap_value: 0.06 },
    { feature: "race_rain_prob", shap_value: -0.03 },
  ],
};

// Fill in plausible SHAP for everyone else
for (const d of DRIVERS) {
  if (SHAP_BY_DRIVER[d.id]) continue;
  const i = DRIVERS.findIndex((x) => x.id === d.id);
  const polarity = i < 10 ? 1 : -1;
  SHAP_BY_DRIVER[d.id] = [
    { feature: "driver_elo", shap_value: polarity * (0.25 - i * 0.012) },
    { feature: "team_elo", shap_value: polarity * (0.2 - i * 0.01) },
    { feature: "fp_long_run_pace", shap_value: polarity * (0.18 - i * 0.009) },
    { feature: "driver_recent_form", shap_value: polarity * (0.14 - i * 0.007) },
    { feature: "fp_consistency", shap_value: polarity * (0.1 - i * 0.005) * 0.5 },
    { feature: "team_pit_stop_avg", shap_value: polarity * 0.04 },
    { feature: "upgrade_cumulative", shap_value: polarity * 0.03 },
    { feature: "race_temp_track", shap_value: polarity * 0.02 },
  ];
}

const FEATURES_BY_DRIVER: Record<string, Record<string, number>> = {};
for (const d of DRIVERS) {
  const i = DRIVERS.findIndex((x) => x.id === d.id);
  const pace = 92.3 + i * 0.18 + (Math.sin(i) * 0.1);
  FEATURES_BY_DRIVER[d.id] = {
    fp_best_lap_delta: 0.02 + i * 0.04,
    fp_long_run_pace: pace,
    fp_short_run_pace: pace - 0.4,
    fp_consistency: 0.11 + i * 0.015,
    fp_long_run_degradation: 0.08 + i * 0.005,
    fp_speed_trap_max: 341 - i * 0.8,
    fp_improvement_fp1_to_fp3: 0.6 - i * 0.03,
    fp_total_laps: 42 - i,
    driver_elo: 1820 - i * 28,
    driver_circuit_history: 2.4 + i * 0.3,
    driver_recent_form: 1 - i * 0.04,
    driver_wet_ability: 0.82 - i * 0.025,
    driver_overtake_rate: 0.34 - i * 0.01,
    driver_dnf_rate: 0.06 + i * 0.005,
    driver_championship_pos: i + 1,
    driver_championship_points: 280 - i * 14,
    driver_starts: 180 - i * 8,
    driver_wins_rate: Math.max(0, 0.28 - i * 0.02),
    driver_podium_rate: Math.max(0, 0.45 - i * 0.025),
    team_elo: 1750 - Math.floor(i / 2) * 40,
    team_constructor_pos: Math.floor(i / 2) + 1,
    team_constructor_points: 480 - Math.floor(i / 2) * 50,
    team_recent_form: 0.78 - i * 0.03,
    team_development_trajectory: 0.12 - i * 0.01,
    team_pit_stop_avg: 2.41 + i * 0.05,
    team_reliability_score: 0.92 - i * 0.01,
    circuit_type: 1,
    circuit_length: 5.412,
    circuit_corners: 15,
    circuit_drs_zones: 3,
    circuit_altitude: 7,
    circuit_power_sensitivity: 0.72,
    circuit_tyre_stress: 2,
    race_temp_air: 24.3,
    race_temp_track: 38.1,
    race_humidity: 58,
    race_wind_speed: 4.2,
    race_rain_prob: 0.08,
    race_is_wet: 0,
    upgrade_impact_score: 0.14 - i * 0.01,
    upgrade_sentiment: 0.3 - i * 0.015,
    upgrade_recency_days: 3,
  };
}

export const RACE_DRIVERS = DRIVERS;

export const DEMO: PredictResponse & {
  predictions: (PredictResponse["predictions"][number] & { _hist?: number[] })[];
} = {
  predictions,
  feature_importance: FEATURE_IMPORTANCE,
  features_by_driver: FEATURES_BY_DRIVER,
  shap_by_driver: SHAP_BY_DRIVER,
  position_histograms: Object.fromEntries(
    predictions.map((p) => [p.driver_id, p._hist!]),
  ),
  metadata: {
    race_name: "Bahrain Grand Prix",
    year: 2026,
    round: 1,
    sessions_used: "FP1, FP2, FP3",
    confidence: "HIGH",
  },
};

export function driverByPos(pos: number) {
  return DRIVERS.find((_, i) => i + 1 === pos)!;
}

export function driverMeta(id: string) {
  return DRIVERS.find((d) => d.id === id)!;
}
