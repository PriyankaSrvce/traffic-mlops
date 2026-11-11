"""Run split-by-seed benchmarks and save a non-active versioned candidate."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import joblib,numpy as np,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor,RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler

FEATURES=["queue_length_m","vehicle_count","halting_vehicle_count","mean_speed_mps","phase_elapsed_s","intersection_id","approach_id","lane_id","signal_phase_id","signal_state","vehicle_composition"]
LEGACY_FEATURES=FEATURES[:-1]
TARGET="queue_length_m_t_plus_60s"
NUMERIC=FEATURES[:5]
CATEGORICAL=FEATURES[5:]
ACCEPTANCE={"validation_mae_improvement_vs_persistence_min_fraction":0.05,"test_mae_improvement_vs_persistence_min_fraction":0.05,"validation_rmse_must_not_exceed_persistence":True,"test_rmse_must_not_exceed_persistence":True,"split_unit":"complete SUMO seed across all scenarios","status":"candidate passes only if every numeric gate passes; test set is never used for model selection"}

def sha(path:Path)->str:
 h=hashlib.sha256()
 with path.open("rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()

def metric(y,p):
 y=np.asarray(y,dtype=float);p=np.asarray(p,dtype=float)
 return {"n":int(len(y)),"mae_m":float(mean_absolute_error(y,p)),"rmse_m":float(mean_squared_error(y,p)**.5),"r2":float(r2_score(y,p)) if len(y)>1 else None}

def cast_frame(frame):
 x=frame[FEATURES].copy()
 for c in NUMERIC:x[c]=pd.to_numeric(x[c],errors="raise")
 for c in CATEGORICAL:x[c]=x[c].astype(str)
 return x

def by_groups(frame,preds,group):
 d=frame[[group,TARGET]].copy();d["prediction"]=preds
 return {str(k):metric(g[TARGET],g.prediction) for k,g in d.groupby(group)}

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data",type=Path,default=Path(__file__).resolve().parent/"datasets"/"osm_v2b"/"training_labels_incident_quarantined.csv");ap.add_argument("--report-dir",type=Path,default=Path(__file__).resolve().parent/"datasets"/"osm_v2b"/"model_evaluation");ap.add_argument("--model-dir",type=Path,default=Path(__file__).resolve().parents[2]/"models"/"bengaluru");ap.add_argument("--legacy-model",type=Path,default=Path(__file__).resolve().parents[2]/"models"/"queue_rf_60s_1794296235306388.joblib");a=ap.parse_args()
 data=a.data.resolve();df=pd.read_csv(data)
 required=set(FEATURES+[TARGET,"seed","scenario","run_id"])
 missing=sorted(required-set(df.columns))
 if missing:raise SystemExit(f"Dataset missing columns: {missing}")
 seeds=sorted(df.seed.astype(int).unique())
 train_seeds={7,42,2026};val_seeds={99};test_seeds={123,31415}
 if not train_seeds|val_seeds|test_seeds <= set(seeds):raise SystemExit(f"Required split seeds absent; found {seeds}")
 train=df[df.seed.isin(train_seeds)].copy();val=df[df.seed.isin(val_seeds)].copy();test=df[df.seed.isin(test_seeds)].copy()
 if min(len(train),len(val),len(test))==0:raise SystemExit("Empty split.")
 overlap=(set(train.run_id)&set(val.run_id))|(set(train.run_id)&set(test.run_id))|(set(val.run_id)&set(test.run_id))
 if overlap:raise SystemExit(f"Run leakage across split: {sorted(overlap)[:5]}")
 for x in (train,val,test):
  x[TARGET]=pd.to_numeric(x[TARGET],errors="raise");x["queue_length_m"]=pd.to_numeric(x["queue_length_m"],errors="raise")
 Xtrain=cast_frame(train);Xval=cast_frame(val);Xtest=cast_frame(test)
 num_pipe=make_pipeline(SimpleImputer(strategy="median"),StandardScaler())
 cat_pipe=make_pipeline(SimpleImputer(strategy="most_frequent"),OneHotEncoder(handle_unknown="ignore",min_frequency=25))
 prep=ColumnTransformer([("num",num_pipe,NUMERIC),("cat",cat_pipe,CATEGORICAL)])
 models={
  "linear_regression":make_pipeline(prep,LinearRegression()),
  "random_forest":make_pipeline(prep,RandomForestRegressor(n_estimators=120,max_depth=16,min_samples_leaf=5,max_features=0.9,n_jobs=4,random_state=2026)),
  "hist_gradient_boosting_numeric":make_pipeline(SimpleImputer(strategy="median"),HistGradientBoostingRegressor(max_iter=120,max_leaf_nodes=15,l2_regularization=1.0,random_state=2026))
 }
 ytr=train[TARGET].to_numpy();yv=val[TARGET].to_numpy();yt=test[TARGET].to_numpy()
 persistence_val=metric(yv,val.queue_length_m);persistence_test=metric(yt,test.queue_length_m)
 output={"dataset":str(data),"dataset_sha256":sha(data),"queue_measurement":"contiguous stopped queue from SUMO front positions and actual vehicle lengths; 0.1 m/s threshold; max bumper gap 2.5m","target":TARGET,"horizon_s":60,"features":FEATURES,"train_seeds":sorted(train.seed.unique().astype(int).tolist()),"validation_seeds":sorted(val.seed.unique().astype(int).tolist()),"test_seeds":sorted(test.seed.unique().astype(int).tolist()),"rows":{"train":len(train),"validation":len(val),"test":len(test)},"run_ids":{"train":sorted(train.run_id.unique()),"validation":sorted(val.run_id.unique()),"test":sorted(test.run_id.unique())},"acceptance_criteria":ACCEPTANCE,"persistence":{"validation":persistence_val,"test":persistence_test},"models":{},"legacy_synthetic_transfer":None}
 fitted={}
 for name,model in models.items():
  if name=="hist_gradient_boosting_numeric":
   model.fit(train[NUMERIC].astype(float),ytr);pv=model.predict(val[NUMERIC].astype(float));pt=model.predict(test[NUMERIC].astype(float))
  else:
   model.fit(Xtrain,ytr);pv=model.predict(Xval);pt=model.predict(Xtest)
  val_m=metric(yv,pv);test_m=metric(yt,pt)
  fitted[name]=model
  output["models"][name]={"validation":val_m,"test":test_m,
     "validation_by_demand":by_groups(val,pv,"scenario"),"test_by_demand":by_groups(test,pt,"scenario"),
     "test_by_composition":by_groups(test,pt,"vehicle_composition"),
     "test_by_intersection":by_groups(test,pt,"intersection_id"),"test_by_seed":by_groups(test,pt,"seed"),
     "test_positive_target":metric(test.loc[yt>0,TARGET],np.asarray(pt)[yt>0]) if np.any(yt>0) else None}
 best=min(models,key=lambda n:output["models"][n]["validation"]["mae_m"])
 bm=output["models"][best];vm=output["persistence"]["validation"];tm=output["persistence"]["test"]
 gates={"validation_mae_improves_5pct":bm["validation"]["mae_m"]<=vm["mae_m"]*.95,
        "test_mae_improves_5pct":bm["test"]["mae_m"]<=tm["mae_m"]*.95,
        "validation_rmse_not_worse":bm["validation"]["rmse_m"]<=vm["rmse_m"],
        "test_rmse_not_worse":bm["test"]["rmse_m"]<=tm["rmse_m"]}
 accepted=all(gates.values())
 output["selected_by_validation_mae"]=best;output["acceptance_gate"]=gates;output["validation_status"]="passed" if accepted else "failed"
 # Legacy artifact uses the same ten names but its queue target was trained on a different network/queue proxy.
 if a.legacy_model.exists():
  legacy=joblib.load(a.legacy_model);old=list(getattr(legacy,"feature_names_in_",[]))
  legacy_report={"sha256":sha(a.legacy_model),"feature_names_match":old==LEGACY_FEATURES,"interpretation":"transfer baseline only; training network IDs and queue target semantics differ"}
  if old==LEGACY_FEATURES:
   lx=Xtest[LEGACY_FEATURES].copy();lp=np.asarray(legacy.predict(lx));legacy_report["test"]=metric(yt,lp);legacy_report["test_by_demand"]=by_groups(test.assign(_legacy=lp),lp,"scenario")
  output["legacy_synthetic_transfer"]=legacy_report
 model=fitted[best]
 if best=="hist_gradient_boosting_numeric": model.fit(train[NUMERIC].astype(float),ytr); input_features=NUMERIC
 else: model.fit(Xtrain,ytr); input_features=FEATURES
 a.report_dir=a.report_dir.resolve();a.report_dir.mkdir(parents=True,exist_ok=True);a.model_dir=a.model_dir.resolve();a.model_dir.mkdir(parents=True,exist_ok=True)
 version="bengaluru_queue_v1_2026-11"
 model_path=a.model_dir/(version+".joblib");metadata_path=a.model_dir/(version+".json")
 if model_path.exists() or metadata_path.exists():raise SystemExit(f"Refusing to overwrite existing model version {version}")
 joblib.dump(model,model_path);model_hash=sha(model_path)
 output.update({"model_version":version,"model_path":str(model_path),"model_sha256":model_hash,"model_input_features":input_features,"metadata_path":str(metadata_path)})
 metadata={"model_version":version,"model_path":str(model_path),"sha256":model_hash,"target":TARGET,"horizon_seconds":60,"features":input_features,"all_candidate_features":FEATURES,"network":"bengaluru_osm_sim.net.xml","validation_status":"passed" if accepted else "failed","activation_status":"eligible_for_review" if accepted else "not_activatable","dataset_sha256":sha(data),"evaluation_report":str(a.report_dir/"model_evaluation.json"),"acceptance_criteria":ACCEPTANCE,"queue_measurement_schema":"physical_contiguous_stopped_queue_v2"}
 metadata_path.write_text(json.dumps(metadata,indent=2),encoding="utf-8")
 test_predictions=np.asarray(model.predict(test[input_features].astype(float) if best=="hist_gradient_boosting_numeric" else Xtest))
 pred_df=test[["run_id","seed","scenario","vehicle_composition","intersection_id","approach_id","lane_id","time_s",TARGET]].copy();pred_df["prediction_m"]=test_predictions;pred_df["persistence_m"]=test.queue_length_m.to_numpy();pred_df.to_csv(a.report_dir/"test_predictions.csv",index=False)
 (a.report_dir/"model_evaluation.json").write_text(json.dumps(output,indent=2),encoding="utf-8")
 print(json.dumps({"best":best,"validation_status":output["validation_status"],"acceptance_gate":gates,"persistence_test":tm,"selected_test":bm["test"],"model_path":str(model_path),"sha256":model_hash},indent=2))

if __name__=="__main__":main()
