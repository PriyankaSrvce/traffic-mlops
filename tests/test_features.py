import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.features.build_features import run_pipeline, validate_required_values


class FeaturePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

        self.raw_path = self.root / "traffic.csv"
        self.events_path = self.root / "events.csv"
        self.output_path = self.root / "processed" / "traffic_features.csv"

        pd.DataFrame(
            {
                "Date": ["2022-01-01", "2022-01-02", "2022-01-03", "2022-01-04"],
                "Area Name": ["Area A", "Area A", "Area B", "Area B"],
                "Road/Intersection Name": ["Road 1", "Road 1", "Road 2", "Road 2"],
                "Traffic Volume": [100, 200, 300, 1000],
                "Average Speed": [30.0, 31.0, 32.0, 33.0],
                "Weather Conditions": ["Clear", "Rain", "Clear", "Windy"],
                "Roadwork and Construction Activity": ["No", "Yes", "No", "No"],
            }
        ).to_csv(self.raw_path, index=False)
        pd.DataFrame(
            {
                "event_date": ["2022-01-01"],
                "event_name": ["Test event"],
                "event_type": ["test"],
            }
        ).to_csv(self.events_path, index=False)

    def test_pipeline_keeps_iqr_outlier_and_writes_expected_interface(self):
        result = run_pipeline(
            self.raw_path,
            self.events_path,
            self.output_path,
        )

        self.assertEqual(len(result), 4)
        self.assertIn(1000, result["Traffic Volume"].tolist())
        self.assertEqual(result.shape[1], 12)
        self.assertTrue(self.output_path.is_file())
        self.assertFalse(result.isna().any().any())
        self.assertEqual(int(result["is_event_day"].sum()), 1)

    def test_pipeline_output_is_repeatable(self):
        first = run_pipeline(self.raw_path, self.events_path, self.output_path)
        first_file = pd.read_csv(self.output_path, parse_dates=["Date"])
        second = run_pipeline(self.raw_path, self.events_path, self.output_path)
        second_file = pd.read_csv(self.output_path, parse_dates=["Date"])
        pd.testing.assert_frame_equal(first, second)
        pd.testing.assert_frame_equal(first_file, second_file)

    def test_blank_required_category_is_rejected(self):
        frame = pd.DataFrame(
            {
                "Date": pd.to_datetime(["2022-01-01"]),
                "Area Name": [" "],
                "Road/Intersection Name": ["Road 1"],
                "Traffic Volume": [100],
                "Weather Conditions": ["Clear"],
                "Roadwork and Construction Activity": ["No"],
            }
        )
        with self.assertRaisesRegex(ValueError, "blank required values"):
            validate_required_values(frame)


if __name__ == "__main__":
    unittest.main()
