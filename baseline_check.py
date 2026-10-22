import numpy as np, pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

df = pd.read_csv("data/processed/traffic_features.csv", parse_dates=["Date"])
cut = pd.Timestamp("2024-02-01")
train, test = df[df.Date < cut], df[df.Date >= cut]

road_mean = train.groupby("road_encoded")["Traffic Volume"].mean()
pred = test["road_encoded"].map(road_mean).fillna(train["Traffic Volume"].mean())

print("MAE ", mean_absolute_error(test["Traffic Volume"], pred))
print("RMSE", np.sqrt(mean_squared_error(test["Traffic Volume"], pred)))
print("R2  ", r2_score(test["Traffic Volume"], pred))