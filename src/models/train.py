"""
Train a baseline (Linear Regression) and two improved models (Random Forest,
XGBoost)
to predict Traffic Volume, using both a random split and a time-aware split.
Every run is logged to MLflow, and a results table is written to
docs/model_results.md.

Input : data/processed/traffic_features.csv  (contains a Date column)
Output: model.pkl (best tree model on the time-aware split), docs/model_results.md
"""
import os

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

FEATURES_PATH = "data/processed/traffic_features.csv"
TARGET = "Traffic Volume"
DATE_COL = "Date"


def load_data():
    df = pd.read_csv(FEATURES_PATH, parse_dates=[DATE_COL])
    return df


def random_split(df):
    """80/20 random split. Date is dropped (it is not a model input)."""
    X = df.drop(columns=[TARGET, DATE_COL])
    y = df[TARGET]
    return train_test_split(X, y, test_size=0.2, random_state=42)


def time_split(df):
    """Train on the earliest ~80% of dates, test on the latest ~20%."""
    df = df.sort_values(DATE_COL)
    cutoff = df[DATE_COL].quantile(0.8, interpolation="nearest")
    train = df[df[DATE_COL] < cutoff]
    test = df[df[DATE_COL] >= cutoff]
    print(f"Time split: train {train[DATE_COL].min().date()} -> "
          f"{train[DATE_COL].max().date()} ({len(train)} rows), "
          f"test {test[DATE_COL].min().date()} -> "
          f"{test[DATE_COL].max().date()} ({len(test)} rows)")
    drop = [TARGET, DATE_COL]
    return (train.drop(columns=drop), test.drop(columns=drop),
            train[TARGET], test[TARGET])


def evaluate(model, X_test, y_test):
    preds = model.predict(X_test)
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_test, preds))),
        "mae": float(mean_absolute_error(y_test, preds)),
        "r2": float(r2_score(y_test, preds)),
    }


def run_experiment(model, name, params, split_name, data):
    X_train, X_test, y_train, y_test = data
    with mlflow.start_run(run_name=name):
        model.fit(X_train, y_train)
        metrics = evaluate(model, X_test, y_test)
        mlflow.log_params(params)
        mlflow.log_param("split", split_name)
        mlflow.log_metrics(metrics)
        mlflow.sklearn.log_model(model, "model",
                                 serialization_format="cloudpickle")
        print(f"{name}: {metrics}")
    return model, metrics


def write_results(rows, best_model, best_name, feature_names):
    os.makedirs("docs", exist_ok=True)
    lines = [
        "# Model Results",
        "",
        "| Run | Split | RMSE | MAE | R2 |",
        "|---|---|---|---|---|",
    ]
    for name, split, m in rows:
        lines.append(f"| {name} | {split} | {m['rmse']:.1f} | "
                     f"{m['mae']:.1f} | {m['r2']:.3f} |")
    lines += ["", f"## {best_name} feature importance (saved model)", "",
              "| Feature | Importance |", "|---|---|"]
    imp = sorted(zip(feature_names, best_model.feature_importances_),
                 key=lambda t: t[1], reverse=True)
    for f, v in imp:
        lines.append(f"| {f} | {v:.3f} |")
    with open("docs/model_results.md", "w") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    # Use a RELATIVE sqlite path. The default absolute path breaks on Windows
    # folders that contain a space (e.g. "C:\\Users\\Priyanka S").
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("bangalore-traffic-volume-prediction")
    df = load_data()
    rf_params = {"n_estimators": 200, "max_depth": 12, "random_state": 42}
    xgb_params = {"n_estimators": 300, "max_depth": 6, "learning_rate": 0.05,
                  "random_state": 42}
    results = []

    def run_all(split_label, split_key, data):
        """Run all three models on one split; return the fitted tree models."""
        suffix = split_key
        _, m = run_experiment(LinearRegression(), f"linear_regression_{suffix}",
                              {}, split_key, data)
        results.append(("Linear Regression", split_label, m))
        rf, m = run_experiment(RandomForestRegressor(**rf_params),
                               f"random_forest_{suffix}", rf_params,
                               split_key, data)
        results.append(("Random Forest", split_label, m))
        xgb, m_x = run_experiment(XGBRegressor(**xgb_params),
                                  f"xgboost_{suffix}", xgb_params,
                                  split_key, data)
        results.append(("XGBoost", split_label, m_x))
        return rf, xgb

    # Random split
    run_all("random", "random", random_split(df))

    # Time-aware split
    data = time_split(df)
    rf_model, xgb_model = run_all("time-aware", "timesplit", data)

    # Save whichever tree model has the lower RMSE on the time-aware split
    rf_rmse = results[-2][2]["rmse"]
    xgb_rmse = results[-1][2]["rmse"]
    if xgb_rmse < rf_rmse:
        best_model, best_name = xgb_model, "XGBoost"
    else:
        best_model, best_name = rf_model, "Random Forest"
    joblib.dump(best_model, "model.pkl")
    write_results(results, best_model, best_name, list(data[0].columns))
    print(f"Saved model.pkl ({best_name}) and docs/model_results.md. "
          "Run `mlflow ui --backend-store-uri sqlite:///mlflow.db` "
          "to compare all 6 runs.")