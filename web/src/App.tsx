import { useCallback, useEffect, useState } from "react";
import RaceSelector from "./components/RaceSelector";
import PredictionGrid from "./components/PredictionGrid";
import FeatureImportance from "./components/FeatureImportance";
import { runPrediction } from "./api";
import type { PredictRequestBody, PredictResponse } from "./types";

const ALL_FP = ["FP1", "FP2", "FP3"];
const CURRENT_YEAR = new Date().getFullYear();

export default function App() {
  const [year, setYear] = useState<number>(CURRENT_YEAR);
  const [round, setRound] = useState<number | null>(null);
  const [fpSessions, setFpSessions] = useState<string[]>(ALL_FP);
  const [skipNews, setSkipNews] = useState<boolean>(true);
  const [skipWeather, setSkipWeather] = useState<boolean>(true);

  const [result, setResult] = useState<PredictResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset prediction when the selected race changes
  useEffect(() => {
    setResult(null);
    setError(null);
  }, [year, round]);

  const toggleFp = (sess: string) => {
    setFpSessions((cur) =>
      cur.includes(sess) ? cur.filter((s) => s !== sess) : [...cur, sess],
    );
  };

  const onPredict = useCallback(async () => {
    if (round == null) {
      setError("Select a race first");
      return;
    }
    setLoading(true);
    setError(null);
    const body: PredictRequestBody = {
      year,
      race: round,
      fp_sessions: fpSessions.length ? fpSessions : undefined,
      skip_news: skipNews,
      skip_weather: skipWeather,
    };
    try {
      const data = await runPrediction(body);
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [year, round, fpSessions, skipNews, skipWeather]);

  return (
    <div className="app">
      <header className="app-header">
        <h1>F1 Prediction Dashboard</h1>
        <span className="sub">ML race predictions · feature explainability</span>
      </header>

      <section className="panel">
        <h2>Race</h2>
        <div className="controls">
          <RaceSelector
            year={year}
            round={round}
            onYearChange={(y) => {
              setYear(y);
              setRound(null);
            }}
            onRoundChange={setRound}
          />

          <div className="field">
            <label>FP sessions</label>
            <div className="chips">
              {ALL_FP.map((s) => (
                <span
                  key={s}
                  className={`chip ${fpSessions.includes(s) ? "active" : ""}`}
                  onClick={() => toggleFp(s)}
                >
                  {s}
                </span>
              ))}
            </div>
          </div>

          <div className="field">
            <label>Options</label>
            <label className="toggle">
              <input
                type="checkbox"
                checked={skipNews}
                onChange={(e) => setSkipNews(e.target.checked)}
              />
              Skip news
            </label>
            <label className="toggle">
              <input
                type="checkbox"
                checked={skipWeather}
                onChange={(e) => setSkipWeather(e.target.checked)}
              />
              Skip weather
            </label>
          </div>

          <div className="field">
            <label>&nbsp;</label>
            <button
              className="primary"
              onClick={onPredict}
              disabled={loading || round == null}
            >
              {loading ? (
                <>
                  <span className="spinner" />
                  Predicting…
                </>
              ) : (
                "Run prediction"
              )}
            </button>
          </div>
        </div>
        {error && <div className="error">{error}</div>}
        {loading && (
          <div className="footer-meta" style={{ marginTop: 10 }}>
            <span>
              First call for a race pulls FP data and can take 30–60s. Subsequent
              runs are cached.
            </span>
          </div>
        )}
      </section>

      {result ? (
        <>
          <PredictionGrid result={result} />
          <FeatureImportance result={result} />
        </>
      ) : (
        <section className="panel">
          <div className="empty-state">
            Pick a race above and hit “Run prediction” to populate the dashboard.
          </div>
        </section>
      )}
    </div>
  );
}
