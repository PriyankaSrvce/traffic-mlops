# Data Dictionary - Bangalore Traffic Dataset

Source: Bangalore's Traffic Pulse (Preetham Gouda, Kaggle),
`data/raw/bangalore_traffic.csv`.
Size: 8,936 rows x 16 columns. Dates: 2022-01-01 to 2024-08-09.
No missing values, no duplicate rows (checked in `notebooks/eda.py`).

Descriptions below are based on the column names and the values we observed.
Units are not stated in the file, so we do not assume any. Check the Kaggle
page before quoting a unit in the report.

"Model input?" means: could this column be known IN ADVANCE when we want to
predict traffic volume? Columns measured at the same time as volume would not
be available at prediction time, so using them would be data leakage.

| # | Column | Type | What it is | Observed values | Model input? |
|---|---|---|---|---|---|
| 1 | Date | date (text in CSV) | Day of the observation. There is no time-of-day column, so the data is daily. | 2022-01-01 to 2024-08-09, 952 distinct dates | Yes - used to build day of week, month, weekend, holiday |
| 2 | Area Name | text | Neighbourhood where the road is | 8 areas; most rows Indiranagar (1,720), fewest Electronic City (552) | Yes |
| 3 | Road/Intersection Name | text | Specific road or junction | 16 roads, e.g. Sony World Junction, Silk Board Junction | Yes |
| 4 | Traffic Volume | integer | Number of vehicles counted. **This is our target.** | 4,233 to 72,039; mean 29,236 | Target (not an input) |
| 5 | Average Speed | decimal | Average vehicle speed | 20.0 to 89.8; mean 39.5 | No - measured with volume |
| 6 | Travel Time Index | decimal | Ratio showing how much longer trips take than free flow | 1.00 to 1.50; mean 1.38 | No - measured with volume |
| 7 | Congestion Level | decimal | Congestion score. Capped at 100; median 92 and the top quartile is exactly 100 | 5.2 to 100; mean 80.8 | No - measured with volume, and saturated |
| 8 | Road Capacity Utilization | decimal | How much of the road's capacity is used. Capped at 100 | 18.7 to 100; mean 92.0 | No - measured with volume |
| 9 | Incident Reports | integer | Number of incidents reported | 0 to 10; mean 1.6 | No - not known in advance |
| 10 | Environmental Impact | decimal | Environmental impact measure. Correlation with volume is about 1.0, so it looks derived from volume | 58.5 to 194.1; mean 108.5 | **No - leakage** |
| 11 | Public Transport Usage | decimal | Share/level of public transport use | 10.0 to 80.0; mean 45.1 | Not used (no correlation with volume, about 0.0, and not known in advance) |
| 12 | Traffic Signal Compliance | decimal | How well drivers obey signals | 60.0 to 100.0; mean 80.0 | Not used (no correlation with volume, not known in advance) |
| 13 | Parking Usage | decimal | Parking occupancy level | 50.0 to 100.0; mean 75.2 | Not used (no correlation with volume, not known in advance) |
| 14 | Pedestrian and Cyclist Count | integer | Number of pedestrians and cyclists | 66 to 243; mean 114.5 | No - measured with volume |
| 15 | Weather Conditions | text | Weather on that day | Clear 60.7%, Overcast 14.5%, Fog 10.7%, Rain 9.3%, Windy 4.8% | Yes (would come from a forecast in real use) |
| 16 | Roadwork and Construction Activity | text (Yes/No) | Whether roadwork is happening | No 90.1%, Yes 9.9% | Yes (roadwork is usually scheduled in advance) |

## Summary of what we use

**Inputs (candidate features):** Date (turned into day of week, month,
weekend, holiday), Area Name, Road/Intersection Name, Weather Conditions,
Roadwork and Construction Activity.

**Target:** Traffic Volume. A Low / Medium / High label is derived from it
using cut-offs fixed from the training data only.

**Excluded:** Average Speed, Travel Time Index, Congestion Level, Road Capacity
Utilization, Incident Reports, Environmental Impact, Pedestrian and Cyclist
Count (same-time measurements or leakage), plus Public Transport Usage,
Traffic Signal Compliance and Parking Usage (not known in advance and showed
no relationship with volume in the EDA).

## Findings that shape the model

- Location is the strongest signal. Road alone explains about 34% of the
  variance in Traffic Volume (R2 = 0.34).
- Day of week, month, year and weather show almost no effect on volume
  (weekend vs weekday -0.7%).
