"""Two-stage candidate for the sparse zero-inflated queue target."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import joblib,numpy as np,pandas as pd
from bengaluru_model import HurdleQueueModel
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier,RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder,StandardScaler

FEATURES=["queue_length_m","vehicle_count","halting_vehicle_count","mean_speed_mps","phase_elapsed_s","intersection_id","approach_id","lane_id","signal_phase_id","signal_state","vehicle_composition"]
NUMERIC=FEATURES[:5];CATEGORICAL=FEATURES[5:];TARGET="queue_length_m_t_plus_60s"
def metrics(y,p):
 y=np.asarray(y,float);p=np.asarray(p,float)
 return {"n":int(len(y)),"mae_m":float(mean_absolute_error(y,p)),"rmse_m":float(mean_squared_error(y,p)**.5),"r2":float(r2_score(y,p))}
def grouped(frame,preds,key):
 x=frame[[key,TARGET]].copy();x["pred"]=preds
 return {str(k):metrics(g[TARGET],g.pred) for k,g in x.groupby(key)}
def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--data",type=Path,default=Path(__file__).resolve().parent/"datasets"/"osm_v2b"/"training_labels_incident_quarantined.csv");ap.add_argument("--output-dir",type=Path,default=Path(__file__).resolve().parent/"datasets"/"osm_v2b"/"hurdle_evaluation");ap.add_argument("--model-dir",type=Path,default=Path(__file__).resolve().parents[2]/"models"/"bengaluru");a=ap.parse_args()
 df=pd.read_csv(a.data);missing=set(FEATURES+[TARGET,"seed","scenario","run_id"])-set(df.columns)
 if missing:raise SystemExit(f"Missing columns: {sorted(missing)}")
 train=df[df.seed.isin([7,42,2026])].copy();val=df[df.seed.eq(99)].copy();test=df[df.seed.isin([123,31415])].copy()
 if set(train.run_id)&(set(val.run_id)|set(test.run_id)) or set(val.run_id)&set(test.run_id):raise SystemExit("Run overlap")
 for f in NUMERIC+[TARGET]:
  train[f]=pd.to_numeric(train[f]);val[f]=pd.to_numeric(val[f]);test[f]=pd.to_numeric(test[f])
 for d in (train,val,test):
  for f in CATEGORICAL:d[f]=d[f].astype(str)
 prep=ColumnTransformer([("num",make_pipeline(SimpleImputer(strategy="median"),StandardScaler()),NUMERIC),
                         ("cat",make_pipeline(SimpleImputer(strategy="most_frequent"),OneHotEncoder(handle_unknown="ignore",min_frequency=25)),CATEGORICAL)])
 clf=make_pipeline(clone(prep),RandomForestClassifier(n_estimators=120,max_depth=16,min_samples_leaf=5,max_features=.9,class_weight="balanced_subsample",n_jobs=4,random_state=31415))
 reg=make_pipeline(clone(prep),RandomForestRegressor(n_estimators=120,max_depth=16,min_samples_leaf=3,max_features=.9,n_jobs=4,random_state=2026))
 Xtr=train[FEATURES];Xv=val[FEATURES];Xt=test[FEATURES];ytr=train[TARGET].to_numpy();yv=val[TARGET].to_numpy();yt=test[TARGET].to_numpy()
 clf.fit(Xtr,(ytr>0).astype(int));positive=ytr>0
 if positive.sum()<50:raise SystemExit("Not enough positive queue rows for conditional magnitude model")
 reg.fit(Xtr.loc[positive],ytr[positive])
 pv=clf.predict_proba(Xv)[:,1];rv=np.maximum(0,reg.predict(Xv));pt=clf.predict_proba(Xt)[:,1];rt=np.maximum(0,reg.predict(Xt))
 persistence_val=metrics(yv,val.queue_length_m);persistence_test=metrics(yt,test.queue_length_m)
 thresholds=sorted(set([0.01,*np.quantile(pv,np.linspace(.05,.95,37)).tolist(),.99]))
 threshold=min(thresholds,key=lambda th:metrics(yv,np.where(pv>=th,rv,0))["mae_m"])
 pred_val=np.where(pv>=threshold,rv,0);pred_test=np.where(pt>=threshold,rt,0)
 valm=metrics(yv,pred_val);testm=metrics(yt,pred_test)
 gates={"validation_mae_improves_5pct":valm["mae_m"]<=persistence_val["mae_m"]*.95,"test_mae_improves_5pct":testm["mae_m"]<=persistence_test["mae_m"]*.95,"validation_rmse_not_worse":valm["rmse_m"]<=persistence_val["rmse_m"],"test_rmse_not_worse":testm["rmse_m"]<=persistence_test["rmse_m"]}
 accepted=all(gates.values());model=HurdleQueueModel(clf,reg,threshold,FEATURES)
 a.model_dir=a.model_dir.resolve();a.output_dir=a.output_dir.resolve();a.model_dir.mkdir(parents=True,exist_ok=True);a.output_dir.mkdir(parents=True,exist_ok=True)
 version="bengaluru_queue_hurdle_v1_2026-11";mp=a.model_dir/(version+".joblib");meta_path=a.model_dir/(version+".json")
 if mp.exists() or meta_path.exists():raise SystemExit(f"Refusing to overwrite {version}")
 joblib.dump(model,mp);model_hash=sha(mp)
 report={"model_version":version,"dataset":str(a.data.resolve()),"dataset_sha256":sha(a.data),"train_seeds":[7,42,2026],"validation_seeds":[99],"test_seeds":[123,31415],"split_by_complete_seed":True,"target":TARGET,"queue_definition":"contiguous stopped vehicles using positions/lengths, 0.1m/s halt cutoff, 2.5m max gap","horizon_s":60,"features":FEATURES,"queue_present_classifier_threshold":threshold,"validation":valm,"test":testm,"persistence":{"validation":persistence_val,"test":persistence_test},"test_by_demand":grouped(test,pred_test,"scenario"),"test_by_composition":grouped(test,pred_test,"vehicle_composition"),"test_by_intersection":grouped(test,pred_test,"intersection_id"),"positive_target_test":metrics(test.loc[yt>0,TARGET],pred_test[yt>0]),"acceptance_gate":gates,"validation_status":"passed" if accepted else "failed","model_sha256":model_hash,"model_path":str(mp)}
 (a.output_dir/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
 out=test[["run_id","seed","scenario","vehicle_composition","intersection_id","approach_id","lane_id","time_s",TARGET]].copy();out["prediction_m"]=pred_test;out["positive_probability"]=pt;out["persistence_m"]=test.queue_length_m.to_numpy();out.to_csv(a.output_dir/"test_predictions.csv",index=False)
 meta={"model_version":version,"sha256":model_hash,"model_path":str(mp),"target":TARGET,"horizon_seconds":60,"features":FEATURES,"network":"bengaluru_osm_sim.net.xml","validation_status":report["validation_status"],"activation_status":"eligible_for_review" if accepted else "not_activatable","dataset_sha256":report["dataset_sha256"],"evaluation_report":str(a.output_dir/"report.json"),"queue_measurement_schema":"physical_contiguous_stopped_queue_v2","threshold":threshold}
 meta_path.write_text(json.dumps(meta,indent=2),encoding="utf-8")
 print(json.dumps({"validation_status":report["validation_status"],"threshold":threshold,"gates":gates,"persistence_test":persistence_test,"candidate_test":testm,"model_path":str(mp),"sha256":model_hash},indent=2))
if __name__=="__main__":main()
