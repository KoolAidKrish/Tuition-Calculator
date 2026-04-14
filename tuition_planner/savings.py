from __future__ import annotations

from datetime import date

import pandas as pd

from tuition_planner.models import SavingsProfile


TD_REFERENCE_URL = "https://www.td.com/ca/en/personal-banking/products/bank-accounts/account-rates"


DEFAULT_PROFILES: dict[str, SavingsProfile] = {
    "TD-style basic savings": SavingsProfile(
        name="TD-style basic savings",
        annual_return=0.0001,
        annual_volatility=0.002,
        description="Ultra-conservative baseline modeled after a basic daily-interest savings account.",
        provider_reference=TD_REFERENCE_URL,
    ),
    "Conservative GIC ladder": SavingsProfile(
        name="Conservative GIC ladder",
        annual_return=0.025,
        annual_volatility=0.01,
        description="Low-risk education savings strategy for users prioritizing capital preservation.",
    ),
    "Balanced portfolio": SavingsProfile(
        name="Balanced portfolio",
        annual_return=0.045,
        annual_volatility=0.08,
        description="Moderate-risk mix for longer time horizons where modest market exposure is acceptable.",
    ),
    "Growth portfolio": SavingsProfile(
        name="Growth portfolio",
        annual_return=0.065,
        annual_volatility=0.14,
        description="Higher expected return for users comfortable with market variability.",
    ),
}


def get_profile(name: str) -> SavingsProfile:
    return DEFAULT_PROFILES.get(name, DEFAULT_PROFILES["TD-style basic savings"])


def future_value_schedule(
    start_balance: float,
    monthly_contribution: float,
    annual_return: float,
    start_date: date,
    target_date: date,
) -> pd.DataFrame:
    if target_date <= start_date:
        raise ValueError("Target date must be after the current date.")

    periods = pd.period_range(start=start_date, end=target_date, freq="M")
    monthly_rate = annual_return / 12
    balance = float(start_balance)
    total_contributions = float(start_balance)
    rows: list[dict[str, float | str]] = []

    for period in periods:
        interest_earned = balance * monthly_rate
        balance += interest_earned + monthly_contribution
        total_contributions += monthly_contribution
        rows.append(
            {
                "month": period.to_timestamp(),
                "contribution": monthly_contribution,
                "interest_earned": interest_earned,
                "balance": balance,
                "total_contributions": total_contributions,
            }
        )
    return pd.DataFrame(rows)


def required_monthly_contribution(
    target_value: float,
    annual_return: float,
    months: int,
    current_balance: float = 0.0,
) -> float:
    if months <= 0:
        return max(0.0, target_value - current_balance)

    monthly_rate = annual_return / 12
    future_value_of_current = current_balance * ((1 + monthly_rate) ** months)
    remaining_goal = max(0.0, target_value - future_value_of_current)
    if monthly_rate == 0:
        return remaining_goal / months

    factor = (((1 + monthly_rate) ** months) - 1) / monthly_rate
    if factor == 0:
        return remaining_goal / months
    return remaining_goal / factor


def build_savings_recommendations(
    goal_value: float,
    projected_balance: float,
    required_monthly: float,
    actual_monthly: float,
    annual_return: float,
) -> list[str]:
    gap = goal_value - projected_balance
    messages: list[str] = []
    if gap > 0:
        messages.append(
            f"Projected savings fall short by ${gap:,.0f}. Raising monthly savings to about ${required_monthly:,.0f} closes the gap."
        )
        messages.append(
            f"At the current return assumption of {annual_return * 100:.2f}% APR, every extra $100 saved per month meaningfully reduces the shortfall."
        )
    else:
        messages.append(
            f"The plan reaches the goal with an estimated surplus of ${abs(gap):,.0f}, which creates a buffer for tuition inflation."
        )
        messages.append(
            "If you want more flexibility, you could reduce monthly savings slightly and still remain on track."
        )

    if actual_monthly == 0:
        messages.append(
            "No monthly savings contribution is currently modeled, so the tuition target depends entirely on the starting balance."
        )
    return messages
