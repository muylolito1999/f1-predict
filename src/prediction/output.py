"""Output formatting for race predictions."""

import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text


console = Console()


def display_prediction(predictions: pd.DataFrame):
    """Display race predictions in a rich formatted table."""
    if predictions.empty:
        console.print("[red]No predictions available[/red]")
        return

    race_name = predictions.iloc[0].get("race_name", "Unknown Race")
    year = predictions.iloc[0].get("year", "")
    sessions = predictions.iloc[0].get("sessions_used", "None")
    confidence = predictions.iloc[0].get("confidence", "UNKNOWN")

    # Create table
    table = Table(
        title=f"{year} {race_name} — Race Prediction",
        show_header=True,
        header_style="bold cyan",
        border_style="bright_blue",
        title_style="bold white on blue",
    )

    table.add_column("P", style="bold", width=4, justify="right")
    table.add_column("Driver", width=18)
    table.add_column("Team", width=14)
    table.add_column("Win %", width=8, justify="right")
    table.add_column("Podium %", width=9, justify="right")
    table.add_column("Points %", width=9, justify="right")
    table.add_column("Confidence", width=12)

    for _, row in predictions.iterrows():
        pos = int(row.get("predicted_position", 0))
        driver = row.get("driver_name", row.get("driver_id", ""))
        team = row.get("team", "")
        win_prob = row.get("win_probability", 0) * 100
        podium_prob = row.get("podium_probability", 0) * 100
        points_prob = row.get("points_probability", 0) * 100

        # Confidence bar
        conf_level = min(6, max(1, int(row.get("ensemble_score", 0.5) * 6)))
        conf_bar = "█" * conf_level + "░" * (6 - conf_level)

        # Color based on position
        if pos <= 3:
            style = "bold green"
        elif pos <= 10:
            style = "yellow"
        else:
            style = "dim"

        table.add_row(
            str(pos),
            driver,
            team,
            f"{win_prob:.1f}%",
            f"{podium_prob:.1f}%",
            f"{points_prob:.1f}%",
            conf_bar,
            style=style,
        )

    console.print()
    console.print(table)

    # Footer with metadata
    footer_parts = [
        f"Sessions analyzed: {sessions}",
        f"Model confidence: {confidence}",
    ]

    # Feature importance if available
    importance = predictions.attrs.get("feature_importance")
    if importance is not None and not importance.empty:
        top_features = importance.head(4)
        total_imp = importance["importance"].sum()
        feat_strs = []
        for _, f in top_features.iterrows():
            pct = (f["importance"] / total_imp * 100) if total_imp > 0 else 0
            feat_strs.append(f"{f['feature']} ({pct:.0f}%)")
        footer_parts.append(f"Key factors: {', '.join(feat_strs)}")

    footer = "\n".join(footer_parts)
    console.print(Panel(footer, title="Info", border_style="dim"))
    console.print()


def display_comparison(predictions: pd.DataFrame, actual: pd.DataFrame = None):
    """Display predictions alongside actual results (for backtesting)."""
    if predictions.empty:
        console.print("[red]No predictions available[/red]")
        return

    table = Table(
        title="Prediction vs Actual",
        show_header=True,
        header_style="bold cyan",
    )

    table.add_column("Pred P", width=7, justify="right")
    table.add_column("Driver", width=18)
    table.add_column("Team", width=14)
    table.add_column("Win %", width=8, justify="right")

    if actual is not None:
        table.add_column("Actual P", width=9, justify="right")
        table.add_column("Delta", width=7, justify="right")

    for _, row in predictions.iterrows():
        pos = int(row.get("predicted_position", 0))
        driver_id = row.get("driver_id", "")
        driver = row.get("driver_name", driver_id)
        team = row.get("team", "")
        win_prob = row.get("win_probability", 0) * 100

        row_data = [str(pos), driver, team, f"{win_prob:.1f}%"]

        if actual is not None:
            actual_row = actual[actual["driver_id"] == driver_id]
            if not actual_row.empty:
                actual_pos = int(actual_row.iloc[0].get("finish_position", 0))
                delta = pos - actual_pos
                delta_str = f"+{delta}" if delta > 0 else str(delta)
                delta_style = "green" if abs(delta) <= 2 else "red"
                row_data.extend([str(actual_pos), f"[{delta_style}]{delta_str}[/{delta_style}]"])
            else:
                row_data.extend(["N/A", "N/A"])

        table.add_row(*row_data)

    console.print(table)


def display_metrics(metrics: dict):
    """Display evaluation metrics."""
    table = Table(title="Model Evaluation Metrics", header_style="bold cyan")

    table.add_column("Metric", width=30)
    table.add_column("Value", width=15, justify="right")

    for key, value in sorted(metrics.items()):
        if isinstance(value, float):
            formatted = f"{value:.4f}"
        else:
            formatted = str(value)

        table.add_row(key, formatted)

    console.print(table)
