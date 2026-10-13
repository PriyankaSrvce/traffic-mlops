# Data Preparation and Feature Engineering Methodology

## 1. Dataset

The Bangalore traffic dataset contains 8,936 records covering daily traffic observations.

The dataset contains the following main fields used during feature engineering:

- Date
- Area Name
- Road/Intersection Name
- Traffic Volume
- Weather Conditions
- Roadwork and Construction Activity

The dataset contains daily observations, so no hour-of-day or rush-hour information is available.

---

## 2. Data Validation

Before feature engineering, the required raw dataset columns were validated.

The following columns were confirmed:

- Date
- Area Name
- Road/Intersection Name
- Traffic Volume
- Weather Conditions
- Roadwork and Construction Activity

The Date column was converted into a datetime format for calendar-based feature generation.

---

## 3. Columns Excluded from Model Inputs

Based on the EDA and data analysis performed by Member B, the following columns were excluded from the feature set:

- Average Speed
- Travel Time Index
- Congestion Level
- Road Capacity Utilization
- Incident Reports
- Environmental Impact
- Pedestrian and Cyclist Count
- Public Transport Usage
- Traffic Signal Compliance
- Parking Usage

These columns were not used as model input features because they were identified during the data analysis as unsuitable for the planned traffic-volume prediction model.

---

## 4. Calendar Feature Engineering

The Date column was used to create calendar-based features:

### Day of Week

The day of the week was extracted from the Date column.

The values range from:

- 0 = Monday
- 1 = Tuesday
- 2 = Wednesday
- 3 = Thursday
- 4 = Friday
- 5 = Saturday
- 6 = Sunday

### Month

The month was extracted from the Date column.

### Weekend Flag

A binary `is_weekend` feature was created:

- 0 = Weekday
- 1 = Weekend

### Indian Holiday Flag

The `holidays` Python library was used to identify Indian public holidays.

A binary `is_holiday` feature was created:

- 0 = Not an Indian public holiday
- 1 = Indian public holiday

---

## 5. Categorical Feature Encoding

The categorical variables were converted into numerical representations for use by machine-learning models.

The following encoded features were created:

- `area_encoded`
- `road_encoded`
- `weather_encoded`

The roadwork information was converted into a binary feature:

- `roadwork_flag = 0` when there was no roadwork
- `roadwork_flag = 1` when roadwork/construction activity was present

---

## 6. Event-Day Enrichment

An additional event dataset was created at:

`src/features/bangalore_events.csv`

The event dataset contains:

- Event date
- Event name
- Event type

The event information was used to create the `is_event_day` feature.

This feature indicates whether a traffic observation occurred on one of the defined event dates:

- 0 = Normal day
- 1 = Event day

The event file contains 5 event dates.

After applying the event-day enrichment, 40 observations in the traffic dataset were marked as event days.

This feature was included as the original data-enrichment component of Member C's work.

---

## 7. IQR-Based Outlier Detection

Interquartile Range (IQR) based outlier detection was applied to the `Traffic Volume` column.

The method uses:

- First quartile (Q1)
- Third quartile (Q3)
- IQR = Q3 - Q1

The outlier limits were calculated using the standard 1.5 × IQR rule.

For the dataset:

- Q1 = 19,413.00
- Q3 = 38,058.50
- IQR = 18,645.50
- Lower bound = -8,555.25
- Upper bound = 66,026.75

Observations outside these bounds were treated as outliers and removed.

A total of:

**24 outlier rows out of 8,936 rows (0.27%)**

were removed.

The resulting dataset contains:

**8,912 rows**

after outlier removal.

The IQR method was selected because it provides a simple distribution-based method for identifying unusually high or low traffic-volume observations without assuming a normal distribution.

---

## 8. Weekday Interaction Feature

The original feature-engineering requirement included a weekday interaction feature.

The dataset contains daily observations and does not contain an hour-of-day column. Therefore, a true rush-hour feature cannot be calculated from this dataset.

Instead, the interaction was represented using:

`weekday_flag`

where:

- 0 = Weekend
- 1 = Weekday

This preserves the intended weekday-based interaction without incorrectly claiming that the dataset contains rush-hour information.

---

## 9. Final Feature Dataset

The final processed dataset contains:

- Date
- day_of_week
- month
- is_weekend
- is_holiday
- is_event_day
- area_encoded
- road_encoded
- weather_encoded
- roadwork_flag
- weekday_flag
- Traffic Volume

`Traffic Volume` is retained as the target variable.

The `Date` column is also retained because it is needed for the later time-aware model development and evaluation process.

---

## 10. Final Output

The processed feature dataset was generated at:

`data/processed/traffic_features.csv`

Final dataset:

- Rows: 8,912
- Columns: 12

This file represents the completed Member C feature-engineering output and will be used by the next project stage for model development.