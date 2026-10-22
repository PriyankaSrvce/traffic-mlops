import unittest

import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from src.models.train import FEATURES, DATE_COL, TARGET, make_pipeline, make_time_split


class TrainingPipelineTests(unittest.TestCase):
    def test_time_split_keeps_each_date_in_one_partition(self):
        frame = pd.DataFrame(
            {
                DATE_COL: pd.date_range("2024-01-01", periods=10).repeat(2),
                "Area Name": ["Area A", "Area B"] * 10,
                "Road/Intersection Name": ["Road A", "Road B"] * 10,
                "Weather Conditions": ["Clear"] * 20,
                "day_of_week": [0] * 20,
                "month": [1] * 20,
                "is_weekend": [0] * 20,
                "is_holiday": [0] * 20,
                "is_event_day": [0] * 20,
                "roadwork_flag": [0] * 20,
                "weekday_flag": [1] * 20,
                TARGET: list(range(20)),
            }
        )
        (X_train, X_test, y_train, y_test), details = make_time_split(frame)

        train_dates = set(frame.loc[X_train.index, DATE_COL])
        test_dates = set(frame.loc[X_test.index, DATE_COL])
        self.assertFalse(train_dates & test_dates)
        self.assertEqual(len(y_train) + len(y_test), len(frame))
        self.assertEqual(details["train_dates"] + details["test_dates"], 10)

    def test_encoder_ignores_categories_not_seen_during_fit(self):
        train = pd.DataFrame(
            {
                "Area Name": ["Area A", "Area B", "Area A"],
                "Road/Intersection Name": ["Road A", "Road B", "Road A"],
                "Weather Conditions": ["Clear", "Rain", "Clear"],
                "day_of_week": [0, 1, 2],
                "month": [1, 1, 1],
                "is_weekend": [0, 0, 0],
                "is_holiday": [0, 0, 0],
                "is_event_day": [0, 0, 0],
                "roadwork_flag": [0, 1, 0],
            },
            columns=FEATURES,
        )
        model = make_pipeline(RandomForestRegressor(n_estimators=2, random_state=1))
        model.fit(train, [100, 200, 150])
        unseen = train.iloc[[0]].copy()
        unseen["Area Name"] = "New Area"
        prediction = model.predict(unseen)
        self.assertEqual(len(prediction), 1)


if __name__ == "__main__":
    unittest.main()
