from __future__ import annotations

from collections import Counter

import pandas as pd
from sklearn.ensemble import IsolationForest

from tuition_planner.models import SpendingInsights


ESSENTIAL_KEYWORDS = {
    "rent",
    "mortgage",
    "groceries",
    "grocery",
    "insurance",
    "utilities",
    "hydro",
    "electric",
    "water",
    "phone",
    "internet",
    "gas",
    "fuel",
    "transit",
    "medical",
    "pharmacy",
    "tuition",
    "books",
    "childcare",
}
DISCRETIONARY_KEYWORDS = { 
    # Original
    "restaurant", "dining", "coffee", "cafe", "streaming", "entertainment", 
    "shopping", "travel", "vacation", "rideshare", "uber", "lyft", 
    "gaming", "beauty", "subscription", "liquor", "takeout", "delivery",
    
    # Dining & Nightlife
    "bar", "pub", "brewery", "nightclub", "bistro", "bakery", "vending",
    
    # Media & Gaming
    "cinema", "movie", "theater", "concert", "ticket", "nintendo", 
    "playstation", "xbox", "steam", "twitch", "casino",
    
    # Retail & Personal Care
    "apparel", "clothing", "boutique", "jewelry", "salon", "spa", 
    "barber", "makeup", "decor", "gift", "bookstore",
    
    # Travel & Fitness
    "hotel", "airbnb", "airline", "flight", "cruise", "resort", 
    "gym", "fitness", "yoga", "classpass"
}


def classify_essentiality(category: str, description: str) -> str:
    blob = f"{category} {description}".lower()
    if any(keyword in blob for keyword in ESSENTIAL_KEYWORDS):
        return "Essential"
    if any(keyword in blob for keyword in DISCRETIONARY_KEYWORDS):
        return "Non-essential"
    return "Review"


def analyze_spending(
    spending_df: pd.DataFrame,
    monthly_income: float | None = None,
    target_extra_savings: float | None = None,
) -> SpendingInsights:
    df = spending_df.copy()
    if df.empty:
        raise ValueError("No spending transactions were found in the selected file.")

    df["essentiality"] = [
        classify_essentiality(category, description)
        for category, description in zip(df["category"], df["description"])
    ]
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()

    monthly_summary = (
        df.groupby("month", as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "monthly_spend"})
    )
    category_summary = (
        df.groupby(["category", "essentiality"], as_index=False)
        .agg(
            total_spend=("amount", "sum"),
            average_transaction=("amount", "mean"),
            transaction_count=("amount", "count"),
        )
        .sort_values("total_spend", ascending=False)
    )

    features = pd.DataFrame(
        {
            "amount": df["amount"],
            "day": df["date"].dt.day,
            "essential_flag": (df["essentiality"] == "Essential").astype(int),
        }
    )
    model = IsolationForest(random_state=42, contamination=min(0.12, max(0.03, 5 / len(df))))
    anomaly_flags = model.fit_predict(features)
    df["is_anomaly"] = anomaly_flags == -1
    anomalies = df.loc[df["is_anomaly"]].sort_values("amount", ascending=False).head(10)

    subscription_groups = (
        df.assign(
            description_key=df["description"]
            .str.lower()
            .str.replace(r"[^a-z0-9 ]", "", regex=True)
        )
        .groupby("description_key")
        .agg(
            months_present=("month", "nunique"),
            average_amount=("amount", "mean"),
            std_amount=("amount", "std"),
            category=("category", lambda s: Counter(s).most_common(1)[0][0]),
        )
        .reset_index()
    )
    subscriptions = subscription_groups.loc[
        (subscription_groups["months_present"] >= 3)
        & (subscription_groups["average_amount"] > 5)
        & (
            subscription_groups["std_amount"].fillna(0)
            < subscription_groups["average_amount"] * 0.2
        )
    ].sort_values("average_amount", ascending=False)

    monthly_average = float(monthly_summary["monthly_spend"].mean())
    essential_average = float(
        df.loc[df["essentiality"] == "Essential"]
        .groupby("month")["amount"]
        .sum()
        .mean()
        if not df.loc[df["essentiality"] == "Essential"].empty
        else 0.0
    )
    nonessential_average = float(
        df.loc[df["essentiality"] == "Non-essential"]
        .groupby("month")["amount"]
        .sum()
        .mean()
        if not df.loc[df["essentiality"] == "Non-essential"].empty
        else 0.0
    )
    review_average = max(0.0, monthly_average - essential_average - nonessential_average)

    suggested_cut = nonessential_average * 0.2 + review_average * 0.1
    top_categories = category_summary.head(3)
    recommendations = [
        f"Average monthly spending is about ${monthly_average:,.0f}, with roughly ${nonessential_average:,.0f} categorized as discretionary.",
        f"A realistic first cut is ${suggested_cut:,.0f} per month by trimming non-essential categories before touching essentials.",
    ]
    for _, row in top_categories.iterrows():
        if row["essentiality"] != "Essential":
            recommendations.append(
                f"{row['category']} is one of the largest flexible categories at ${row['total_spend']:,.0f} total. A 15-20% trim here would create room for tuition savings."
            )

    if not subscriptions.empty:
        top_subscription = subscriptions.iloc[0]
        recommendations.append(
            f"Recurring charges like {top_subscription['description_key']} may be worth reviewing since they repeat across multiple months."
        )

    if monthly_income:
        current_surplus = monthly_income - monthly_average
        recommendations.append(
            f"With monthly take-home income of ${monthly_income:,.0f}, the current model implies about ${current_surplus:,.0f} of monthly surplus."
        )
        if target_extra_savings and current_surplus < target_extra_savings:
            recommendations.append(
                f"To free up the target ${target_extra_savings:,.0f} per month, the spending plan needs about ${target_extra_savings - current_surplus:,.0f} in additional cuts or income."
            )

    metrics = {
        "monthly_average": monthly_average,
        "essential_average": essential_average,
        "nonessential_average": nonessential_average,
        "review_average": review_average,
        "suggested_cut": suggested_cut,
        "subscriptions_count": int(len(subscriptions)),
        "anomaly_count": int(df["is_anomaly"].sum()),
    }
    return SpendingInsights(
        cleaned_transactions=df,
        category_summary=category_summary,
        monthly_summary=monthly_summary,
        anomalies=anomalies,
        subscriptions=subscriptions,
        recommendations=recommendations,
        metrics=metrics,
    )
