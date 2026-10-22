"""Train leakage-aware models to predict daily Traffic Volume.

Run from the repository root with:
    python -m src.models.train

Categorical encoders are fit inside each model on its training rows. The
primary evaluation is a holdout of the latest dates; random-split scores are
reported only as a comparison because rows from the same date can cross that
split.
"""
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor

try:
    import mlflow
    import mlflow.sklearn
except ModuleNotFoundError:
    mlflow = None

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FEATURES_PATH = PROJECT_ROOT / "data" / "processed" / "traffic_features.csv"
MODEL_PATH = PROJECT_ROOT / "model.pkl"
RESULTS_PATH = PROJECT_ROOT / "docs" / "model_results.md"
TARGET = "Traffic Volume"
DATE_COL = "Date"
CATEGORICAL_FEATURES = ["Area Name", "Road/Intersection Name", "Weather Conditions"]
NUMERIC_FEATURES = [
    "day_of_week",
    "month",
    "is_weekend",
    "is_holiday",
    "is_event_day",
    "roadwork_flag",
]
FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def load_data(path: Path = FEATURES_PATH) -> pd.DataFrame:
    """Load prepared data and reject a schema that the trainer cannot use."""
    df = pd.read_csv(path, parse_dates=[DATE_COL])
    required = [DATE_COL, TARGET, *FEATURES]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Prepared dataset is missing columns: {missing}")
    if df[required].isna().any().any():
        raise ValueError("Prepared model inputs and target cannot contain missing values.")
    df[TARGET] = pd.to_numeric(df[TARGET], errors="raise")
    if not np.isfinite(df[TARGET]).all():
        raise ValueError("Traffic Volume target must contain finite numbers.")
    if df[DATE_COL].isna().any():
        raise ValueError("Date values must all parse successfully.")
    return df


def random_split(df: pd.DataFrame):
    """Return a reproducible 80/20 row split for comparison only."""
    X = df[FEATURES]
    y = df[TARGET]
    return train_test_split(X, y, test_size=0.2, random_state=42)


def make_time_split(df: pd.DataFrame):
    """Split on distinct dates so one date never appears in both partitions."""
    dates = df[DATE_COL].drop_duplicates().sort_values().reset_index(drop=True)
    if len(dates) < 2:
        raise ValueError("At least two distinct dates are required for a time split.")
    split_index = min(max(int(len(dates) * 0.8), 1), len(dates) - 1)
    cutoff = dates.iloc[split_index]
    train = df.loc[df[DATE_COL] < cutoff]
    test = df.loc[df[DATE_COL] >= cutoff]
    if train.empty or test.empty or train[DATE_COL].max() >= test[DATE_COL].min():
        raise ValueError("Time split must have nonempty, nonoverlapping date ranges.")

    details = {
        "cutoff": cutoff,
        "train_start": train[DATE_COL].min(),
        "train_end": train[DATE_COL].max(),
        "test_start": test[DATE_COL].min(),
        "test_end": test[DATE_COL].max(),
        "train_rows": len(train),
        "test_rows": len(test),
        "train_dates": train[DATE_COL].nunique(),
        "test_dates": test[DATE_COL].nunique(),
    }
    data = (train[FEATURES], test[FEATURES], train[TARGET], test[TARGET])
    return data, details


def time_split(df: pd.DataFrame):
    """Train on the earliest dates and test on the latest dates."""
    return make_time_split(df)[0]


def make_pipeline(estimator) -> Pipeline:
    """Fit categorical encoding only on each split's training rows."""
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                CATEGORICAL_FEATURES,
            )
        ],
        remainder="passthrough",
    )
    return Pipeline(
        steps=[("preprocessor", preprocessor), ("estimator", estimator)]
    )


def evaluate_predictions(y_true, predictions) -> dict:
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_true, predictions))),
        "mae": float(mean_absolute_error(y_true, predictions)),
        "r2": float(r2_score(y_true, predictions)),
    }


def evaluate(model, X_test, y_test) -> dict:
    return evaluate_predictions(y_test, model.predict(X_test))


def baseline_metrics(y_train, y_test) -> dict:
    """Score a mean-only predictor to show whether features add value."""
    predictions = np.full(len(y_test), float(y_train.mean()))
    return evaluate_predictions(y_test, predictions)


def model_specs() -> dict:
    return {
        "Linear Regression": (LinearRegression(), {}),
        "Random Forest": (
            RandomForestRegressor(
                n_estimators=200,
                max_depth=12,
                random_state=42,
                n_jobs=-1,
            ),
            {"n_estimators": 200, "max_depth": 12, "random_state": 42},
        ),
        "XGBoost": (
            XGBRegressor(
                n_estimators=300,
                max_depth=6,
                learning_rate=0.05,
                random_state=42,
                n_jobs=-1,
                tree_method="hist",
                objective="reg:squarederror",
            ),
            {
                "n_estimators": 300,
                "max_depth": 6,
                "learning_rate": 0.05,
                "random_state": 42,
                "tree_method": "hist",
            },
        ),
    }


def run_experiment(estimator, name, params, split_name, data):
    X_train, X_test, y_train, y_test = data
    pipeline = make_pipeline(estimator)
    if mlflow is None:
        pipeline.fit(X_train, y_train)
        metrics = evaluate(pipeline, X_test, y_test)
    else:
        with mlflow.start_run(run_name=f"{split_name}_{name}"):
            pipeline.fit(X_train, y_train)
            metrics = evaluate(pipeline, X_test, y_test)
            mlflow.log_params(params)
            mlflow.log_param("split", split_name)
            mlflow.log_param("train_rows", len(X_train))
            mlflow.log_param("test_rows", len(X_test))
            mlflow.log_metrics(metrics)
            mlflow.sklearn.log_model(
                pipeline,
                name="model",
                serialization_format="cloudpickle",
            )
    print(f"{name} ({split_name}): {metrics}")
    return pipeline, metrics


def write_results(rows, champion_name, champion, tree_name, tree_model, time_details):
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Model Results",
        "",
        "## Evaluation setup",
        "",
        "Target: continuous `Traffic Volume` (same-day daily observation).",
        "The time-aware holdout is the primary score; the random split is a comparison only.",
        "OneHotEncoder is fit inside each training pipeline, with unseen categories ignored.",
        "`weekday_flag` is excluded because it duplicates `is_weekend`.",
        f"Environment: Python {sys.version.split()[0]}, pandas {pd.__version__}, "
        f"scikit-learn {sklearn.__version__}, XGBoost {xgboost.__version__}, "
        f"MLflow {mlflow.__version__ if mlflow else 'unavailable'}.",
        "Project requirements pin scikit-learn 1.7.2; this run used the locally installed version shown above.",
        "The saved model is a Python serialization artifact; load only this project's trusted output.",
        "",
        f"Time split cutoff: {time_details['cutoff'].date()}.",
        f"Train: {time_details['train_start'].date()} to {time_details['train_end'].date()} "
        f"({time_details['train_rows']} rows, {time_details['train_dates']} dates).",
        f"Test: {time_details['test_start'].date()} to {time_details['test_end'].date()} "
        f"({time_details['test_rows']} rows, {time_details['test_dates']} dates).",
        "",
        "## Scores",
        "",
        "| Model | Split | RMSE | MAE | R² |",
        "|---|---|---:|---:|---:|",
    ]
    for name, split_name, metrics in rows:
        lines.append(
            f"| {name} | {split_name} | {metrics['rmse']:.1f} | "
            f"{metrics['mae']:.1f} | {metrics['r2']:.3f} |"
        )

    lines += [
        "",
        f"Saved model: **{champion_name}** (lowest RMSE on the time-aware holdout).",
        "This is a holdout benchmark, not a claim of future deployment performance.",
        "The dataset has daily same-day weather and no queue-length or signal-phase target.",
        "",
        f"## {tree_name} Feature Importance on Time Holdout Model",
        "",
        "These model-based importances are descriptive, not causal.",
        "",
        "| Encoded feature | Importance |",
        "|---|---:|",
    ]
    fitted_estimator = tree_model.named_steps["estimator"]
    feature_names = tree_model.named_steps["preprocessor"].get_feature_names_out()
    importances = sorted(
        zip(feature_names, fitted_estimator.feature_importances_),
        key=lambda item: item[1],
        reverse=True,
    )
    for feature_name, importance in importances:
        lines.append(f"| {feature_name} | {importance:.4f} |")
    RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_training():
    df = load_data()
    random_data = random_split(df)
    time_data, time_details = make_time_split(df)

    print(
        f"Time holdout: train {time_details['train_start'].date()} through "
        f"{time_details['train_end'].date()} ({time_details['train_rows']} rows); "
        f"test {time_details['test_start'].date()} through "
        f"{time_details['test_end'].date()} ({time_details['test_rows']} rows)."
    )
    if mlflow is not None:
        mlflow.set_tracking_uri(f"sqlite:///{(PROJECT_ROOT / 'mlflow.db').as_posix()}")
        mlflow.set_experiment("bangalore-traffic-volume-prediction")
    else:
        print("MLflow is unavailable; metrics will be saved locally without tracking.")

    results = []
    fitted = {}
    for split_name, data in [("random", random_data), ("time-aware", time_data)]:
        X_train, X_test, y_train, y_test = data
        baseline = baseline_metrics(y_train, y_test)
        results.append(("Mean baseline", split_name, baseline))
        print(f"Mean baseline ({split_name}): {baseline}")
        for name, (estimator, params) in model_specs().items():
            pipeline, metrics = run_experiment(
                estimator, name, params, split_name, data
            )
            results.append((name, split_name, metrics))
            fitted[(split_name, name)] = (pipeline, metrics)

    time_candidates = [
        (name, *fitted[("time-aware", name)]) for name in model_specs()
    ]
    champion_name, champion, _ = min(
        time_candidates, key=lambda item: item[2]["rmse"]
    )
    tree_name = min(
        ["Random Forest", "XGBoost"],
        key=lambda name: fitted[("time-aware", name)][1]["rmse"],
    )
    tree_model = fitted[("time-aware", tree_name)][0]

    joblib.dump(champion, MODEL_PATH)
    write_results(
        results,
        champion_name,
        champion,
        tree_name,
        tree_model,
        time_details,
    )
    print(f"Saved {MODEL_PATH.name} ({champion_name}) and {RESULTS_PATH.name}.")
    return results, champion_name


if __name__ == "__main__":
    run_training()
