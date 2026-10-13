from pathlib import Path

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

    df["is_holiday"] = (
        df["Date"].isin(india_holidays)
    ).astype(int)

    # -----------------------------
    # Categorical encoding
    # -----------------------------
    df["area_encoded"] = (
        df["Area Name"]
        .astype("category")
        .cat.codes
    )

    df["road_encoded"] = (
        df["Road/Intersection Name"]
        .astype("category")
        .cat.codes
    )

    df["weather_encoded"] = (
        df["Weather Conditions"]
        .astype("category")
        .cat.codes
    )

    # -----------------------------
    # Roadwork flag
    # -----------------------------
    df["roadwork_flag"] = (
        df["Roadwork and Construction Activity"] != "No"
    ).astype(int)

    print("\nCore features created:")
    print("- day_of_week")
    print("- month")
    print("- is_weekend")
    print("- is_holiday")
    print("- area_encoded")
    print("- road_encoded")
    print("- weather_encoded")
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


def flag_outliers_iqr(
    df: pd.DataFrame,
    column: str = "Traffic Volume",
) -> pd.DataFrame:
    """
    Detect and remove outliers using the IQR method.
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

    return df[~outlier_mask].copy()


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
) -> pd.DataFrame:
    """Run the complete Member C feature-engineering pipeline."""

    df = build_features(df)

    df = add_event_flag(df)

    df = flag_outliers_iqr(
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
        "area_encoded",
        "road_encoded",
        "weather_encoded",
        "roadwork_flag",
        "weekday_flag",
        "Traffic Volume",
    ]

    final_df = df[feature_columns].dropna()

    return final_df


if __name__ == "__main__":

    print("=" * 60)
    print("MEMBER C - FEATURE ENGINEERING")
    print("=" * 60)

    # Load raw data
    df = load_raw(RAW_DATA_PATH)

    # Validate required columns
    validate_columns(df)

    # Remove columns identified by Member B
    df = remove_leakage_columns(df)

    # Build final features
    features = build_final_features(df)

    # Create output directory
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Save processed features
    features.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print("\n" + "=" * 60)
    print("FEATURE ENGINEERING COMPLETED")
    print("=" * 60)

    print(f"Final rows: {len(features)}")
    print(f"Final columns: {len(features.columns)}")

    print("\nFinal columns:")
    for column in features.columns:
        print(f"- {column}")

    print("\nSaved to:")
    print(OUTPUT_PATH)