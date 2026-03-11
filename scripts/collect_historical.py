"""One-time historical data collection script.

Usage:
    python scripts/collect_historical.py --seasons 2022 2023 2024 2025
"""

import argparse
import logging
import sys

sys.path.insert(0, ".")

from src.data.storage import Storage
from src.data.historical import HistoricalClient
from src.data.fastf1_client import FastF1Client
from src.features.driver import update_elo
from src.features.team import update_team_elo


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Collect historical F1 data")
    parser.add_argument(
        "--seasons", nargs="+", type=int, required=True,
        help="Seasons to collect (e.g., 2022 2023 2024 2025)"
    )
    parser.add_argument(
        "--db-path", default="data/f1_predict.db",
        help="SQLite database path"
    )
    parser.add_argument(
        "--cache-dir", default="data/cache",
        help="FastF1 cache directory"
    )
    parser.add_argument(
        "--skip-fastf1", action="store_true",
        help="Skip FastF1 data collection (API-only)"
    )
    args = parser.parse_args()

    storage = Storage(db_path=args.db_path)

    # Step 1: Collect race results and standings from Jolpica-F1 API
    logger.info("=== Phase 1: Historical results from Jolpica-F1 API ===")
    historical = HistoricalClient()
    for year in sorted(args.seasons):
        logger.info(f"Collecting {year} from Jolpica-F1...")
        try:
            historical.collect_season(year, storage)
        except Exception as e:
            logger.error(f"Failed to collect {year}: {e}")

    # Step 2: Collect FP session data from FastF1
    if not args.skip_fastf1:
        logger.info("=== Phase 2: FP session data from FastF1 ===")
        fastf1 = FastF1Client(cache_dir=args.cache_dir)
        for year in sorted(args.seasons):
            logger.info(f"Collecting {year} FP data from FastF1...")
            try:
                fastf1.collect_season(year, storage)
            except Exception as e:
                logger.error(f"Failed FastF1 collection for {year}: {e}")

    # Step 3: Compute Elo ratings
    logger.info("=== Phase 3: Computing Elo ratings ===")
    for year in sorted(args.seasons):
        races = storage.get_races_for_season(year)
        for race in races:
            try:
                update_elo(storage, race["id"], year, race["round"])
                update_team_elo(storage, race["id"], year, race["round"])
            except Exception as e:
                logger.debug(f"Elo update error for {year} R{race['round']}: {e}")

    logger.info("=== Data collection complete ===")

    # Summary
    for year in args.seasons:
        races = storage.get_races_for_season(year)
        logger.info(f"  {year}: {len(races)} races stored")


if __name__ == "__main__":
    main()
