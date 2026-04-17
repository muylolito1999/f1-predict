/** The prediction pipeline modeled as discrete steps. Each step has a
 *  rough duration estimate derived from observed timings. The animator
 *  advances through them while the backend works in the background so
 *  the user sees what the system is doing. */

export interface PipelineStep {
  id: string;
  label: string;
  detail: string;
  /** Rough estimated wall-clock duration in ms. */
  estMs: number;
  /** When true, this step is skipped when the user toggles the
   *  corresponding option off (skip_news / skip_weather). */
  skippableBy?: "news" | "weather";
}

export const PIPELINE: PipelineStep[] = [
  {
    id: "resolve",
    label: "Resolving race",
    detail: "Looking up circuit metadata and round info",
    estMs: 400,
  },
  {
    id: "fp1",
    label: "Free Practice 1 · Telemetry",
    detail: "Pulling lap times, sectors, speed-trap from FastF1",
    estMs: 3800,
  },
  {
    id: "fp2",
    label: "Free Practice 2 · Telemetry",
    detail: "Long-run pace, tyre degradation, compound performance",
    estMs: 3800,
  },
  {
    id: "fp3",
    label: "Free Practice 3 · Telemetry",
    detail: "Qualifying simulations, best-lap deltas",
    estMs: 3500,
  },
  {
    id: "weather",
    label: "Weather forecast",
    detail: "Race-day track/air temperature, wind, rain probability",
    estMs: 1600,
    skippableBy: "weather",
  },
  {
    id: "news",
    label: "Upgrade news · NLP",
    detail: "Scraping sources, GPT-4o structured extraction",
    estMs: 7200,
    skippableBy: "news",
  },
  {
    id: "features",
    label: "Feature matrix",
    detail: "Composing 56 features across 7 categories per driver",
    estMs: 2200,
  },
  {
    id: "bayesian",
    label: "Bayesian cold-start",
    detail: "Shrinking new-regulation priors toward team strength",
    estMs: 700,
  },
  {
    id: "models",
    label: "Loading ensemble",
    detail: "XGBoost · LightGBM · CatBoost · Neural · Stacker",
    estMs: 2400,
  },
  {
    id: "simulate",
    label: "Monte Carlo · 5,000 runs",
    detail: "Sampling DNFs, safety cars, score noise per simulation",
    estMs: 5800,
  },
  {
    id: "calibrate",
    label: "Probability calibration",
    detail: "Isotonic regression on win / podium / points heads",
    estMs: 500,
  },
  {
    id: "shap",
    label: "SHAP attribution",
    detail: "Per-driver feature contributions from TreeExplainer",
    estMs: 2400,
  },
];

export function activeSteps(options: { skipNews: boolean; skipWeather: boolean }): PipelineStep[] {
  return PIPELINE.filter((s) => {
    if (s.skippableBy === "news" && options.skipNews) return false;
    if (s.skippableBy === "weather" && options.skipWeather) return false;
    return true;
  });
}

export function totalDuration(steps: PipelineStep[]): number {
  return steps.reduce((sum, s) => sum + s.estMs, 0);
}
