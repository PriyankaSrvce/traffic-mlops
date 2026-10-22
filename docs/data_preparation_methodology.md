# Data Preparation and Feature Engineering Methodology

## 1. Dataset and verified input

The supplied local file is `data/raw/bangalore_traffic.csv`; project notes attribute it to Bangalore's Traffic Pulse (Preetham Gouda, Kaggle). Its MD5 hash matches the DVC pointer in this project snapshot. This verifies the local file against the pointer, not the original external source or listing. Dataset license status: **unverified**. The CSV contains 8,936 rows and 16 columns, with daily dates from 2022-01-01 through 2024-08-09. It has no time-of-day, queue-length, or signal-phase observations.

The input is preserved unchanged. Feature preparation writes a separate file to `data/processed/traffic_features.csv`.

## 2. Validation and cleaning

The pipeline checks for the required columns, blank or missing values in required fields, negative traffic volume, and roadwork labels outside Yes/No. Dates are parsed with errors raised instead of silently coercing invalid values. It does not drop rows to handle IQR outliers or missing values. If required output fields are missing, it raises an error instead of silently dropping records.

Verified in the supplied CSV: 0 missing cells, 0 exact duplicate rows, and 0 duplicate `(Date, Road/Intersection Name)` pairs. The observed traffic-volume IQR rule flags 24 high observations (0.27%); these are retained because statistical unusualness alone does not establish a data error.

The feature pipeline was run in an isolated scratch copy. Its generated output was verified at 8,936 rows and 12 columns, with zero missing values in every column. `Traffic Volume` was numeric, finite, nonnegative, and ranged from 4,233 to 72,039. The run also marked 40 dataset rows using the five entries in the event file; this verifies the code's matching behavior, not the completeness or correctness of that manually curated list. The original source attribution remains qualified and the dataset license remains **unverified**.

## 3. Features and exclusions

The 12-column output keeps the dataset's categorical labels as text: `Date`, `day_of_week`, `month`, `is_weekend`, `is_holiday`, `is_event_day`, `Area Name`, `Road/Intersection Name`, `Weather Conditions`, `roadwork_flag`, `weekday_flag`, and `Traffic Volume`.

- `day_of_week` uses Monday=0 through Sunday=6; `month` is 1–12; `is_weekend` and `weekday_flag` are complementary binary calendar features.
- `is_holiday` uses the `holidays` package's India calendar.
- `is_event_day` matches dates in `src/features/bangalore_events.csv`. This is a small, manually curated list, not a complete event calendar.
- Area, road, and weather labels stay as text in the processed file. Person 2's training pipeline fits `OneHotEncoder` only on training rows and ignores unseen labels at prediction time.
- `roadwork_flag` is 1 for Yes and 0 for No; unexpected labels are rejected.
- `Traffic Volume` remains the existing target column. `Date` is retained for time-aware splitting and is removed from model inputs by the current training script.

The following same-observation or otherwise unsuitable columns remain excluded from the model feature output: Average Speed, Travel Time Index, Congestion Level, Road Capacity Utilization, Incident Reports, Environmental Impact, Public Transport Usage, Traffic Signal Compliance, Parking Usage, and Pedestrian and Cyclist Count. In particular, Environmental Impact has a verified Pearson correlation of 1.000 with Traffic Volume in this file; it must not be used as a predictor.

## 4. Interpretation and limits

This dataset can support a historical daily traffic-volume prediction exercise using location and calendar/context inputs. Weather is recorded for the observed day, so a real prediction would need a weather forecast available at prediction time. This dataset does not support rush-hour, future queue-length, or signal-control prediction: those need suitable timestamped observations and, for future targets, a defined prediction horizon. SUMO-generated data should be tracked and documented separately from this real-world dataset.

## 5. Output and reproduction

The prepared output is `data/processed/traffic_features.csv`. With the project's declared dependencies installed, run from the repository root:

```powershell
python -m src.features.build_features
```

The verified real dataset produced 8,936 rows and 12 columns. All 24 IQR candidates are retained. The existing model-training interface and target column were preserved.

From a Windows PowerShell prompt at the repository root, reproduce the EDA, features, and focused checks with:

```powershell
python notebooks\eda.py
python -m src.features.build_features
python -m unittest discover -s tests -v
```

If setting up a fresh environment, create and activate a virtual environment, then install the project's declared requirements before running these commands. The requirements file is UTF-8 encoded. DVC credentials must be configured safely before using DVC; credentials are not stored in the sanitized working-copy config.
