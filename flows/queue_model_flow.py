"""Train and evaluate the 60-second SUMO queue model with local Metaflow."""

import json
import hashlib
import math
import platform
from pathlib import Path
import sys
from importlib.metadata import version

import numpy as np
import pandas as pd
from metaflow import FlowSpec, Parameter, current, step
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "processed"
MODEL_DIR = ROOT / "models"
REPORT_DIR = ROOT / "reports"
HORIZON_S = 60
TARGET = "queue_length_m_t_plus_60s"
NUMERIC_FEATURES = [
    "queue_length_m",
    "vehicle_count",
    "halting_vehicle_count",
    "mean_speed_mps",
    "phase_elapsed_s",
]
CATEGORICAL_FEATURES = [
    "intersection_id",
    "approach_id",
    "lane_id",
    "signal_phase_id",
    "signal_state",
]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
REQUIRED_COLUMNS = set(FEATURES + [TARGET, "simulation_time_s", "run_id"])


def split_values(value):
    result = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    if not result or len(result) != len(set(result)):
        raise ValueError(f"Expected unique comma-separated seed values, got: {value!r}")
    return result


def read_run_files(tag, seeds):
    frames = []
    provenance = []
    for scenario in ("low", "reference", "high"):
        for seed in seeds:
            path = DATA_DIR / f"queue_labeled_60s_{tag}_{scenario}_seed{seed}.csv"
            if not path.is_file():
                raise FileNotFoundError(f"Missing labeled run: {path}")
            frame = pd.read_csv(path)
            missing = REQUIRED_COLUMNS.difference(frame.columns)
            if missing:
                raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
            if frame.empty:
                raise ValueError(f"{path.name} has no labeled rows")
            run_ids = frame["run_id"].dropna().astype(str).unique().tolist()
            if len(run_ids) != 1 or not run_ids[0]:
                raise ValueError(f"Expected one non-empty run_id in {path.name}; got {run_ids}")
            for name in ("run_id", "intersection_id", "lane_id"):
                frame[name] = frame[name].astype(str)
            numeric = frame[NUMERIC_FEATURES + [TARGET, "simulation_time_s"]].apply(
                pd.to_numeric, errors="coerce"
            )
            if numeric.isna().any().any() or not np.isfinite(numeric.to_numpy()).all():
                raise ValueError(f"{path.name} has missing or non-finite numeric values")
            nonnegative = NUMERIC_FEATURES + [TARGET, "simulation_time_s"]
            if (numeric[nonnegative] < 0).any().any():
                raise ValueError(f"{path.name} has a negative physical value")
            if (numeric["halting_vehicle_count"] > numeric["vehicle_count"]).any():
                raise ValueError(f"{path.name} has more halting vehicles than total vehicles")
            if numeric["vehicle_count"].mod(1).ne(0).any() or numeric["halting_vehicle_count"].mod(1).ne(0).any():
                raise ValueError(f"{path.name} has a non-integer vehicle count")
            for name in CATEGORICAL_FEATURES:
                if frame[name].isna().any() or frame[name].astype(str).str.strip().eq("").any():
                    raise ValueError(f"{path.name} has missing categorical feature {name}")
                frame[name] = frame[name].astype(str)
            frame[NUMERIC_FEATURES + [TARGET, "simulation_time_s"]] = numeric
            key_columns = ["run_id", "intersection_id", "lane_id", "simulation_time_s"]
            if frame.duplicated(key_columns).any():
                raise ValueError(f"{path.name} contains duplicate run/intersection/lane/time rows")

            observation_path = DATA_DIR / f"queue_observations_{tag}_{scenario}_seed{seed}.csv"
            # Older runs may have reused the archived baseline reference observations.
            # Keep that fallback for backward compatibility; new tagged collections
            # always use a run-specific file, including reference demand.
            if scenario == "reference" and not observation_path.is_file():
                observation_path = DATA_DIR / f"sumo_queue_observations_seed{seed}.csv"
            if not observation_path.is_file():
                raise FileNotFoundError(f"Missing source observations: {observation_path}")
            observations = pd.read_csv(observation_path)
            observation_columns = set(key_columns + ["queue_length_m"])
            missing_observation_columns = observation_columns.difference(observations.columns)
            if missing_observation_columns:
                raise ValueError(
                    f"{observation_path.name} is missing source columns: "
                    f"{sorted(missing_observation_columns)}"
                )
            for name in ("run_id", "intersection_id", "lane_id"):
                observations[name] = observations[name].astype(str)
            observations["simulation_time_s"] = pd.to_numeric(
                observations["simulation_time_s"], errors="coerce"
            )
            observations["queue_length_m"] = pd.to_numeric(
                observations["queue_length_m"], errors="coerce"
            )
            if observations[["simulation_time_s", "queue_length_m"]].isna().any().any():
                raise ValueError(f"{observation_path.name} has invalid numeric source values")
            if observations.duplicated(key_columns).any():
                raise ValueError(f"{observation_path.name} has duplicate source observations")
            observation_run_ids = observations["run_id"].unique().tolist()
            if observation_run_ids != run_ids:
                raise ValueError(
                    f"Source run IDs in {observation_path.name} do not match {path.name}"
                )
            future_rows = observations[key_columns + ["queue_length_m"]].rename(
                columns={"simulation_time_s": "future_time_s", "queue_length_m": "verified_target"}
            )
            labeled_for_join = frame.copy()
            labeled_for_join["future_time_s"] = labeled_for_join["simulation_time_s"] + HORIZON_S
            verified = labeled_for_join.merge(
                future_rows,
                on=["run_id", "intersection_id", "lane_id", "future_time_s"],
                how="left",
                validate="many_to_one",
            )
            if verified["verified_target"].isna().any() or not np.allclose(
                verified[TARGET].to_numpy(dtype=float),
                verified["verified_target"].to_numpy(dtype=float),
                rtol=0,
                atol=1e-9,
            ):
                raise ValueError(f"{path.name} contains a label that is not the exact +60s source queue")
            frame["scenario"] = scenario
            frame["seed"] = seed
            frames.append(frame)
            provenance.append({
                "scenario": scenario,
                "seed": seed,
                "run_id": run_ids[0],
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "observation_path": str(observation_path),
                "observation_sha256": hashlib.sha256(observation_path.read_bytes()).hexdigest(),
                "verified_exact_horizon_labels": int(len(verified)),
                "rows": int(len(frame)),
                "zero_target_fraction": float((frame[TARGET] == 0).mean()),
            })
    return pd.concat(frames, ignore_index=True), provenance


def metric_set(frame, predictions):
    actual = frame[TARGET].to_numpy(dtype=float)
    persistence = frame["queue_length_m"].to_numpy(dtype=float)
    predictions = np.asarray(predictions, dtype=float)
    positive = actual > 0

    def pair(y, pred):
        absolute_error = np.abs(np.asarray(pred, dtype=float) - np.asarray(y, dtype=float))
        return {
            "n": int(len(y)),
            "mae_m": float(mean_absolute_error(y, pred)),
            "rmse_m": float(math.sqrt(mean_squared_error(y, pred))),
            "p95_absolute_error_m": float(np.percentile(absolute_error, 95)),
        }

    if not np.isfinite(predictions).all():
        raise ValueError("Model produced non-finite predictions")
    if (predictions < 0).any():
        raise ValueError("Model produced negative queue predictions")
    return {
        "rows": int(len(actual)),
        "zero_target_fraction": float((actual == 0).mean()),
        "model": pair(actual, predictions),
        "persistence": pair(actual, persistence),
        "positive_future_queue_rows": int(positive.sum()),
        "model_positive": pair(actual[positive], predictions[positive]) if positive.any() else None,
        "persistence_positive": pair(actual[positive], persistence[positive]) if positive.any() else None,
        "prediction_min_m": float(predictions.min()),
        "prediction_max_m": float(predictions.max()),
    }


def grouped_metrics(model, frame, group_columns):
    results = {}
    for key, group in frame.groupby(group_columns, sort=True, dropna=False):
        key_values = key if isinstance(key, tuple) else (key,)
        group_name = "|".join(str(value) for value in key_values)
        predictions = model.predict(group[FEATURES])
        results[group_name] = metric_set(group, predictions)
    return results


class QueueModelFlow(FlowSpec):
    train_tag = Parameter("train-tag", default="phase2_v1")
    evaluation_tag = Parameter("evaluation-tag", default="phase2_v2")
    train_seeds = Parameter("train-seeds", default="7,21")
    validation_seeds = Parameter("validation-seeds", default="42")
    test_seeds = Parameter("test-seeds", default="99")

    @step
    def start(self):
        self.train_seed_values = split_values(self.train_seeds)
        self.validation_seed_values = split_values(self.validation_seeds)
        self.test_seed_values = split_values(self.test_seeds)
        partitions = [set(self.train_seed_values), set(self.validation_seed_values),
                      set(self.test_seed_values)]
        if any(partitions[i] & partitions[j] for i in range(3) for j in range(i + 1, 3)):
            raise ValueError("Train, validation, and test seeds must be disjoint")
        self.horizon_seconds = HORIZON_S
        self.target_name = TARGET
        self.feature_names = FEATURES
        self.next(self.validate_partitions)

    @step
    def validate_partitions(self):
        self.train_frame, self.train_provenance = read_run_files(
            self.train_tag, self.train_seed_values
        )
        self.validation_frame, self.validation_provenance = read_run_files(
            self.evaluation_tag, self.validation_seed_values
        )
        self.test_frame, self.test_provenance = read_run_files(
            self.evaluation_tag, self.test_seed_values
        )
        train_run_ids = {item["run_id"] for item in self.train_provenance}
        validation_run_ids = {item["run_id"] for item in self.validation_provenance}
        test_run_ids = {item["run_id"] for item in self.test_provenance}
        if (train_run_ids & validation_run_ids) or (train_run_ids & test_run_ids) or (validation_run_ids & test_run_ids):
            raise ValueError("The same SUMO run_id appears in more than one data partition")
        self.next(self.train_model)

    @step
    def train_model(self):
        transformer = ColumnTransformer([
            ("numeric", "passthrough", NUMERIC_FEATURES),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ])
        self.model = Pipeline([
            ("preprocessor", transformer),
            ("regressor", RandomForestRegressor(
                n_estimators=300,
                min_samples_leaf=5,
                random_state=42,
                n_jobs=-1,
            )),
        ])
        self.model.fit(self.train_frame[FEATURES], self.train_frame[TARGET])
        self.next(self.validate_model)

    @step
    def validate_model(self):
        prediction = self.model.predict(self.validation_frame[FEATURES])
        self.validation_metrics = metric_set(self.validation_frame, prediction)
        self.validation_metrics_by_scenario = grouped_metrics(
            self.model, self.validation_frame, ["scenario"]
        )
        self.validation_metrics_by_intersection_approach = grouped_metrics(
            self.model, self.validation_frame, ["intersection_id", "approach_id"]
        )
        checks = {
            "beats_persistence_mae": (
                self.validation_metrics["model"]["mae_m"]
                < self.validation_metrics["persistence"]["mae_m"]
            ),
            "beats_persistence_rmse": (
                self.validation_metrics["model"]["rmse_m"]
                < self.validation_metrics["persistence"]["rmse_m"]
            ),
            "beats_positive_persistence_mae": (
                self.validation_metrics["model_positive"]["mae_m"]
                < self.validation_metrics["persistence_positive"]["mae_m"]
            ),
            "beats_positive_persistence_rmse": (
                self.validation_metrics["model_positive"]["rmse_m"]
                < self.validation_metrics["persistence_positive"]["rmse_m"]
            ),
        }
        for scenario, metrics in self.validation_metrics_by_scenario.items():
            checks[f"{scenario}_beats_persistence_mae"] = (
                metrics["model"]["mae_m"] < metrics["persistence"]["mae_m"]
            )
            checks[f"{scenario}_beats_persistence_rmse"] = (
                metrics["model"]["rmse_m"] < metrics["persistence"]["rmse_m"]
            )
            checks[f"{scenario}_beats_positive_persistence_mae"] = (
                metrics["model_positive"]["mae_m"] < metrics["persistence_positive"]["mae_m"]
            )
            checks[f"{scenario}_beats_positive_persistence_rmse"] = (
                metrics["model_positive"]["rmse_m"] < metrics["persistence_positive"]["rmse_m"]
            )
        self.validation_checks = checks
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            raise ValueError("Validation quality gate failed: " + ", ".join(failed))
        self.next(self.evaluate_test)

    @step
    def evaluate_test(self):
        # The final test partition is evaluated only after validation passes.
        predictions = self.model.predict(self.test_frame[FEATURES])
        self.test_metrics = metric_set(self.test_frame, predictions)
        self.test_metrics_by_scenario = grouped_metrics(
            self.model, self.test_frame, ["scenario"]
        )
        self.test_metrics_by_intersection_approach = grouped_metrics(
            self.model, self.test_frame, ["intersection_id", "approach_id"]
        )
        self.next(self.save_version)

    @step
    def save_version(self):
        run_id = str(current.run_id)
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        model_path = MODEL_DIR / f"queue_rf_60s_{run_id}.joblib"
        report_path = REPORT_DIR / f"queue_model_metaflow_{run_id}.json"
        if model_path.exists() or report_path.exists():
            raise FileExistsError("Refusing to overwrite an existing Metaflow output")
        import joblib

        joblib.dump(self.model, model_path)
        self.version_record = {
            "metaflow_flow": "QueueModelFlow",
            "metaflow_run_id": run_id,
            "target": TARGET,
            "horizon_seconds": HORIZON_S,
            "queue_unit": "metres",
            "features": FEATURES,
            "train_seeds": list(self.train_seed_values),
            "validation_seeds": list(self.validation_seed_values),
            "test_seeds": list(self.test_seed_values),
            "train_runs": self.train_provenance,
            "validation_runs": self.validation_provenance,
            "test_runs": self.test_provenance,
            "train_rows": int(len(self.train_frame)),
            "validation_rows": int(len(self.validation_frame)),
            "test_rows": int(len(self.test_frame)),
            "validation_metrics": self.validation_metrics,
            "validation_checks": self.validation_checks,
            "test_metrics": self.test_metrics,
            "validation_metrics_by_scenario": self.validation_metrics_by_scenario,
            "validation_metrics_by_intersection_approach": self.validation_metrics_by_intersection_approach,
            "test_metrics_by_scenario": self.test_metrics_by_scenario,
            "test_metrics_by_intersection_approach": self.test_metrics_by_intersection_approach,
            "validation_quality_gate_checks": self.validation_checks,
            "model_path": str(model_path),
            "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
            "report_path": str(report_path),
            "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "environment": {
                "python": sys.version,
                "platform": platform.platform(),
                "packages": {
                    name: version(name)
                    for name in ("metaflow", "numpy", "pandas", "scikit-learn", "joblib")
                },
            },
            "model_selection": "fixed RandomForest; validation gate against persistence",
            "model_status": "candidate_passed_validation_quality_gate",
            "limitations": [
                "One synthetic network; results do not establish real-world impact.",
                "Queue measurement is simulation-derived and not field-validated.",
                "Two training seeds and one validation/test seed each are preliminary.",
                "The test set is held out by complete SUMO seed, not by network topology.",
            ],
        }
        report_path.write_text(json.dumps(self.version_record, indent=2), encoding="utf-8")
        self.model_path = str(model_path)
        self.report_path = str(report_path)
        self.next(self.end)

    @step
    def end(self):
        print("Metaflow run:", current.run_id)
        print("Model artifact:", self.model_path)
        print("Version report:", self.report_path)
        print("Validation metrics:", json.dumps(self.validation_metrics, sort_keys=True))
        print("Final test metrics:", json.dumps(self.test_metrics, sort_keys=True))


if __name__ == "__main__":
    QueueModelFlow()
