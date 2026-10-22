"""
Diagnostic: why is the model score low, and is there room to improve?
Run from the project root:  python diagnose.py
Read-only: does not change any project files. Do not commit this file.
"""
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score

PATH = "data/processed/traffic_features.csv"
TARGET = "Traffic Volume"

df = pd.read_csv(PATH, parse_dates=["Date"]).sort_values("Date")
cutoff = df["Date"].quantile(0.8, interpolation="nearest")
train, test = df[df["Date"] < cutoff], df[df["Date"] >= cutoff]
y_test = test[TARGET]


def report(name, preds):
    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
    print(f"{name:<52} RMSE {rmse:>9,.0f}   R2 {r2_score(y_test, preds):>7.3f}")


def group_mean_model(cols):
    means = train.groupby(cols)[TARGET].mean()
    key = test[cols].apply(tuple, axis=1) if len(cols) > 1 else test[cols[0]]
    preds = key.map(means if len(cols) == 1 else means.to_dict())
    return preds.fillna(train[TARGET].mean())


print("Time-aware split. All scores are on the TEST period.\n")
report("1. Always predict the training average",
       np.full(len(test), train[TARGET].mean()))
report("2. Average per road",
       group_mean_model(["road_encoded"]))
report("3. Average per area + road",
       group_mean_model(["area_encoded", "road_encoded"]))
report("4. Average per road + day of week",
       group_mean_model(["road_encoded", "day_of_week"]))

# Linear Regression with proper one-hot encoding instead of number codes
cats = ["road_encoded", "area_encoded", "weather_encoded",
        "day_of_week", "month"]
others = ["is_weekend", "is_holiday", "is_event_day", "roadwork_flag"]
X_all = pd.get_dummies(df[cats + others], columns=cats)
X_tr, X_te = X_all.loc[train.index], X_all.loc[test.index]
lr = LinearRegression().fit(X_tr, train[TARGET])
report("5. Linear Regression, one-hot encoded", lr.predict(X_te))

# How much of the variation is unexplainable noise at road level?
g = df.groupby(["area_encoded", "road_encoded"])[TARGET]
within = (df[TARGET] - g.transform("mean")).var()
print(f"\nShare of total variance that remains inside a single "
      f"area+road: {within / df[TARGET].var():.0%}")
print("(Anything the features cannot separate within that group is "
      "noise to a model.)")