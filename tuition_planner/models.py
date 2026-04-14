from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(slots=True)
class SavingsProfile:
    name: str
    annual_return: float
    annual_volatility: float
    description: str
    provider_reference: str = ""


@dataclass(slots=True)
class ForecastBundle:
    summary: dict[str, Any]
    tuition_table: pd.DataFrame
    savings_schedule: pd.DataFrame
    recommendations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SpendingInsights:
    cleaned_transactions: pd.DataFrame
    category_summary: pd.DataFrame
    monthly_summary: pd.DataFrame
    anomalies: pd.DataFrame
    subscriptions: pd.DataFrame
    recommendations: list[str]
    metrics: dict[str, Any]
