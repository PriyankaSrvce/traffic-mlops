import unittest
import pandas as pd
from sumo.bengaluru_osm.monitoring import psi
from sumo.bengaluru_osm.record_feedback import build_feedback

class BengaluruMonitoringTests(unittest.TestCase):
    def test_psi_is_zero_for_same_distribution_and_detects_shift(self):
        values=[0,0,1,2,3,4,5,6,7,8]
        self.assertAlmostEqual(psi(values,values),0.0,places=12)
        self.assertGreater(psi(values,[20]*len(values)),0.25)

    def test_feedback_joins_exact_keys_and_records_model_provenance(self):
        obs=pd.DataFrame([{"run_id":"run1","seed":123,"scenario":"low","vehicle_composition":"balanced_assumed",
          "intersection_id":"tls1","approach_id":"a1","lane_id":"a1_0","time_s":10,"queue_length_m_t_plus_60s":4.0}])
        pred=obs[["run_id","seed","scenario","vehicle_composition","intersection_id","approach_id","lane_id","time_s"]].copy()
        pred["prediction_m"]=3.0
        result=build_feedback(obs,pred,{"model_version":"bengaluru-v1"},"abc123")
        self.assertEqual(result.loc[0,"prediction_error_m"],-1.0)
        self.assertEqual(result.loc[0,"feedback_model_version"],"bengaluru-v1")
        self.assertEqual(result.loc[0,"feedback_source"],"held_out_sumo_replay")

    def test_feedback_rejects_incomplete_alignment(self):
        obs=pd.DataFrame([{"run_id":"run1","seed":1,"scenario":"low","vehicle_composition":"balanced_assumed",
          "intersection_id":"tls1","approach_id":"a1","lane_id":"a1_0","time_s":10,"queue_length_m_t_plus_60s":4.0}])
        pred=obs.drop(columns=["queue_length_m_t_plus_60s"]).copy();pred["prediction_m"]=1.0;pred.loc[0,"lane_id"]="wrong"
        with self.assertRaises(ValueError):build_feedback(obs,pred,{"model_version":"v1"},"hash")

if __name__=="__main__":unittest.main()
