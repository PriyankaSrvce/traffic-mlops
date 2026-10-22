# Data Dictionary - Bangalore Traffic Dataset

The supplied local file is named `Banglore_traffic_Dataset.csv`; project notes attribute it to Bangalore's Traffic Pulse (Preetham Gouda, Kaggle). This audit verified the local file contents and that its MD5 matches the project's DVC pointer, but did not independently verify the original source or Kaggle listing. Dataset license status: **unverified**.

The raw CSV contains 8,936 rows and 16 columns. Dates range from 2022-01-01 to 2024-08-09; all 952 calendar dates are present. There are no blank cells, exact duplicate rows, or duplicate `(Date, Road/Intersection Name)` pairs. Source units are not stated, so none are assumed.

| Column | CSV type | Description and verified observations | Prediction use |
|---|---|---|---|
| Date | date text | Daily observation date; 952 distinct dates. | Calendar features and time-aware evaluation. Not a model input in the current trainer. |
| Area Name | text | Area label; 8 areas. | Candidate categorical input; stored as a text label in the prepared output and encoded within the training pipeline. |
| Road/Intersection Name | text | Road or junction label; 16 roads. | Candidate categorical input; stored as a text label in the prepared output and encoded within the training pipeline. |
| Traffic Volume | integer | Target field; 4,233 to 72,039; mean 29,236. | Current continuous regression target. |
| Average Speed | decimal | Same-observation speed. | Excluded from model inputs. |
| Travel Time Index | decimal | Same-observation travel-time measure. | Excluded; correlated 0.698 with volume. |
| Congestion Level | decimal | Same-observation congestion measure, capped at 100. | Excluded; correlated 0.837 with volume. |
| Road Capacity Utilization | decimal | Same-observation capacity-use measure, capped at 100. | Excluded; correlated 0.653 with volume. |
| Incident Reports | integer | Same-observation incident count. | Excluded from current feature set. |
| Environmental Impact | decimal | Environmental measure; Pearson correlation 1.000 with volume in this file. | Excluded; strong leakage concern. |
| Public Transport Usage | decimal | Public-transport measure. | Excluded from current feature set; availability at prediction time is unclear. |
| Traffic Signal Compliance | decimal | Same-observation signal-compliance measure. | Excluded from current feature set. |
| Parking Usage | decimal | Parking-use measure. | Excluded from current feature set. |
| Pedestrian and Cyclist Count | integer | Same-observation count. | Excluded from current feature set. |
| Weather Conditions | text | Clear 5,426 (60.7%), Overcast 1,296 (14.5%), Fog 959 (10.7%), Rain 827 (9.3%), Windy 428 (4.8%). | Candidate only when a forecast is available before prediction. |
| Roadwork and Construction Activity | text | Yes 882 (9.9%), No 8,054 (90.1%). | Candidate only when known before prediction. |

## Prepared feature interface

`data/processed/traffic_features.csv` contains `Date`, `day_of_week`, `month`, `is_weekend`, `is_holiday`, `is_event_day`, `Area Name`, `Road/Intersection Name`, `Weather Conditions`, `roadwork_flag`, `weekday_flag`, and `Traffic Volume` (12 columns). The trainer uses `Traffic Volume` as the regression target, drops `Date` for model fitting, and excludes `weekday_flag` because it duplicates `is_weekend`. The model pipeline fits one-hot category encoding on training data and ignores unseen categories.

The IQR rule marks 24 high-volume observations for review. They are retained; unusual values are not automatically errors. In the isolated scratch reproduction, the generated output was verified at 8,936 rows and 12 columns, with no missing values in any processed column. `Traffic Volume` was numeric, finite, nonnegative, and ranged from 4,233 to 72,039.

This is daily, same-day historical data. It contains no future traffic-volume label, time-of-day, queue length, or signal phase. It does not establish support for queue forecasting or adaptive signal control. SUMO observations should be recorded and documented separately from the real-world dataset.
