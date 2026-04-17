"""FastAPI app exposing the F1 prediction pipeline to a web dashboard."""

import logging
from functools import lru_cache
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.cli import load_config
from src.data.storage import Storage
from src.dashboard.serializers import serialize_prediction, serialize_races
from src.features.builder import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

app = FastAPI(title="F1 Prediction Dashboard", version="0.1.0")

# Vite dev server runs on 5173 by default
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_config() -> dict:
    return load_config("config.yaml")


@lru_cache(maxsize=1)
def get_storage() -> Storage:
    cfg = get_config()
    db_path = cfg.get("data", {}).get("db_path", "data/f1_predict.db")
    return Storage(db_path=db_path)


class PredictRequest(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    race: str | int
    fp_sessions: Optional[list[str]] = None
    skip_news: bool = False
    skip_weather: bool = False


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/feature-columns")
def feature_columns() -> dict:
    """Return the ordered list of features the model consumes (for UI grouping)."""
    return {"features": list(FEATURE_COLUMNS)}


@app.get("/api/races")
def list_races(year: int = Query(..., ge=2000, le=2100)) -> dict:
    """Return races for the given year, falling back to Jolpica-F1 if the DB is empty."""
    storage = get_storage()
    races = storage.get_races_for_season(year)

    if not races:
        try:
            from src.data.historical import HistoricalClient
            client = HistoricalClient()
            schedule = client.get_season_races(year)
            races = [
                {
                    "year": year,
                    "round": int(ev.get("round", i + 1)),
                    "name": ev.get("raceName", ev.get("name", "")),
                    "date": ev.get("date", ""),
                    "country": ev.get("Circuit", {}).get("Location", {}).get("country", ""),
                }
                for i, ev in enumerate(schedule or [])
            ]
        except Exception as exc:  # remote API fallback is best-effort
            logger.warning(f"Race schedule fallback failed for {year}: {exc}")
            races = []

    return {"races": serialize_races(races)}


@app.post("/api/predict")
def predict(req: PredictRequest) -> dict:
    """Run the full prediction pipeline and return predictions + explainability data."""
    from src.prediction.pipeline import PredictionPipeline

    storage = get_storage()
    config = get_config()

    # Accept numeric race strings from the UI
    race: str | int = req.race
    if isinstance(race, str):
        try:
            race = int(race)
        except ValueError:
            pass

    pipeline = PredictionPipeline(storage, config)

    try:
        df = pipeline.predict_race(
            year=req.year,
            race=race,
            fp_sessions=req.fp_sessions,
            skip_news=req.skip_news,
            skip_weather=req.skip_weather,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.exception("predict_race failed")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}")

    return serialize_prediction(df)
