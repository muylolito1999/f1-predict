# F1 Prediction Dashboard

Local web UI for the `f1-predict` project. Shows the next-race prediction grid
and the model's feature importance (global + per-driver raw values).

## Stack

- Backend: FastAPI wrapping `src/prediction/pipeline.py`.
- Frontend: React + Vite + TypeScript, Recharts for the bar chart.

## Running locally

Two terminals.

### 1. Backend

```bash
pip install -e .                      # pulls in fastapi + uvicorn
uvicorn src.dashboard.api:app --reload --port 8000
```

Smoke test: `curl http://localhost:8000/api/health` should return `{"status":"ok"}`.

The backend expects a trained model under `models/` and (optionally) historical
data in `data/f1_predict.db`. If the DB has no races for a given year, the
`/api/races` endpoint falls back to the public Jolpica-F1 API.

### 2. Frontend

```bash
cd web
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api/*` to the backend on `:8000`.

## Usage

1. Pick a year and race.
2. Toggle the FP sessions you want the model to use (default: all three).
3. Leave **Skip news** / **Skip weather** checked unless you have valid Azure
   OpenAI / OpenWeatherMap keys in `config.yaml` — the pipeline will run
   without them, it just won't use those features.
4. Hit **Run prediction**. First call for a race pulls FP telemetry from FastF1
   (cached locally) and can take 30–60s.

## What the dashboard shows

- **Prediction grid** — ranked 20-driver table with win / podium / points
  probabilities and a confidence bar. Colors follow canonical team liveries.
- **Feature importance** — horizontal bar chart of the top 20 features driving
  the model's decisions, colored by category (practice / driver / team /
  circuit / weather / strategy / news).
- **Per-driver feature values** — drill into the raw feature vector for any
  driver, grouped by the same categories.

## Cross-checking against the CLI

The dashboard is a thin wrapper around `pipeline.predict_race()` — the same
function the CLI calls. Run:

```bash
f1predict predict --year 2025 --round 1 --skip-news --skip-weather
```

and verify the ranked grid and the footer's "Key factors" line match what the
dashboard shows.
