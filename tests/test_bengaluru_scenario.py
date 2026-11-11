"""Fast static checks for the isolated Bengaluru scenario artifacts."""
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "sumo" / "bengaluru_osm"
sys.path.insert(0, str(SCENARIO))
from queue_measurement import measure_lane_queue
from label_observations import label_rows


class BengaluruScenarioTests(unittest.TestCase):
    def test_network_is_additive_and_scenario_declares_corridor_anchors(self):
        for name in ("bengaluru_osm_sim.net.xml", "bengaluru_osm.net.xml"):
            network = SCENARIO / name
            pointer = SCENARIO / f"{name}.dvc"
            if network.is_file():
                self.assertGreater(network.stat().st_size, 1_000_000)
            else:
                # A clean Git checkout may contain only the DVC pointer. The
                # actual network is a large DVC-managed input and CI must not
                # need remote credentials just to run unit tests.
                self.assertTrue(pointer.is_file(), f"Missing network and DVC pointer: {name}")
                pointer_text = pointer.read_text(encoding="utf-8")
                self.assertIn("md5:", pointer_text)
        data = json.loads((SCENARIO / "scenario.json").read_text(encoding="utf-8"))
        self.assertEqual(set(data["anchors"]), {"silk_board", "hsr_layout", "koramangala"})

    def test_demo_routes_have_all_vehicle_classes_and_anchor_paths(self):
        root = ET.parse(SCENARIO / "traffic.rou.xml").getroot()
        route_ids = {e.get("id") for e in root.findall("route")}
        vehicle_types = {e.get("id") for e in ET.parse(SCENARIO / "vtypes.add.xml").getroot().findall("vType")}
        self.assertEqual(len(route_ids), 6)
        self.assertEqual(vehicle_types, {"two_wheeler", "car", "auto_rickshaw", "bus", "truck"})
        self.assertEqual(len(root.findall("vehicle")), 45)
        self.assertTrue(all(v.get("route") in route_ids and v.get("type") in vehicle_types for v in root.findall("vehicle")))

    def test_prediction_controller_requires_validated_network_model(self):
        source = (SCENARIO / "controller.py").read_text(encoding="utf-8")
        self.assertIn('meta.get("validation_status")!="passed"', source)
        self.assertIn('meta.get("network")!="bengaluru_osm_sim.net.xml"', source)

    def test_physical_queue_contiguous_stopped_vehicles_and_legacy_proxy(self):
        q = measure_lane_queue([
            {"lanePosition": 20.0, "length": 4.0, "speed": 0.0},
            {"lanePosition": 14.0, "length": 4.0, "speed": 0.0},  # 2 m gap
            {"lanePosition": 5.0, "length": 4.0, "speed": 0.0},   # separated queue
            {"lanePosition": 25.0, "length": 4.0, "speed": 2.0}, # moving
        ])
        self.assertEqual(q["queue_length_m"], 10.0)
        self.assertEqual(q["queue_vehicle_count"], 2)
        self.assertEqual(q["halting_vehicle_count"], 3)
        self.assertEqual(q["queue_proxy_5m"], 15.0)

    def test_future_labels_match_exact_lane_and_exact_horizon(self):
        base = {"run_id":"r1", "intersection_id":"tls1", "approach_id":"edge",
                "lane_id":"edge_0", "time_s":"0", "queue_length_m":"3.0"}
        future = {**base, "time_s":"60", "queue_length_m":"8.0"}
        other_lane = {**future, "lane_id":"edge_1", "queue_length_m":"99"}
        labelled = label_rows([base, future, other_lane])
        self.assertEqual(len(labelled), 1)
        self.assertEqual(labelled[0]["queue_length_m_t_plus_60s"], "8.0")

    def test_duplicate_observation_key_is_rejected(self):
        row = {"run_id":"r1", "intersection_id":"tls1", "approach_id":"edge",
               "lane_id":"edge_0", "time_s":"0", "queue_length_m":"3.0"}
        with self.assertRaises(ValueError):
            label_rows([row, dict(row)])


if __name__ == "__main__":
    unittest.main()
