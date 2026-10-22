"""
EDA for the Bangalore traffic dataset (Member B).

Run from the repo root (the traffic-mlops folder, with venv active):
    python notebooks/eda.py

It prints the dataset summary and saves six plots as PNG files in notebooks/:
traffic volume by day of week, by area, by weather, by month, a numeric
correlation heatmap, and a traffic volume distribution histogram. It saves
all printed text to
notebooks/eda_summary.txt.
"""
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save plots to files, no windows pop up
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

DATA_PATH = Path("data/raw/bangalore_traffic.csv")
OUT_DIR = Path("notebooks")

# Real column names (checked against the file)
DATE = "Date"
AREA = "Area Name"
ROAD = "Road/Intersection Name"
VOLUME = "Traffic Volume"
WEATHER = "Weather Conditions"
ROADWORK = "Roadwork and Construction Activity"

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]


def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def run() -> None:
    if not DATA_PATH.exists():
        sys.exit(f"Cannot find {DATA_PATH}. Run this from the repo root "
                 "and make sure `dvc pull` has finished.")
    OUT_DIR.mkdir(exist_ok=True)

    df = pd.read_csv(DATA_PATH)
    raw_rows, raw_columns = df.shape
    df[DATE] = pd.to_datetime(df[DATE], errors="raise")
    df["day_of_week"] = df[DATE].dt.day_name()
    df["month"] = df[DATE].dt.month
    df["is_weekend"] = df[DATE].dt.dayofweek >= 5

    # ------------------------------------------------------------------
    section("1. BASIC INFO")
    print(f"Raw dataset rows: {raw_rows}   Raw dataset columns: {raw_columns}")
    print(f"EDA working-table columns (including 3 added calendar fields): {df.shape[1]}")
    print(f"Date range: {df[DATE].min().date()} to {df[DATE].max().date()}")
    print(f"Distinct dates: {df[DATE].nunique()}")
    expected_days = (df[DATE].max() - df[DATE].min()).days + 1
    print(f"Missing dates in daily range: {expected_days - df[DATE].nunique()}")
    print(f"Distinct areas: {df[AREA].nunique()}")
    print(f"Distinct roads/intersections: {df[ROAD].nunique()}")
    print("\nColumn data types:")
    print(df.dtypes.to_string())

    section("2. UNIQUE VALUES")
    print(df.nunique(dropna=False).to_string())

    # ------------------------------------------------------------------
    section("3. DATA QUALITY")
    print("Missing values per column:")
    print(df.isnull().sum().to_string())
    print(f"\nDuplicate rows: {df.duplicated().sum()}")
    print(f"Duplicate (Date, Road) pairs: "
          f"{df.duplicated(subset=[DATE, ROAD]).sum()}")

    # ------------------------------------------------------------------
    section("4. TRAFFIC VOLUME SUMMARY")
    print(df[VOLUME].describe().round(1).to_string())
    q1, q3 = df[VOLUME].quantile(0.25), df[VOLUME].quantile(0.75)
    iqr = q3 - q1
    low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    n_out = ((df[VOLUME] < low) | (df[VOLUME] > high)).sum()
    print(f"\nIQR outlier bounds: {low:.0f} to {high:.0f}")
    print(f"Rows outside bounds: {n_out} ({n_out / len(df) * 100:.2f}%)")

    section("5. ALL NUMERIC COLUMNS (describe)")
    print(df.select_dtypes(include="number").describe().round(2).T.to_string())

    # ------------------------------------------------------------------
    section("6. ROWS PER AREA")
    area_counts = df[AREA].value_counts()
    print(pd.DataFrame({
        "rows": area_counts,
        "percent": (area_counts / len(df) * 100).round(1),
    }).to_string())

    section("7. WEATHER")
    w_counts = df[WEATHER].value_counts()
    print(pd.DataFrame({
        "rows": w_counts,
        "percent": (w_counts / len(df) * 100).round(1),
    }).to_string())
    print("\nAverage Traffic Volume by weather:")
    print(df.groupby(WEATHER)[VOLUME].mean().round(0)
          .sort_values(ascending=False).to_string())

    section("8. ROADWORK")
    r_counts = df[ROADWORK].value_counts()
    print(pd.DataFrame({
        "rows": r_counts,
        "percent": (r_counts / len(df) * 100).round(1),
    }).to_string())
    print("\nAverage Traffic Volume by roadwork:")
    print(df.groupby(ROADWORK)[VOLUME].mean().round(0).to_string())

    # ------------------------------------------------------------------
    section("9. DAY OF WEEK AND WEEKEND vs WEEKDAY")
    dow = (df.groupby("day_of_week")[VOLUME].mean()
           .reindex(DAY_ORDER).round(0))
    print(dow.to_string())
    wk = df.loc[~df["is_weekend"], VOLUME].mean()
    we = df.loc[df["is_weekend"], VOLUME].mean()
    diff = (we - wk) / wk * 100
    print(f"\nWeekday average: {wk:.0f}")
    print(f"Weekend average: {we:.0f}")
    print(f"Weekend vs weekday: {diff:+.1f}%")

    section("10. AVERAGE VOLUME BY AREA")
    area_avg = (df.groupby(AREA)[VOLUME].mean()
                .sort_values(ascending=False).round(0))
    print(area_avg.to_string())

    section("11. AVERAGE VOLUME BY MONTH")
    month_avg = df.groupby("month")[VOLUME].mean().round(0)
    print(month_avg.to_string())

    section("12. CORRELATION WITH TRAFFIC VOLUME")
    corr = df.select_dtypes(include="number").corr()
    print(corr[VOLUME].drop(VOLUME).sort_values(ascending=False)
          .round(3).to_string())
    print("\nNote: columns measured at the same time as volume (speed, "
          "congestion, capacity use, etc.) must NOT be model inputs.")

    # ------------------------------------------------------------------
    # PLOTS
    # ------------------------------------------------------------------
    plt.figure(figsize=(10, 5))
    sns.barplot(x=dow.index, y=dow.values, order=DAY_ORDER, color="#4C72B0")
    plt.title("Average Traffic Volume by Day of Week")
    plt.ylabel("Average Traffic Volume")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "plot_day_of_week.png", dpi=150)
    plt.close()

    plt.figure(figsize=(10, 5))
    area_avg.plot(kind="bar", color="#55A868")
    plt.title("Average Traffic Volume by Area")
    plt.ylabel("Average Traffic Volume")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "plot_area.png", dpi=150)
    plt.close()

    plt.figure(figsize=(10, 5))
    order = df.groupby(WEATHER)[VOLUME].median().sort_values().index
    sns.boxplot(data=df, x=WEATHER, y=VOLUME, order=order)
    plt.title("Traffic Volume Distribution by Weather")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(OUT_DIR / "plot_weather.png", dpi=150)
    plt.close()

    plt.figure(figsize=(11, 9))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm",
                annot_kws={"size": 7})
    plt.title("Correlation Between Numeric Columns")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "plot_correlation.png", dpi=150)
    plt.close()

    plt.figure(figsize=(10, 5))
    sns.barplot(x=month_avg.index, y=month_avg.values, color="#C44E52")
    plt.title("Average Traffic Volume by Month")
    plt.xlabel("Month")
    plt.ylabel("Average Traffic Volume")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "plot_month.png", dpi=150)
    plt.close()

    plt.figure(figsize=(10, 5))
    sns.histplot(df[VOLUME], bins=30, color="#4C72B0", edgecolor="white")
    plt.title("Traffic Volume Distribution")
    plt.xlabel("Traffic Volume")
    plt.ylabel("Number of observations")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "plot_traffic_volume_distribution.png", dpi=150)
    plt.close()

    print("\nSaved plots: plot_day_of_week.png, plot_area.png, "
          "plot_weather.png, plot_correlation.png, plot_month.png, "
          "plot_traffic_volume_distribution.png")


if __name__ == "__main__":
    # Print to screen AND save everything printed to a text file.
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run()
    text = buffer.getvalue()
    print(text)
    OUT_DIR.mkdir(exist_ok=True)
    (OUT_DIR / "eda_summary.txt").write_text(text, encoding="utf-8")
    print("Saved numbers to notebooks/eda_summary.txt")
