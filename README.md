# Tuition Forecasting & Financial Planning Application

A desktop project for forecasting future engineering tuition, stress-testing savings plans, and turning personal nank statement csv's into personalized savings recommendations.

## What It Does

- Loads the provided Alberta engineering tuition history CSV
- Forecasts future annual tuition using a recency-weighted trend model and estimates the full cost of a four-year degree.
- Projects a savings account forward using monthly contributions and a selectable risk/return profile.
- Accepts spending CSV files, auto-detects or manually maps bank-export columns, classifies essential vs non-essential costs, flags anomalous spending, and suggests realistic monthly cuts.
- Embeds dashboards directly in the desktop app with `matplotlib`.
- Saves scenarios to SQLite and exports forecast results to Excel.
- Includes a built-in font-size control for a more readable desktop experience.

## Desktop Experience

- `Planner Dashboard` tab for scenario inputs, forecast charts, tuition tables, and recommendations.
- `Spending Analysis` tab for CSV upload, category dashboards, anomaly detection, and cut recommendations.
- `Scenario History` tab for previously saved runs stored in SQLite.

## Tech Stack

- Python 3.13
- `tkinter`
- `pandas`, `numpy`, `scikit-learn`
- `matplotlib`
- `sqlite3`
- `openpyxl`

## Run It

1. Install dependencies if needed:

```powershell
python -m pip install -r requirements.txt
```

2. Launch the app:

```powershell
python app.py
```

Or double-click `Launch Tuition Planner.bat`.

## Modeling Notes

- The tuition forecaster blends a polynomial regression curve with recent compound annual growth rates to keep long-range forecasts realistic.
- Degree cost is modeled as a four-year path, not a single flat-year estimate, so each academic year can inflate separately.
- The default `TD-style basic savings` profile is intentionally conservative and can be overridden in the GUI.
- Spending analysis uses keyword-based essentiality classification plus `IsolationForest` anomaly detection to surface unusual or high-impact transactions.

## Project Files

- `EngineeringTuitionData.csv`: historical tuition data source
- `data/sample_spending.csv`: demo spending file
- `data/tuition_planner.db`: SQLite database created on first run
- `exports/`: generated Excel workbooks
- `tuition_planner/`: forecasting, analytics, export, persistence, and GUI code

## Reference Data

- Tuition history comes from the local CSV already in this folder.
- The conservative baseline savings profile is modeled after a basic TD-style savings setup and is intended as a starting assumption, not financial advice.
