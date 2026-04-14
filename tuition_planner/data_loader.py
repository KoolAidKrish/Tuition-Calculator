from __future__ import annotations

from pathlib import Path

import pandas as pd


TUITION_COLUMNS = [
    "year",
    "tuition_unadjusted",
    "tuition_adjusted_2025",
]

DATE_ALIASES = {
    "date",
    "transaction_date",
    "posted_date",
    "purchase_date",
    "post_date",
    "posted",
    "trans_date",
}
AMOUNT_ALIASES = {
    "amount",
    "debit",
    "expense",
    "value",
    "transaction_amount",
    "spending_amount",
    "spent",
    "withdrawal",
    "charge",
    "debits",
}
BALANCE_ALIASES = {
    "balance",
    "account_balance",
    "running_balance",
    "available_balance",
    "total_account_amount",
    "total_balance",
    "current_balance",
}
CATEGORY_ALIASES = {"category", "type", "merchant_category", "spend_category"}
DESCRIPTION_ALIASES = {
    "description",
    "merchant",
    "details",
    "memo",
    "name",
    "payee",
    "transaction",
    "narrative",
    "reference",
}

SPENDING_REQUIRED_FIELDS = ("date", "description", "amount")


def _normalize_name(name: str) -> str:
    return (
        str(name)
        .strip()
        .lower()
        .replace("(", "")
        .replace(")", "")
        .replace("/", "_")
        .replace("-", "_")
        .replace(" ", "_")
    )


def _coerce_money(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("CAD", "", regex=False)
        .str.replace("cad", "", regex=False)
        .str.replace("(", "-", regex=False)
        .str.replace(")", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _non_null_ratio(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    return float(series.notna().mean())


def _datetime_ratio(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    parsed = pd.to_datetime(series, errors="coerce", format="mixed")
    return float(parsed.notna().mean())


def _numeric_ratio(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    parsed = _coerce_money(series)
    return float(parsed.notna().mean())


def _text_ratio(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    as_text = series.astype(str).str.strip()
    return float((as_text != "").mean())


def _score_date_column(column_name: str, series: pd.Series) -> float:
    normalized = _normalize_name(column_name)
    score = _datetime_ratio(series) * 4
    if normalized in DATE_ALIASES:
        score += 4
    if "date" in normalized:
        score += 2
    return score


def _score_description_column(column_name: str, series: pd.Series) -> float:
    normalized = _normalize_name(column_name)
    score = _text_ratio(series)
    if normalized in DESCRIPTION_ALIASES:
        score += 4
    if "desc" in normalized or "merchant" in normalized or "memo" in normalized:
        score += 2
    if _numeric_ratio(series) < 0.35:
        score += 1
    return score


def _score_category_column(column_name: str, series: pd.Series) -> float:
    normalized = _normalize_name(column_name)
    score = _text_ratio(series)
    if normalized in CATEGORY_ALIASES:
        score += 4
    if "category" in normalized or normalized == "type":
        score += 2
    return score


def _score_amount_column(column_name: str, series: pd.Series) -> float:
    normalized = _normalize_name(column_name)
    score = _numeric_ratio(series) * 4
    if normalized in AMOUNT_ALIASES:
        score += 5
    if (
        "amount" in normalized
        or "debit" in normalized
        or "spent" in normalized
        or "withdraw" in normalized
    ):
        score += 2
    return score


def _score_balance_column(column_name: str, series: pd.Series) -> float:
    normalized = _normalize_name(column_name)
    score = _numeric_ratio(series) * 4
    if normalized in BALANCE_ALIASES:
        score += 5
    if "balance" in normalized or "account" in normalized:
        score += 2
    return score


def _choose_best_column(
    df: pd.DataFrame,
    scorer,
    used: set[str],
    minimum_score: float,
) -> str | None:
    candidates: list[tuple[float, str]] = []
    for column in df.columns:
        if column in used:
            continue
        score = scorer(column, df[column])
        candidates.append((score, column))
    if not candidates:
        return None
    best_score, best_column = max(candidates, key=lambda item: item[0])
    return best_column if best_score >= minimum_score else None


def _derive_category(description: str) -> str:
    text = str(description).strip()
    if not text:
        return "Uncategorized"
    separators = [" - ", " / ", "  ", ","]
    for separator in separators:
        if separator in text:
            text = text.split(separator)[0]
            break
    words = [word for word in text.split() if word]
    if not words:
        return "Uncategorized"
    return " ".join(words[:2]).title()


def load_tuition_history(csv_path: str | Path) -> pd.DataFrame:
    path = Path(csv_path)
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    header_row = next(
        (index for index, line in enumerate(lines) if line.strip().startswith("Year,")),
        None,
    )
    if header_row is None:
        raise ValueError("Could not find the tuition header row in the CSV.")

    df = pd.read_csv(path, skiprows=header_row)
    df = df.iloc[:, :3].copy()
    df.columns = TUITION_COLUMNS
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    for column in TUITION_COLUMNS[1:]:
        df[column] = pd.to_numeric(
            df[column].astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        )
    df = df.dropna().sort_values("year").reset_index(drop=True)
    df["year"] = df["year"].astype(int)
    df["unadjusted_yoy"] = df["tuition_unadjusted"].pct_change().fillna(0.0)
    df["adjusted_yoy"] = df["tuition_adjusted_2025"].pct_change().fillna(0.0)
    return df


def load_spending_preview(csv_path: str | Path, rows: int = 8) -> pd.DataFrame:
    return pd.read_csv(Path(csv_path)).head(rows)


def infer_spending_columns(
    df_or_columns: pd.DataFrame | list[str],
) -> dict[str, str]:
    if isinstance(df_or_columns, pd.DataFrame):
        df = df_or_columns.copy()
    else:
        df = pd.DataFrame(columns=df_or_columns)

    mapping: dict[str, str] = {}
    used: set[str] = set()

    date_column = _choose_best_column(df, _score_date_column, used, minimum_score=2.5)
    if date_column:
        mapping["date"] = date_column
        used.add(date_column)

    amount_column = _choose_best_column(
        df, _score_amount_column, used, minimum_score=2.5
    )
    if amount_column:
        mapping["amount"] = amount_column
        used.add(amount_column)

    balance_column = _choose_best_column(
        df, _score_balance_column, used, minimum_score=2.5
    )
    if balance_column:
        mapping["balance"] = balance_column
        used.add(balance_column)

    description_column = _choose_best_column(
        df, _score_description_column, used, minimum_score=1.5
    )
    if description_column:
        mapping["description"] = description_column
        used.add(description_column)

    category_column = _choose_best_column(
        df, _score_category_column, used, minimum_score=2.0
    )
    if category_column:
        mapping["category"] = category_column

    return mapping


def normalize_spending_columns(
    df: pd.DataFrame,
    column_mapping: dict[str, str] | None = None,
) -> pd.DataFrame:
    mapping = infer_spending_columns(df)
    if column_mapping:
        mapping.update(
            {
                field: column_name
                for field, column_name in column_mapping.items()
                if column_name and column_name in df.columns
            }
        )

    missing_fields = [
        field
        for field in SPENDING_REQUIRED_FIELDS
        if field not in mapping or mapping[field] not in df.columns
    ]
    if missing_fields:
        raise ValueError(
            "Unable to confidently identify the spending CSV columns for "
            + ", ".join(missing_fields)
            + ". Use the manual column mapping option to assign them."
        )

    renamed = df.rename(columns={value: key for key, value in mapping.items()}).copy()
    if "description" not in renamed:
        renamed["description"] = "Unspecified"
    if "category" not in renamed:
        renamed["category"] = renamed["description"].map(_derive_category)
    else:
        renamed["category"] = renamed["category"].fillna("").astype(str)
        fallback_mask = renamed["category"].str.strip() == ""
        renamed.loc[fallback_mask, "category"] = renamed.loc[
            fallback_mask, "description"
        ].map(_derive_category)
    if "balance" not in renamed:
        renamed["balance"] = pd.NA

    cleaned = renamed[["date", "description", "amount", "balance", "category"]].copy()
    cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce", format="mixed")
    cleaned["description"] = cleaned["description"].fillna("Unspecified").astype(str)
    cleaned["amount"] = _coerce_money(cleaned["amount"]).abs()
    cleaned["balance"] = _coerce_money(cleaned["balance"])
    cleaned["category"] = cleaned["category"].fillna("Uncategorized").astype(str)
    cleaned = cleaned.dropna(subset=["date", "amount"])
    cleaned["month"] = cleaned["date"].dt.to_period("M").dt.to_timestamp()
    cleaned["day_of_week"] = cleaned["date"].dt.day_name()
    return cleaned.sort_values("date").reset_index(drop=True)


def load_spending_history(
    csv_path: str | Path,
    column_mapping: dict[str, str] | None = None,
) -> pd.DataFrame:
    path = Path(csv_path)
    df = pd.read_csv(path)
    return normalize_spending_columns(df, column_mapping=column_mapping)
