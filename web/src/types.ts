export interface Race {
  year: number;
  round: number;
  name: string;
  date: string;
  country: string;
}

export interface PredictionRow {
  predicted_position: number;
  driver_id: string;
  driver_name: string;
  team: string;
  win_probability: number;
  podium_probability: number;
  points_probability: number;
  ensemble_score: number;
  // Monte Carlo simulation outputs (optional for back-compat)
  expected_position?: number;
  position_p10?: number;
  position_p90?: number;
  race_name?: string;
  year?: number;
  round?: number;
  sessions_used?: string;
  confidence?: string;
  [key: string]: unknown;
}

export interface FeatureImportanceRow {
  feature: string;
  importance: number;
  pct: number;
}

export interface ShapContribution {
  feature: string;
  shap_value: number;
}

export interface PredictResponse {
  predictions: PredictionRow[];
  feature_importance: FeatureImportanceRow[];
  features_by_driver: Record<string, Record<string, number | null>>;
  shap_by_driver: Record<string, ShapContribution[]>;
  // histogram[i] = count of simulations where driver finished P(i+1)
  position_histograms: Record<string, number[]>;
  metadata: {
    race_name: string;
    year: number | null;
    round: number | null;
    sessions_used: string;
    confidence: string;
  };
}

export interface PredictRequestBody {
  year: number;
  race: string | number;
  fp_sessions?: string[];
  skip_news: boolean;
  skip_weather: boolean;
}
