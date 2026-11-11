import csv
import tempfile
import unittest
from pathlib import Path

from sumo.generate_perimeter_routes import (
    demand_scenarios,
    generate_perimeter_routes,
    network_route_catalog,
    road_level_medians,
)
from sumo.model_contract_60s import FEATURES, validate_model_feature_schema
from sumo.run_policy_matrix import expected_outputs


ROOT = Path(__file__).resolve().parents[1]
NETWORK = ROOT / "sumo" / "grid_network_tls.net.xml"
BASELINE = ROOT / "sumo" / "traffic.rou.xml"


class PerimeterRouteGenerationTests(unittest.TestCase):
    def write_sample_csv(self, path):
        with path.open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=["Road/Intersection Name", "Traffic Volume"])
            writer.writeheader()
            for index, volume in enumerate((100, 200, 300, 400)):
                writer.writerow({"Road/Intersection Name": f"Road {index}", "Traffic Volume": volume})

    def test_road_median_quartile_scenarios_are_scaled_from_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "traffic.csv"
            self.write_sample_csv(source)
            medians = road_level_medians(source)
            scenarios = demand_scenarios(medians, 900)
        self.assertEqual(scenarios["low"]["vehicle_count"], 630)
        self.assertEqual(scenarios["reference"]["vehicle_count"], 900)
        self.assertEqual(scenarios["high"]["vehicle_count"], 1170)

    def test_network_has_64_connected_perimeter_pairs(self):
        entries, exits, routes = network_route_catalog(NETWORK)
        self.assertEqual(len(entries), 8)
        self.assertEqual(len(exits), 8)
        self.assertEqual(len(routes), 64)

    def test_generated_routes_have_expected_counts_balanced_od_and_repeatable_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "traffic.csv"
            self.write_sample_csv(source)
            out_a, out_b = root / "routes_a", root / "routes_b"
            manifest_a, manifest_b = root / "manifest_a.csv", root / "manifest_b.csv"
            generate_perimeter_routes(source, NETWORK, BASELINE, out_a, manifest_a, seed=19)
            generate_perimeter_routes(source, NETWORK, BASELINE, out_b, manifest_b, seed=19)
            for scenario, expected in (("low", 630), ("reference", 900), ("high", 1170)):
                first = (out_a / f"traffic_{scenario}.rou.xml").read_bytes()
                second = (out_b / f"traffic_{scenario}.rou.xml").read_bytes()
                self.assertEqual(first, second)
                import xml.etree.ElementTree as ET
                vehicles = ET.fromstring(first).findall("vehicle")
                self.assertEqual(len(vehicles), expected)
                departures = [float(vehicle.get("depart")) for vehicle in vehicles]
                self.assertEqual(departures, sorted(departures))

    def test_generator_refuses_to_overwrite_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "traffic.csv"
            self.write_sample_csv(source)
            output = root / "routes"
            manifest = root / "manifest.csv"
            generate_perimeter_routes(source, NETWORK, BASELINE, output, manifest, seed=7)
            with self.assertRaises(FileExistsError):
                generate_perimeter_routes(source, NETWORK, BASELINE, output, manifest, seed=7)

    def test_predictive_model_feature_contract_is_checked_in_order(self):
        class Model:
            feature_names_in_ = list(FEATURES)

        self.assertTrue(validate_model_feature_schema(Model()))
        Model.feature_names_in_ = list(reversed(FEATURES))
        with self.assertRaisesRegex(ValueError, "feature schema"):
            validate_model_feature_schema(Model())

    def test_policy_output_names_are_separate_and_run_specific(self):
        fixed = expected_outputs("fixed", "perimeter_trial_low", 21)
        adaptive = expected_outputs("adaptive", "perimeter_trial_low", 21)
        predictive = expected_outputs("predictive60s", "perimeter_trial_low", 21)
        all_outputs = fixed + adaptive + predictive
        self.assertEqual(len(all_outputs), 9)
        self.assertEqual(len(set(all_outputs)), len(all_outputs))
        self.assertTrue(all("perimeter_trial_low_seed21" in str(path) for path in all_outputs))


if __name__ == "__main__":
    unittest.main()
