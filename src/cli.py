"""CLI entry point for F1 race prediction system."""

import logging
import os
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv

from src.data.storage import Storage


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration, resolving environment variables."""
    load_dotenv()
    path = Path(config_path)
    if not path.exists():
        return {}

    with open(path) as f:
        config = yaml.safe_load(f) or {}

    # Resolve env vars in string values
    def resolve_env(obj):
        if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            var_name = obj[2:-1]
            return os.environ.get(var_name, "")
        elif isinstance(obj, dict):
            return {k: resolve_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [resolve_env(v) for v in obj]
        return obj

    return resolve_env(config)


@click.group()
@click.option("--config", default="config.yaml", help="Path to config file")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(ctx, config, verbose):
    """F1 Race Prediction System — ML-powered race winner predictions."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config)
    ctx.obj["storage"] = Storage(
        db_path=ctx.obj["config"].get("data", {}).get("db_path", "data/f1_predict.db")
    )


@cli.command("collect-history")
@click.option("--seasons", "-s", multiple=True, type=int, required=True,
              help="Seasons to collect (e.g., -s 2022 -s 2023)")
@click.option("--source", type=click.Choice(["fastf1", "jolpica", "both"]),
              default="both", help="Data source to use")
@click.pass_context
def collect_history(ctx, seasons, source):
    """Collect historical race data for training."""
    storage = ctx.obj["storage"]

    if source in ("jolpica", "both"):
        from src.data.historical import HistoricalClient
        client = HistoricalClient()
        for year in seasons:
            click.echo(f"Collecting {year} from Jolpica-F1 API...")
            client.collect_season(year, storage)

    if source in ("fastf1", "both"):
        from src.data.fastf1_client import FastF1Client
        config = ctx.obj["config"]
        client = FastF1Client(
            cache_dir=config.get("data", {}).get("cache_dir", "data/cache")
        )
        for year in seasons:
            click.echo(f"Collecting {year} FP data from FastF1...")
            client.collect_season(year, storage)

    click.echo("Data collection complete.")


@cli.command("train")
@click.option("--seasons", "-s", multiple=True, type=int, required=True,
              help="Seasons to train on")
@click.option("--validate", "-val", type=int, default=None,
              help="Season to hold out for validation")
@click.pass_context
def train(ctx, seasons, validate):
    """Train ML models on historical data."""
    from src.models.trainer import Trainer
    from src.prediction.output import display_metrics

    storage = ctx.obj["storage"]
    config = ctx.obj["config"]

    trainer = Trainer(
        storage,
        model_dir=config.get("model", {}).get("save_dir", "models")
    )

    click.echo(f"Training on seasons: {list(seasons)}")
    if validate:
        click.echo(f"Validation season: {validate}")

    metrics = trainer.train(list(seasons), validation_season=validate)

    if "error" in metrics:
        click.echo(f"Training failed: {metrics['error']}", err=True)
        raise SystemExit(1)

    display_metrics(metrics)
    click.echo("Training complete. Models saved.")


@cli.command("predict")
@click.option("--race", "-r", required=True,
              help="Race name or round number (e.g., 'Bahrain' or 1)")
@click.option("--year", "-y", type=int, required=True, help="Season year")
@click.option("--sessions", "-fp", multiple=True,
              help="FP sessions to use (e.g., -fp FP1 -fp FP2)")
@click.option("--skip-news", is_flag=True, help="Skip news scraping")
@click.option("--skip-weather", is_flag=True, help="Skip weather forecast")
@click.pass_context
def predict(ctx, race, year, sessions, skip_news, skip_weather):
    """Predict race results for a specific race."""
    from src.prediction.pipeline import PredictionPipeline
    from src.prediction.output import display_prediction

    storage = ctx.obj["storage"]
    config = ctx.obj["config"]

    pipeline = PredictionPipeline(storage, config)

    # Parse race as int if possible
    try:
        race = int(race)
    except ValueError:
        pass

    fp_sessions = list(sessions) if sessions else None

    try:
        predictions = pipeline.predict_race(
            year=year,
            race=race,
            fp_sessions=fp_sessions,
            skip_news=skip_news,
            skip_weather=skip_weather,
        )

        display_prediction(predictions)

    except Exception as e:
        click.echo(f"Prediction failed: {e}", err=True)
        logging.getLogger().debug("Full traceback:", exc_info=True)
        raise SystemExit(1)


@cli.command("backtest")
@click.option("--season", "-s", type=int, required=True,
              help="Season to backtest on")
@click.option("--train-seasons", "-ts", multiple=True, type=int,
              help="Seasons to train on (default: all before backtest season)")
@click.pass_context
def backtest(ctx, season, train_seasons):
    """Backtest model predictions against actual race results."""
    from scripts.backtest import run_backtest

    storage = ctx.obj["storage"]
    config = ctx.obj["config"]

    if not train_seasons:
        train_seasons = list(range(2022, season))

    run_backtest(storage, config, list(train_seasons), season)


@cli.command("explain")
@click.pass_context
def explain(ctx):
    """Show model feature importances."""
    from src.models.trainer import Trainer
    from src.features.builder import FEATURE_COLUMNS
    from rich.console import Console
    from rich.table import Table

    storage = ctx.obj["storage"]
    config = ctx.obj["config"]
    console = Console()

    trainer = Trainer(
        storage,
        model_dir=config.get("model", {}).get("save_dir", "models")
    )
    trainer.load_models()

    for name, model in [("XGBoost", trainer.xgb_model),
                         ("LightGBM", trainer.lgb_model)]:
        importance = model.get_feature_importance(FEATURE_COLUMNS)
        if importance.empty:
            continue

        total = importance["importance"].sum()

        table = Table(title=f"{name} Feature Importance", header_style="bold cyan")
        table.add_column("Rank", width=5, justify="right")
        table.add_column("Feature", width=35)
        table.add_column("Importance", width=12, justify="right")
        table.add_column("% Total", width=10, justify="right")
        table.add_column("Bar", width=20)

        for i, (_, row) in enumerate(importance.head(20).iterrows()):
            pct = (row["importance"] / total * 100) if total > 0 else 0
            bar_len = int(pct / 2)
            bar = "█" * bar_len + "░" * (10 - bar_len)
            table.add_row(
                str(i + 1),
                row["feature"],
                f"{row['importance']:.4f}",
                f"{pct:.1f}%",
                bar,
            )

        console.print(table)
        console.print()


if __name__ == "__main__":
    cli()
