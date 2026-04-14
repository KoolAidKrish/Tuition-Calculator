from __future__ import annotations

import matplotlib.pyplot as plt


def tuition_figure(tuition_history, forecast_table):
    figure, axis = plt.subplots(figsize=(7.2, 4.0), dpi=110)
    axis.plot(
        tuition_history["year"],
        tuition_history["tuition_unadjusted"],
        color="#6D597A",
        linewidth=2,
        label="Historical annual tuition",
    )
    axis.plot(
        forecast_table["academic_year"],
        forecast_table["nominal_cost"],
        color="#E76F51",
        linewidth=2.5,
        marker="o",
        label="Forecasted future tuition",
    )
    axis.fill_between(
        forecast_table["academic_year"],
        forecast_table["nominal_low"],
        forecast_table["nominal_high"],
        color="#F4A261",
        alpha=0.2,
        label="Forecast range",
    )
    axis.set_title("Engineering Tuition Forecast", fontsize=12, loc="left")
    axis.set_xlabel("Year")
    axis.set_ylabel("CAD")
    axis.grid(alpha=0.2)
    axis.legend(frameon=False, fontsize=8)
    figure.tight_layout()
    return figure


def savings_figure(savings_table, target_value: float):
    figure, axis = plt.subplots(figsize=(7.2, 4.0), dpi=110)
    axis.plot(
        savings_table["month"],
        savings_table["balance"],
        color="#2A9D8F",
        linewidth=2.5,
        label="Projected balance",
    )
    axis.plot(
        savings_table["month"],
        savings_table["total_contributions"],
        color="#264653",
        linewidth=1.6,
        linestyle="--",
        label="Total contributions",
    )
    axis.axhline(target_value, color="#E63946", linestyle=":", linewidth=2, label="Tuition target")
    axis.set_title("Savings Growth vs Tuition Goal", fontsize=12, loc="left")
    axis.set_xlabel("Month")
    axis.set_ylabel("CAD")
    axis.grid(alpha=0.2)
    axis.legend(frameon=False, fontsize=8)
    figure.autofmt_xdate()
    figure.tight_layout()
    return figure


def spending_breakdown_figure(category_summary):
    figure, axis = plt.subplots(figsize=(7.2, 4.0), dpi=110)
    top_categories = category_summary.head(6).sort_values("total_spend")
    axis.barh(top_categories["category"], top_categories["total_spend"], color="#457B9D")
    axis.set_title("Largest Spending Categories", fontsize=12, loc="left")
    axis.set_xlabel("Total spend (CAD)")
    axis.grid(alpha=0.15, axis="x")
    figure.tight_layout()
    return figure


def monthly_spending_figure(monthly_summary):
    figure, axis = plt.subplots(figsize=(7.2, 4.0), dpi=110)
    axis.plot(monthly_summary["month"], monthly_summary["monthly_spend"], color="#BC6C25", linewidth=2.4)
    axis.fill_between(monthly_summary["month"], monthly_summary["monthly_spend"], color="#DDA15E", alpha=0.25)
    axis.set_title("Monthly Spending Trend", fontsize=12, loc="left")
    axis.set_xlabel("Month")
    axis.set_ylabel("CAD")
    axis.grid(alpha=0.2)
    figure.autofmt_xdate()
    figure.tight_layout()
    return figure
