from pathlib import Path
from math import isfinite

import holidays
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "bangalore_traffic.csv"
EVENTS_PATH = PROJECT_ROOT / "src" / "features" / "bangalore_events.csv"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "traffic_features.csv"


def load_raw(path: Path) -> pd.DataFrame:
    """Load the raw Bangalore traffic dataset."""
    df = pd.read_csv(path)

    df["Date"] = pd.to_datetime(df["Date"], errors="raise")

    print("Dataset loaded successfully.")
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")

    return df


def validate_columns(df: pd.DataFrame) -> None:
    """Check that required raw dataset columns are present."""

    required_columns = [
        "Date",
        "Area Name",
        "Road/Intersection Name",
        "Traffic Volume",
        "Weather Conditions",
        "Roadwork and Construction Activity",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    print("\nColumn validation: PASSED")


def validate_required_values(df: pd.DataFrame) -> None:
    """Reject invalid values in fields required by the feature pipeline."""
    required = [
        "Date",
        "Area Name",
        "Road/Intersection Name",
        "Traffic Volume",
        "Weather Conditions",
        "Roadwork and Construction Activity",
    ]
    missing = df[required].isna().sum()
    blank_text = {
        column: int(df[column].astype("string").str.strip().eq("").sum())
        for column in [
            "Area Name",
            "Road/Intersection Name",
            "Weather Conditions",
            "Roadwork and Construction Activity",
        ]
    }
    problems = {column: int(count) for column, count in missing.items() if count}
    problems.update(
        {column: count for column, count in blank_text.items() if count}
    )
    if problems:
        raise ValueError(f"Missing or blank required values: {problems}")

    volume = pd.to_numeric(df["Traffic Volume"], errors="raise")
    if not volume.map(isfinite).all():
        raise ValueError("Traffic Volume must contain only finite numbers.")
    if (volume < 0).any():
        raise ValueError("Traffic Volume cannot contain negative values.")

    roadwork_values = (
        df["Roadwork and Construction Activity"]
        .astype("string")
        .str.strip()
        .str.casefold()
    )
    invalid_roadwork = sorted(set(roadwork_values) - {"yes", "no"})
    if invalid_roadwork:
        raise ValueError(
            "Unexpected roadwork labels; expected Yes/No, found: "
            f"{invalid_roadwork}"
        )


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Create the core calendar and categorical features."""

    df = df.copy()

    # -----------------------------
    # Date features
    # -----------------------------
    df["day_of_week"] = df["Date"].dt.dayofweek
    df["month"] = df["Date"].dt.month

    df["is_weekend"] = (
        df["day_of_week"] >= 5
    ).astype(int)

    # -----------------------------
    # Indian holiday feature
    # -----------------------------
    india_holidays = holidays.India(
        years=df["Date"].dt.year.unique().tolist()
    )

    holiday_dates = pd.DatetimeIndex(pd.to_datetime(list(india_holidays.keys())))
    df["is_holiday"] = (
        df["Date"].dt.normalize().isin(holiday_dates)
    ).astype(int)

    # -----------------------------
    # Keep labels as strings. The model pipeline fits one-hot encoders on its
    # training partition so held-out categories cannot affect the mapping.
    # -----------------------------
    for column in ["Area Name", "Road/Intersection Name", "Weather Conditions"]:
        df[column] = df[column].astype("string").str.strip()

    # -----------------------------
    # Roadwork flag
    # -----------------------------
    roadwork_values = (
        df["Roadwork and Construction Activity"]
        .astype("string")
        .str.strip()
        .str.casefold()
    )
    df["roadwork_flag"] = roadwork_values.eq("yes").astype(int)

    print("\nCore features created:")
    print("- day_of_week")
    print("- month")
    print("- is_weekend")
    print("- is_holiday")
    print("- Area Name (categorical text for train-fitted encoding)")
    print("- Road/Intersection Name (categorical text for train-fitted encoding)")
    print("- Weather Conditions (categorical text for train-fitted encoding)")
    print("- roadwork_flag")

    return df


def remove_leakage_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove columns that Member B identified as unsuitable
    for model inputs.
    """

    df = df.copy()

    leakage_columns = [
        "Average Speed",
        "Travel Time Index",
        "Congestion Level",
        "Road Capacity Utilization",
        "Incident Reports",
        "Environmental Impact",
        "Pedestrian and Cyclist Count",
        "Public Transport Usage",
        "Traffic Signal Compliance",
        "Parking Usage",
    ]

    columns_to_remove = [
        column
        for column in leakage_columns
        if column in df.columns
    ]

    df = df.drop(columns=columns_to_remove)

    print("\nExcluded columns:")

    for column in columns_to_remove:
        print(f"- {column}")

    return df


def add_event_flag(
    df: pd.DataFrame,
    events_path: Path = EVENTS_PATH,
) -> pd.DataFrame:
    """Add a flag indicating whether a date is an event day."""

    df = df.copy()

    events = pd.read_csv(
        events_path,
        parse_dates=["event_date"],
    )

    event_dates = events["event_date"].dt.normalize()

    df["is_event_day"] = (
        df["Date"].dt.normalize().isin(event_dates)
    ).astype(int)

    print("\nEvent enrichment:")
    print(f"- Events in event file: {len(events)}")
    print(
        f"- Dataset rows marked as event days: "
        f"{df['is_event_day'].sum()}"
    )

    return df


def report_iqr_outliers(
    df: pd.DataFrame,
    column: str = "Traffic Volume",
) -> pd.DataFrame:
    """
    Report IQR outlier candidates without deleting observations.
    """

    df = df.copy()

    q1 = df[column].quantile(0.25)
    q3 = df[column].quantile(0.75)

    iqr = q3 - q1

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    outlier_mask = (
        (df[column] < lower_bound)
        | (df[column] > upper_bound)
    )

    outlier_count = int(outlier_mask.sum())
    total_rows = len(df)

    percentage = (
        outlier_count / total_rows * 100
        if total_rows > 0
        else 0
    )

    print("\nIQR outlier detection:")
    print(f"- Q1: {q1:.2f}")
    print(f"- Q3: {q3:.2f}")
    print(f"- IQR: {iqr:.2f}")
    print(f"- Lower bound: {lower_bound:.2f}")
    print(f"- Upper bound: {upper_bound:.2f}")
    print(
        f"- Flagged {outlier_count} outlier rows "
        f"out of {total_rows} ({percentage:.2f}%)"
    )

    print("- Outlier candidates are retained for investigation; no rows removed.")
    return df.copy()


def add_interaction_features(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add the weekday interaction required by the workbook.

    The dataset is daily and contains no hour-of-day column,
    so this is represented as a weekday flag rather than
    a misleading rush-hour feature.
    """

    df = df.copy()

    df["weekday_flag"] = (
        df["is_weekend"] == 0
    ).astype(int)

    print("\nInteraction feature created:")
    print("- weekday_flag")

    return df


def build_final_features(
    df: pd.DataFrame,
    events_path: Path = EVENTS_PATH,
) -> pd.DataFrame:
    """Build model-ready columns while retaining every valid observation."""

    df = build_features(df)

    df = add_event_flag(df, events_path=events_path)

    df = report_iqr_outliers(
        df,
        column="Traffic Volume",
    )

    df = add_interaction_features(df)

    # Keep only the features required by the workbook
    # plus Date and Traffic Volume.
    feature_columns = [
        "Date",
        "day_of_week",
        "month",
        "is_weekend",
        "is_holiday",
        "is_event_day",
        "Area Name",
        "Road/Intersection Name",
        "Weather Conditions",
        "roadwork_flag",
        "weekday_flag",
        "Traffic Volume",
    ]

    final_df = df[feature_columns].copy()
    missing_rows = final_df.isna().any(axis=1)
    if missing_rows.any():
        raise ValueError(
            f"Prepared features contain missing values in "
            f"{int(missing_rows.sum())} rows; no rows were silently dropped."
        )

    return final_df


def run_pipeline(
    raw_data_path: Path = RAW_DATA_PATH,
    events_path: Path = EVENTS_PATH,
    output_path: Path = OUTPUT_PATH,
) -> pd.DataFrame:
    """Validate, prepare and save the feature dataset reproducibly."""
    df = load_raw(raw_data_path)
    validate_columns(df)
    validate_required_values(df)
    df = remove_leakage_columns(df)
    features = build_final_features(df, events_path=events_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(output_path, index=False)
    print(f"\nSaved prepared features to: {output_path}")
    print(f"Final rows: {len(features)}")
    print(f"Final columns: {len(features.columns)}")
    return features


if __name__ == "__main__":

    print("=" * 60)
    print("PERSON 1 - FEATURE PREPARATION")
    print("=" * 60)

    features = run_pipeline()

    print("\n" + "=" * 60)
    print("FEATURE ENGINEERING COMPLETED")
    print("=" * 60)

    print("\nFinal columns:")
    for column in features.columns:
        print(f"- {column}")
