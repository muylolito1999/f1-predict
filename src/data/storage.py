"""SQLite persistence layer for F1 prediction data."""

import sqlite3
import json
from pathlib import Path
from contextlib import contextmanager

import pandas as pd


class Storage:
    """SQLite database for storing F1 data."""

    def __init__(self, db_path: str = "data/f1_predict.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS races (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    round INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    circuit_id TEXT NOT NULL,
                    circuit_name TEXT,
                    country TEXT,
                    date TEXT NOT NULL,
                    latitude REAL,
                    longitude REAL,
                    UNIQUE(year, round)
                );

                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    race_id INTEGER NOT NULL,
                    driver_id TEXT NOT NULL,
                    driver_name TEXT NOT NULL,
                    team TEXT NOT NULL,
                    grid_position INTEGER,
                    finish_position INTEGER,
                    status TEXT,
                    points REAL,
                    laps_completed INTEGER,
                    fastest_lap_time TEXT,
                    fastest_lap_rank INTEGER,
                    FOREIGN KEY (race_id) REFERENCES races(id),
                    UNIQUE(race_id, driver_id)
                );

                CREATE TABLE IF NOT EXISTS fp_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    race_id INTEGER NOT NULL,
                    session_type TEXT NOT NULL,  -- FP1, FP2, FP3
                    driver_id TEXT NOT NULL,
                    driver_name TEXT NOT NULL,
                    team TEXT NOT NULL,
                    best_lap_time REAL,
                    median_lap_time REAL,
                    lap_count INTEGER,
                    consistency_stddev REAL,
                    long_run_pace REAL,
                    long_run_degradation REAL,
                    short_run_pace REAL,
                    sector1_best REAL,
                    sector2_best REAL,
                    sector3_best REAL,
                    speed_trap_max REAL,
                    compound_soft_pace REAL,
                    compound_medium_pace REAL,
                    compound_hard_pace REAL,
                    data_json TEXT,  -- Full session data as JSON
                    FOREIGN KEY (race_id) REFERENCES races(id),
                    UNIQUE(race_id, session_type, driver_id)
                );

                CREATE TABLE IF NOT EXISTS weather (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    race_id INTEGER NOT NULL,
                    session_type TEXT NOT NULL,  -- FP1, FP2, FP3, Q, R
                    air_temp REAL,
                    track_temp REAL,
                    humidity REAL,
                    wind_speed REAL,
                    wind_direction REAL,
                    rain_probability REAL,
                    is_wet INTEGER DEFAULT 0,
                    FOREIGN KEY (race_id) REFERENCES races(id),
                    UNIQUE(race_id, session_type)
                );

                CREATE TABLE IF NOT EXISTS standings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    round INTEGER NOT NULL,
                    driver_id TEXT NOT NULL,
                    driver_name TEXT NOT NULL,
                    team TEXT NOT NULL,
                    points REAL,
                    position INTEGER,
                    wins INTEGER,
                    UNIQUE(year, round, driver_id)
                );

                CREATE TABLE IF NOT EXISTS constructor_standings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL,
                    round INTEGER NOT NULL,
                    team TEXT NOT NULL,
                    points REAL,
                    position INTEGER,
                    wins INTEGER,
                    UNIQUE(year, round, team)
                );

                CREATE TABLE IF NOT EXISTS upgrades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team TEXT NOT NULL,
                    race_id INTEGER,
                    date TEXT NOT NULL,
                    component TEXT,       -- aero/PU/suspension/other
                    impact_score REAL,    -- -1.0 to +1.0
                    confidence TEXT,      -- rumor/confirmed/tested
                    sentiment REAL,       -- -1.0 to +1.0
                    summary TEXT,
                    source_url TEXT,
                    source_name TEXT,
                    FOREIGN KEY (race_id) REFERENCES races(id)
                );

                CREATE TABLE IF NOT EXISTS elo_ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,  -- driver or team
                    entity_id TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    round INTEGER NOT NULL,
                    rating REAL NOT NULL,
                    UNIQUE(entity_type, entity_id, year, round)
                );

                CREATE TABLE IF NOT EXISTS pit_stops (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    race_id INTEGER NOT NULL,
                    driver_id TEXT NOT NULL,
                    stop_number INTEGER,
                    lap INTEGER,
                    duration REAL,
                    FOREIGN KEY (race_id) REFERENCES races(id),
                    UNIQUE(race_id, driver_id, stop_number)
                );

                CREATE TABLE IF NOT EXISTS circuits (
                    circuit_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    country TEXT,
                    latitude REAL,
                    longitude REAL,
                    length_km REAL,
                    corners INTEGER,
                    drs_zones INTEGER,
                    altitude REAL,
                    circuit_type TEXT,  -- street/high_speed/technical/hybrid
                    tyre_stress TEXT,   -- low/medium/high
                    power_sensitivity REAL  -- 0.0 to 1.0
                );
            """)

    def save_race(self, year: int, round_num: int, name: str, circuit_id: str,
                  date: str, circuit_name: str = None, country: str = None,
                  latitude: float = None, longitude: float = None) -> int:
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO races
                (year, round, name, circuit_id, circuit_name, country, date, latitude, longitude)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (year, round_num, name, circuit_id, circuit_name, country,
                  date, latitude, longitude))
            cursor = conn.execute(
                "SELECT id FROM races WHERE year=? AND round=?",
                (year, round_num)
            )
            return cursor.fetchone()[0]

    def save_result(self, race_id: int, driver_id: str, driver_name: str,
                    team: str, grid_position: int, finish_position: int,
                    status: str, points: float, laps_completed: int = None,
                    fastest_lap_time: str = None, fastest_lap_rank: int = None):
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO results
                (race_id, driver_id, driver_name, team, grid_position,
                 finish_position, status, points, laps_completed,
                 fastest_lap_time, fastest_lap_rank)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (race_id, driver_id, driver_name, team, grid_position,
                  finish_position, status, points, laps_completed,
                  fastest_lap_time, fastest_lap_rank))

    def save_fp_session(self, race_id: int, session_type: str, driver_id: str,
                        driver_name: str, team: str, data: dict):
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO fp_sessions
                (race_id, session_type, driver_id, driver_name, team,
                 best_lap_time, median_lap_time, lap_count, consistency_stddev,
                 long_run_pace, long_run_degradation, short_run_pace,
                 sector1_best, sector2_best, sector3_best, speed_trap_max,
                 compound_soft_pace, compound_medium_pace, compound_hard_pace,
                 data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                race_id, session_type, driver_id, driver_name, team,
                data.get("best_lap_time"), data.get("median_lap_time"),
                data.get("lap_count"), data.get("consistency_stddev"),
                data.get("long_run_pace"), data.get("long_run_degradation"),
                data.get("short_run_pace"),
                data.get("sector1_best"), data.get("sector2_best"),
                data.get("sector3_best"), data.get("speed_trap_max"),
                data.get("compound_soft_pace"), data.get("compound_medium_pace"),
                data.get("compound_hard_pace"),
                json.dumps(data)
            ))

    def save_weather(self, race_id: int, session_type: str, data: dict):
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO weather
                (race_id, session_type, air_temp, track_temp, humidity,
                 wind_speed, wind_direction, rain_probability, is_wet)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                race_id, session_type,
                data.get("air_temp"), data.get("track_temp"),
                data.get("humidity"), data.get("wind_speed"),
                data.get("wind_direction"), data.get("rain_probability"),
                data.get("is_wet", 0)
            ))

    def save_standings(self, year: int, round_num: int, driver_id: str,
                       driver_name: str, team: str, points: float,
                       position: int, wins: int):
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO standings
                (year, round, driver_id, driver_name, team, points, position, wins)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (year, round_num, driver_id, driver_name, team,
                  points, position, wins))

    def save_constructor_standing(self, year: int, round_num: int, team: str,
                                  points: float, position: int, wins: int):
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO constructor_standings
                (year, round, team, points, position, wins)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (year, round_num, team, points, position, wins))

    def save_upgrade(self, team: str, date: str, component: str,
                     impact_score: float, confidence: str, sentiment: float,
                     summary: str, source_url: str, source_name: str,
                     race_id: int = None):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO upgrades
                (team, race_id, date, component, impact_score, confidence,
                 sentiment, summary, source_url, source_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (team, race_id, date, component, impact_score, confidence,
                  sentiment, summary, source_url, source_name))

    def save_elo(self, entity_type: str, entity_id: str, year: int,
                 round_num: int, rating: float):
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO elo_ratings
                (entity_type, entity_id, year, round, rating)
                VALUES (?, ?, ?, ?, ?)
            """, (entity_type, entity_id, year, round_num, rating))

    def save_pit_stop(self, race_id: int, driver_id: str, stop_number: int,
                      lap: int, duration: float):
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO pit_stops
                (race_id, driver_id, stop_number, lap, duration)
                VALUES (?, ?, ?, ?, ?)
            """, (race_id, driver_id, stop_number, lap, duration))

    def save_circuit(self, circuit_id: str, name: str, country: str = None,
                     latitude: float = None, longitude: float = None,
                     length_km: float = None, corners: int = None,
                     drs_zones: int = None, altitude: float = None,
                     circuit_type: str = None, tyre_stress: str = None,
                     power_sensitivity: float = None):
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO circuits
                (circuit_id, name, country, latitude, longitude, length_km,
                 corners, drs_zones, altitude, circuit_type, tyre_stress,
                 power_sensitivity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (circuit_id, name, country, latitude, longitude, length_km,
                  corners, drs_zones, altitude, circuit_type, tyre_stress,
                  power_sensitivity))

    # Query methods

    def get_race(self, year: int, round_num: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM races WHERE year=? AND round=?",
                (year, round_num)
            ).fetchone()
            return dict(row) if row else None

    def get_race_id(self, year: int, round_num: int) -> int | None:
        race = self.get_race(year, round_num)
        return race["id"] if race else None

    def get_races_for_season(self, year: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM races WHERE year=? ORDER BY round", (year,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_results(self, race_id: int) -> pd.DataFrame:
        with self._connect() as conn:
            return pd.read_sql_query(
                "SELECT * FROM results WHERE race_id=? ORDER BY finish_position",
                conn, params=(race_id,)
            )

    def get_fp_data(self, race_id: int, session_type: str = None) -> pd.DataFrame:
        with self._connect() as conn:
            if session_type:
                return pd.read_sql_query(
                    "SELECT * FROM fp_sessions WHERE race_id=? AND session_type=?",
                    conn, params=(race_id, session_type)
                )
            return pd.read_sql_query(
                "SELECT * FROM fp_sessions WHERE race_id=?",
                conn, params=(race_id,)
            )

    def get_driver_results_at_circuit(self, driver_id: str,
                                       circuit_id: str,
                                       limit: int = 5,
                                       before_date: str | None = None) -> pd.DataFrame:
        with self._connect() as conn:
            if before_date:
                return pd.read_sql_query("""
                    SELECT r.*, ra.year, ra.round
                    FROM results r
                    JOIN races ra ON r.race_id = ra.id
                    WHERE r.driver_id=? AND ra.circuit_id=? AND ra.date < ?
                    ORDER BY ra.year DESC, ra.round DESC
                    LIMIT ?
                """, conn, params=(driver_id, circuit_id, before_date, limit))
            return pd.read_sql_query("""
                SELECT r.*, ra.year, ra.round
                FROM results r
                JOIN races ra ON r.race_id = ra.id
                WHERE r.driver_id=? AND ra.circuit_id=?
                ORDER BY ra.year DESC, ra.round DESC
                LIMIT ?
            """, conn, params=(driver_id, circuit_id, limit))

    def get_recent_results(self, driver_id: str, limit: int = 5,
                           before_date: str | None = None) -> pd.DataFrame:
        with self._connect() as conn:
            if before_date:
                return pd.read_sql_query("""
                    SELECT r.*, ra.year, ra.round, ra.name as race_name, ra.date as race_date
                    FROM results r
                    JOIN races ra ON r.race_id = ra.id
                    WHERE r.driver_id=? AND ra.date < ?
                    ORDER BY ra.year DESC, ra.round DESC
                    LIMIT ?
                """, conn, params=(driver_id, before_date, limit))
            return pd.read_sql_query("""
                SELECT r.*, ra.year, ra.round, ra.name as race_name, ra.date as race_date
                FROM results r
                JOIN races ra ON r.race_id = ra.id
                WHERE r.driver_id=?
                ORDER BY ra.year DESC, ra.round DESC
                LIMIT ?
            """, conn, params=(driver_id, limit))

    def get_latest_elo(self, entity_type: str, entity_id: str,
                       before_date: str | None = None) -> float:
        with self._connect() as conn:
            if before_date:
                row = conn.execute("""
                    SELECT er.rating
                    FROM elo_ratings er
                    JOIN races ra ON er.year = ra.year AND er.round = ra.round
                    WHERE er.entity_type=? AND er.entity_id=? AND ra.date < ?
                    ORDER BY ra.date DESC
                    LIMIT 1
                """, (entity_type, entity_id, before_date)).fetchone()
            else:
                row = conn.execute("""
                    SELECT rating FROM elo_ratings
                    WHERE entity_type=? AND entity_id=?
                    ORDER BY year DESC, round DESC
                    LIMIT 1
                """, (entity_type, entity_id)).fetchone()
            return row[0] if row else 1500.0

    def get_team_upgrades(self, team: str, before_date: str = None,
                          days_back: int = 14) -> pd.DataFrame:
        with self._connect() as conn:
            if before_date:
                return pd.read_sql_query("""
                    SELECT * FROM upgrades
                    WHERE team=? AND date <= ? AND date >= date(?, '-' || ? || ' days')
                    ORDER BY date DESC
                """, conn, params=(team, before_date, before_date, days_back))
            return pd.read_sql_query(
                "SELECT * FROM upgrades WHERE team=? ORDER BY date DESC",
                conn, params=(team,)
            )

    def get_team_pit_stops(self, team: str, limit: int = 20,
                           before_date: str | None = None) -> pd.DataFrame:
        with self._connect() as conn:
            if before_date:
                return pd.read_sql_query("""
                    SELECT ps.*, r.driver_id, ra.year, ra.round
                    FROM pit_stops ps
                    JOIN results r ON ps.race_id = r.race_id AND ps.driver_id = r.driver_id
                    JOIN races ra ON ps.race_id = ra.id
                    WHERE r.team=? AND ra.date < ?
                    ORDER BY ra.year DESC, ra.round DESC
                    LIMIT ?
                """, conn, params=(team, before_date, limit))
            return pd.read_sql_query("""
                SELECT ps.*, r.driver_id, ra.year, ra.round
                FROM pit_stops ps
                JOIN results r ON ps.race_id = r.race_id AND ps.driver_id = r.driver_id
                JOIN races ra ON ps.race_id = ra.id
                WHERE r.team=?
                ORDER BY ra.year DESC, ra.round DESC
                LIMIT ?
            """, conn, params=(team, limit))

    def get_circuit(self, circuit_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM circuits WHERE circuit_id=?", (circuit_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_weather(self, race_id: int, session_type: str = "R") -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM weather WHERE race_id=? AND session_type=?",
                (race_id, session_type)
            ).fetchone()
            return dict(row) if row else None

    def get_all_drivers_for_season(self, year: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT DISTINCT r.driver_id, r.driver_name, r.team
                FROM results r
                JOIN races ra ON r.race_id = ra.id
                WHERE ra.year=?
            """, (year,)).fetchall()
            return [dict(r) for r in rows]

    def get_standings_before_race(self, year: int, round_num: int) -> pd.DataFrame:
        with self._connect() as conn:
            prev_round = round_num - 1
            if prev_round < 1:
                return pd.DataFrame()
            return pd.read_sql_query("""
                SELECT * FROM standings
                WHERE year=? AND round=?
                ORDER BY position
            """, conn, params=(year, prev_round))

    def get_constructor_standings_before_race(self, year: int,
                                              round_num: int) -> pd.DataFrame:
        with self._connect() as conn:
            prev_round = round_num - 1
            if prev_round < 1:
                return pd.DataFrame()
            return pd.read_sql_query("""
                SELECT * FROM constructor_standings
                WHERE year=? AND round=?
                ORDER BY position
            """, conn, params=(year, prev_round))
