# Model Results

| Run | Split | RMSE | MAE | R2 |
|---|---|---|---|---|
| Linear Regression | random | 12744.5 | 10397.2 | 0.007 |
| Random Forest | random | 10764.5 | 8660.5 | 0.292 |
| XGBoost | random | 10601.4 | 8531.3 | 0.313 |
| Linear Regression | time-aware | 12773.5 | 10446.6 | 0.006 |
| Random Forest | time-aware | 10968.4 | 8863.9 | 0.267 |
| XGBoost | time-aware | 10856.4 | 8761.2 | 0.282 |

## XGBoost feature importance (saved model)

| Feature | Importance |
|---|---|
| area_encoded | 0.723 |
| road_encoded | 0.097 |
| weather_encoded | 0.034 |
| roadwork_flag | 0.033 |
| day_of_week | 0.031 |
| month | 0.031 |
| is_holiday | 0.027 |
| is_event_day | 0.025 |
| is_weekend | 0.000 |
| weekday_flag | 0.000 |
