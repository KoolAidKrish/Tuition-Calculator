from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures


@dataclass(slots=True)
class SeriesModel:
    poly: PolynomialFeatures
    model: LinearRegression
    recent_cagr: float
    last_year: int
    last_value: float
    residual_std: float
    origin_year: int


class TuitionForecaster:
    def __init__(self, tuition_history: pd.DataFrame):
        self.tuition_history = tuition_history.copy()
        self.series_models: dict[str, SeriesModel] = {}
        self.min_year = int(self.tuition_history["year"].min())
        self.max_year = int(self.tuition_history["year"].max())

    def fit(self) -> "TuitionForecaster":
        for column in ("tuition_unadjusted", "tuition_adjusted_2025"):
            self.series_models[column] = self._fit_series(column)
        return self

    def _fit_series(self, column: str) -> SeriesModel:
        years = self.tuition_history["year"].to_numpy(dtype=float)
        values = self.tuition_history[column].to_numpy(dtype=float)
        x = (years - self.min_year).reshape(-1, 1)
        poly = PolynomialFeatures(degree=2, include_bias=False)
        x_poly = poly.fit_transform(x)
        model = LinearRegression()
        sample_weights = np.linspace(1.0, 2.75, len(values))
        model.fit(x_poly, np.log(values), sample_weight=sample_weights)

        fitted = np.exp(model.predict(x_poly))
        residual_std = float(np.std(values - fitted, ddof=1))

        lookback = min(10, len(values))
        start_value = values[-lookback]
        end_value = values[-1]
        periods = max(1, lookback - 1)
        recent_cagr = float((end_value / start_value) ** (1 / periods) - 1)
        return SeriesModel(
            poly=poly,
            model=model,
            recent_cagr=recent_cagr,
            last_year=int(years[-1]),
            last_value=float(end_value),
            residual_std=residual_std,
            origin_year=self.min_year,
        )

    def predict_year(self, year: int, column: str) -> dict[str, float]:
        if column not in self.series_models:
            raise ValueError(f"Model for {column} has not been fitted.")

        if year <= self.max_year:
            historical_match = self.tuition_history.loc[
                self.tuition_history["year"] == year, column
            ]
            if not historical_match.empty:
                actual = float(historical_match.iloc[0])
                return {"prediction": actual, "low": actual, "high": actual}

        series_model = self.series_models[column]
        transformed = series_model.poly.transform([[year - series_model.origin_year]])
        curve_projection = float(np.exp(series_model.model.predict(transformed))[0])
        years_ahead = max(0, year - series_model.last_year)
        cagr_projection = series_model.last_value * ((1 + series_model.recent_cagr) ** years_ahead)
        blend_weight = min(0.82, 0.58 + years_ahead * 0.03)
        prediction = blend_weight * curve_projection + (1 - blend_weight) * cagr_projection
        band = series_model.residual_std * (1.0 + years_ahead * 0.08)
        return {
            "prediction": float(prediction),
            "low": float(max(0.0, prediction - 1.28 * band)),
            "high": float(prediction + 1.28 * band),
        }

    def forecast_degree_cost(self, start_year: int, duration_years: int = 4) -> pd.DataFrame:
        rows: list[dict[str, float | int]] = []
        for offset in range(duration_years):
            academic_year = start_year + offset
            nominal = self.predict_year(academic_year, "tuition_unadjusted")
            real_2025 = self.predict_year(academic_year, "tuition_adjusted_2025")
            rows.append(
                {
                    "academic_year": academic_year,
                    "nominal_cost": nominal["prediction"],
                    "nominal_low": nominal["low"],
                    "nominal_high": nominal["high"],
                    "real_2025_cost": real_2025["prediction"],
                    "real_2025_low": real_2025["low"],
                    "real_2025_high": real_2025["high"],
                }
            )

        forecast = pd.DataFrame(rows)
        forecast["cumulative_nominal"] = forecast["nominal_cost"].cumsum()
        forecast["cumulative_real_2025"] = forecast["real_2025_cost"].cumsum()
        return forecast
