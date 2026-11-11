"""Artifact-independent unit tests for the validated Bengaluru API contract."""
import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import joblib
import numpy as np
from pydantic import ValidationError

from src.api.app import (
    FEATURES,
    HORIZON_SECONDS,
    MODEL_VERSION,
    TARGET,
    PredictionRequest,
    create_app,
    features_from_request,
    load_model,
)

VALID={"queue_length_m":2.5,"vehicle_count":8,"halting_vehicle_count":3,"mean_speed_mps":4.2,"phase_elapsed_s":18.0,
"intersection_id":"4105324822","approach_id":"1109948890#1","lane_id":"1109948890#1_0","signal_phase_id":"1","signal_state":"GGrr",
"vehicle_composition":"balanced_assumed"}
class FakeModel:
 def __init__(self,features,out=(2.5,)):
  self.feature_names_in_=np.asarray(features)
  self.out=np.asarray(out,dtype=float)
 def predict(self,x):
  if list(x.columns)!=list(self.feature_names_in_):raise ValueError("feature order mismatch")
  return self.out

def endpoint(application,path):return next(r.endpoint for r in application.routes if r.path==path)

class BengaluruApiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp_dir=TemporaryDirectory()
  cls.root=Path(cls.temp_dir.name)
  cls.model_path=cls.root/"test_model.joblib"
  cls.metadata_path=cls.root/"test_model.json"
  joblib.dump(FakeModel(FEATURES),cls.model_path)
  digest=hashlib.sha256(cls.model_path.read_bytes()).hexdigest()
  cls.metadata={
   "model_version":MODEL_VERSION,
   "sha256":digest,
   "target":TARGET,
   "horizon_seconds":HORIZON_SECONDS,
   "features":FEATURES,
   "network":"bengaluru_osm_sim.net.xml",
   "validation_status":"passed",
  }
  cls.metadata_path.write_text(json.dumps(cls.metadata),encoding="utf-8")

 @classmethod
 def tearDownClass(cls):
  cls.temp_dir.cleanup()

 def setUp(self):
  self.application=create_app(self.model_path,self.metadata_path)

 def test_valid_request_uses_bengaluru_feature_order(self):
  req=PredictionRequest(**VALID);df=features_from_request(req)
  self.assertEqual(list(df.columns),FEATURES);self.assertEqual(df.loc[0,"vehicle_composition"],"balanced_assumed")
 def test_negative_or_nonfinite_input_rejected(self):
  for key,value in (("queue_length_m",-1),("mean_speed_mps",float("inf"))):
   with self.assertRaises(ValidationError):PredictionRequest(**{**VALID,key:value})
 def test_halting_count_cannot_exceed_lane_count(self):
  with self.assertRaises(ValidationError):PredictionRequest(**{**VALID,"vehicle_count":1,"halting_vehicle_count":2})
 def test_bad_profile_and_unknown_fields_rejected(self):
  with self.assertRaises(ValidationError):PredictionRequest(**{**VALID,"vehicle_composition":"measured_bengaluru"})
  with self.assertRaises(ValidationError):PredictionRequest(**{**VALID,"future_queue_length_m":4})
 def test_missing_model_is_not_ready(self):
  x=create_app(Path("missing-bengaluru-model.joblib"));self.assertIsNone(x.state.model)
 def test_health_and_model_info_reflect_validation(self):
  self.assertEqual(endpoint(self.application,"/api/v1/health")()["status"],"ok")
  info=endpoint(self.application,"/api/v1/model-info")();self.assertEqual(info["network"],"bengaluru_osm_sim.net.xml");self.assertEqual(info["validation_status"],"passed")
 def test_prediction_endpoint_returns_model_version_and_horizon(self):
  response=endpoint(self.application,"/api/v1/predict")(PredictionRequest(**VALID))
  self.assertEqual(response["target"],"queue_length_m_t_plus_60s");self.assertEqual(response["horizon_seconds"],60)
  self.assertGreaterEqual(response["predicted_queue_length_m"],0);self.assertEqual(response["model_version"],MODEL_VERSION)
 def test_prediction_is_finite_nonnegative(self):
  model,digest,meta=load_model(self.model_path,metadata_path=self.metadata_path)
  self.assertEqual(digest,meta["sha256"])
  req=PredictionRequest(**VALID);result=np.asarray(model.predict(features_from_request(req,meta["features"])),dtype=float)
  self.assertTrue(np.isfinite(result[0]));self.assertGreaterEqual(result[0],0)
 def test_hash_mismatch_prevents_deserialization(self):
  with TemporaryDirectory() as td:
   folder=Path(td);mp=folder/"bad.joblib";mp.write_bytes(b"untrusted")
   meta={"validation_status":"passed","network":"bengaluru_osm_sim.net.xml","features":FEATURES,"sha256":"0"*64}
   mpath=folder/"bad.json";mpath.write_text(json.dumps(meta))
   with patch("src.api.app.joblib.load") as loader:
    with self.assertRaisesRegex(ValueError,"SHA-256"):load_model(mp,"0"*64,mpath)
    loader.assert_not_called()
 def test_unvalidated_metadata_rejected(self):
  with TemporaryDirectory() as td:
   folder=Path(td);mp=folder/"x.joblib";mp.write_bytes(b"x");meta=folder/"x.json";meta.write_text(json.dumps({"validation_status":"failed","network":"bengaluru_osm_sim.net.xml","features":FEATURES}))
   with self.assertRaisesRegex(ValueError,"passed Bengaluru validation"):load_model(mp,"0"*64,meta)

if __name__=="__main__":unittest.main()
