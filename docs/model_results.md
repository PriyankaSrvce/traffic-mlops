# Model Results

## Evaluation setup

Target: continuous `Traffic Volume` (same-day daily observation).
The time-aware holdout is the primary score; the random split is a comparison only.
OneHotEncoder is fit inside each training pipeline, with unseen categories ignored.
`weekday_flag` is excluded because it duplicates `is_weekend`.
Environment: Python 3.10.1, pandas 2.3.3, scikit-learn 1.7.2, XGBoost 3.2.0, MLflow 3.16.1.
Project requirements pin scikit-learn 1.7.2; this run used the locally installed version shown above.
The saved model is a Python serialization artifact; load only this project's trusted output.

Time split cutoff: 2024-02-01.
Train: 2022-01-01 to 2024-01-31 (7145 rows, 761 dates).
Test: 2024-02-01 to 2024-08-09 (1791 rows, 191 dates).

## Scores

| Model | Split | RMSE | MAE | R² |
|---|---|---:|---:|---:|
| Mean baseline | random | 12957.0 | 10493.3 | -0.000 |
| Linear Regression | random | 10502.0 | 8454.6 | 0.343 |
| Random Forest | random | 10957.3 | 8712.2 | 0.284 |
| XGBoost | random | 10892.9 | 8684.1 | 0.293 |
| Mean baseline | time-aware | 12846.2 | 10544.0 | -0.000 |
| Linear Regression | time-aware | 10454.1 | 8499.3 | 0.338 |
| Random Forest | time-aware | 10965.4 | 8808.5 | 0.271 |
| XGBoost | time-aware | 10964.8 | 8831.6 | 0.271 |

Saved model: **Linear Regression** (lowest RMSE on the time-aware holdout).
This is a holdout benchmark, not a claim of future deployment performance.
The dataset has daily same-day weather and no queue-length or signal-phase target.

## XGBoost Feature Importance on Time Holdout Model

These model-based importances are descriptive, not causal.

| Encoded feature | Importance |
|---|---:|
| categorical__Area Name_Koramangala | 0.3669 |
| categorical__Area Name_Indiranagar | 0.2159 |
| categorical__Area Name_M.G. Road | 0.1950 |
| categorical__Area Name_Hebbal | 0.0336 |
| categorical__Area Name_Jayanagar | 0.0334 |
| categorical__Area Name_Electronic City | 0.0319 |
| categorical__Area Name_Whitefield | 0.0312 |
| categorical__Area Name_Yeshwanthpur | 0.0142 |
| categorical__Road/Intersection Name_Anil Kumble Circle | 0.0051 |
| categorical__Road/Intersection Name_Hebbal Flyover | 0.0040 |
| categorical__Road/Intersection Name_100 Feet Road | 0.0040 |
| categorical__Weather Conditions_Clear | 0.0038 |
| categorical__Road/Intersection Name_Sarjapur Road | 0.0038 |
| remainder__roadwork_flag | 0.0037 |
| remainder__day_of_week | 0.0037 |
| categorical__Weather Conditions_Rain | 0.0036 |
| categorical__Road/Intersection Name_Trinity Circle | 0.0035 |
| remainder__month | 0.0034 |
| categorical__Weather Conditions_Windy | 0.0034 |
| categorical__Weather Conditions_Overcast | 0.0033 |
| remainder__is_holiday | 0.0033 |
| categorical__Weather Conditions_Fog | 0.0032 |
| categorical__Road/Intersection Name_Marathahalli Bridge | 0.0032 |
| categorical__Road/Intersection Name_ITPL Main Road | 0.0031 |
| categorical__Road/Intersection Name_CMH Road | 0.0027 |
| categorical__Road/Intersection Name_Ballari Road | 0.0026 |
| categorical__Road/Intersection Name_Sony World Junction | 0.0025 |
| remainder__is_event_day | 0.0025 |
| categorical__Road/Intersection Name_Jayanagar 4th Block | 0.0020 |
| categorical__Road/Intersection Name_South End Circle | 0.0020 |
| categorical__Road/Intersection Name_Tumkur Road | 0.0019 |
| categorical__Road/Intersection Name_Yeshwanthpur Circle | 0.0018 |
| categorical__Road/Intersection Name_Hosur Road | 0.0010 |
| categorical__Road/Intersection Name_Silk Board Junction | 0.0007 |
| remainder__is_weekend | 0.0000 |
