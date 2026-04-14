from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


class ScenarioRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS forecast_scenarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    scenario_name TEXT NOT NULL,
                    target_start_year INTEGER NOT NULL,
                    degree_years INTEGER NOT NULL,
                    starting_balance REAL NOT NULL,
                    monthly_contribution REAL NOT NULL,
                    annual_return REAL NOT NULL,
                    risk_profile TEXT NOT NULL,
                    forecast_total_nominal REAL NOT NULL,
                    forecast_total_real REAL NOT NULL,
                    projected_balance REAL NOT NULL,
                    shortfall REAL NOT NULL,
                    spending_file TEXT,
                    recommendations TEXT
                )
                """
            )

    def save_scenario(self, payload: dict[str, object]) -> None:
        keys = list(payload.keys())
        placeholders = ", ".join(["?"] * len(keys))
        columns = ", ".join(keys)
        values = [payload[key] for key in keys]
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO forecast_scenarios ({columns}) VALUES ({placeholders})",
                values,
            )

    def list_recent_scenarios(self, limit: int = 15) -> pd.DataFrame:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, scenario_name, target_start_year, monthly_contribution,
                       forecast_total_nominal, projected_balance, shortfall, risk_profile
                FROM forecast_scenarios
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return pd.DataFrame([dict(row) for row in rows])

    def get_scenario(self, scenario_id: int) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM forecast_scenarios
                WHERE id = ?
                """,
                (scenario_id,),
            ).fetchone()
        return dict(row) if row else None

    def clear_history(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM forecast_scenarios")
