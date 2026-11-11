"""Validate separated run outputs and build auditable clean labelled tables."""
from __future__ import annotations
import argparse,csv,json,re,xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd

REQUIRED={"run_id","seed","scenario","time_s","intersection_id","approach_id","lane_id","queue_length_m","vehicle_count","halting_vehicle_count","mean_speed_mps","phase_elapsed_s","signal_phase_id","signal_state","queue_length_m_t_plus_60s"}
FEATURES=["queue_length_m","vehicle_count","halting_vehicle_count","mean_speed_mps","phase_elapsed_s","intersection_id","approach_id","lane_id","signal_phase_id","signal_state","vehicle_composition"]
NUMERIC=["time_s","queue_length_m","queue_proxy_5m","queue_vehicle_count","vehicle_count","halting_vehicle_count","mean_speed_mps","waiting_time_s","occupancy_pct","phase_elapsed_s","signal_phase_id","queue_length_m_t_plus_60s"]

def events_for(run:Path)->list[float]:
    times=[]
    cp=run/"collisions.xml"
    if cp.exists():
        try: times += [float(e.get("time")) for e in ET.parse(cp).getroot().findall("collision") if e.get("time")]
        except ET.ParseError: pass
    log=run/"collector.log"
    if log.exists():
        for m in re.finditer(r"Teleporting vehicle .*?time=(\d+(?:\.\d+)?)\b",log.read_text(encoding="utf-8",errors="ignore")):
            times.append(float(m.group(1)))
    return sorted(set(times))

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--roots",nargs="+",type=Path,required=True);ap.add_argument("--output",type=Path,default=Path(__file__).resolve().parent/"datasets"/"osm_v2");ap.add_argument("--incident-window",type=int,default=60);a=ap.parse_args()
    out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    obs_frames=[];label_frames=[];run_reports=[];skipped=[]
    for root in a.roots:
        for run in sorted(root.glob("*")):
            if not run.is_dir():continue
            mp=run/"run_metadata.json";op=run/"observations.csv";lp=run/"labeled.csv"
            if not(mp.exists() and op.exists() and lp.exists()):continue
            meta=json.loads(mp.read_text(encoding="utf-8"));status=meta.get("status")
            if status not in ("complete","quality_failure"):
                skipped.append({"run_id":meta.get("run_id"),"reason":status});continue
            od=pd.read_csv(op);ld=pd.read_csv(lp)
            for df in (od,ld):
                if "vehicle_composition" not in df: df["vehicle_composition"]=meta.get("vehicle_composition","balanced_assumed")
                if "queue_proxy_5m" not in df: df["queue_proxy_5m"]=pd.to_numeric(df["halting_vehicle_count"],errors="coerce")*5.0
                if "queue_vehicle_count" not in df: df["queue_vehicle_count"]=df["halting_vehicle_count"]
                if "vehicle_type_mix" in df: df["vehicle_type_mix"]=df["vehicle_type_mix"].fillna("none")
            missing=sorted(REQUIRED-set(ld.columns))
            key=["run_id","intersection_id","lane_id","time_s"]
            dup=int(ld.duplicated(key).sum()) if not missing else -1
            event_times=events_for(run)
            clean=ld.copy()
            if event_times:
                bad=pd.Series(False,index=clean.index)
                # Remove observations whose input or +60s label straddles a collision/teleport neighborhood.
                t=pd.to_numeric(clean["time_s"]);future=t+60
                for ev in event_times:
                    bad |= (t.sub(ev).abs()<=a.incident_window) | (future.sub(ev).abs()<=a.incident_window)
                clean=clean.loc[~bad].copy()
            for col in NUMERIC:
                if col in clean: clean[col]=pd.to_numeric(clean[col],errors="coerce")
            clean["incident_count_run"]=len(event_times)
            report={"run_id":meta.get("run_id"),"scenario":meta.get("scenario"),"seed":meta.get("seed"),"composition":meta.get("vehicle_composition","balanced_assumed"),"status":status,"observations":len(od),"labels_raw":len(ld),"labels_after_incident_quarantine":len(clean),"incident_times_s":event_times,"missing_required_columns":missing,"duplicate_observation_keys":dup,"missing_cells_after_quarantine":int(clean.isna().sum().sum()),"teleports":meta.get("teleports",{}),"vehicle_counts":meta.get("vehicle_counts",meta.get("demand_generation",{}).get("vehicle_shares_assumed")),"output_dir":str(run)}
            run_reports.append(report)
            if missing or dup or report["missing_cells_after_quarantine"]>0:
                skipped.append({"run_id":meta.get("run_id"),"reason":"schema_missing_duplicate_or_null"});continue
            obs_frames.append(od);label_frames.append((ld,clean))
    if not label_frames:raise SystemExit("No valid labelled run directories found.")
    raw_obs=pd.concat(obs_frames,ignore_index=True);raw_lab=pd.concat([x[0] for x in label_frames],ignore_index=True);clean_lab=pd.concat([x[1] for x in label_frames],ignore_index=True)
    raw_obs.to_csv(out/"observations_all.csv",index=False);raw_lab.to_csv(out/"labels_all.csv",index=False);clean_lab.to_csv(out/"training_labels_incident_quarantined.csv",index=False)
    all_key=["run_id","intersection_id","lane_id","time_s"]
    dup_obs=int(raw_obs.duplicated(all_key).sum());dup_labels=int(raw_lab.duplicated(all_key).sum())
    if dup_obs or dup_labels: raise SystemExit(f"Duplicate records across runs: observations={dup_obs}, labels={dup_labels}")
    # Verify each target is the queue recorded at exact time + 60 within that same run/lane.
    qmap={(r.run_id,r.intersection_id,r.lane_id,int(r.time_s)):float(r.queue_length_m) for r in raw_obs.itertuples()}
    mismatches=0
    for r in raw_lab.itertuples():
        y=qmap.get((r.run_id,r.intersection_id,r.lane_id,int(r.time_s)+60))
        if y is None or abs(y-float(r.queue_length_m_t_plus_60s))>1e-6:mismatches+=1
    run_ids=sorted(raw_lab.run_id.unique())
    num_summary={}
    for c in NUMERIC:
        if c in clean_lab:
            s=pd.to_numeric(clean_lab[c],errors="coerce").dropna()
            if len(s):num_summary[c]={"n":int(len(s)),"min":float(s.min()),"p50":float(s.median()),"mean":float(s.mean()),"p95":float(s.quantile(.95)),"max":float(s.max())}
    by_scenario=clean_lab.groupby("scenario").agg(rows=("run_id","size"),runs=("run_id","nunique"),target_mean_m=("queue_length_m_t_plus_60s","mean"),target_p95_m=("queue_length_m_t_plus_60s",lambda x:x.quantile(.95))).reset_index()
    by_mix=clean_lab.groupby("vehicle_composition").agg(rows=("run_id","size"),runs=("run_id","nunique"),target_mean_m=("queue_length_m_t_plus_60s","mean")).reset_index()
    by_tls=clean_lab.groupby("intersection_id").agg(rows=("run_id","size"),approaches=("approach_id","nunique"),target_mean_m=("queue_length_m_t_plus_60s","mean"),target_p95_m=("queue_length_m_t_plus_60s",lambda x:x.quantile(.95))).reset_index()
    by_approach=clean_lab.groupby(["intersection_id","approach_id"]).agg(rows=("run_id","size"),lanes=("lane_id","nunique"),target_mean_m=("queue_length_m_t_plus_60s","mean")).reset_index()
    by_scenario.to_csv(out/"counts_by_demand.csv",index=False);by_mix.to_csv(out/"counts_by_composition.csv",index=False);by_tls.to_csv(out/"counts_by_intersection.csv",index=False);by_approach.to_csv(out/"counts_by_approach.csv",index=False)
    summary={"dataset_version":"bengaluru_osm_v2","raw_observations":len(raw_obs),"raw_labelled_rows":len(raw_lab),"clean_labelled_rows":len(clean_lab),"run_count":len(run_ids),"run_ids":run_ids,"duplicate_observation_keys":dup_obs,"duplicate_label_keys":dup_labels,"exact_60s_label_mismatches":mismatches,"null_cells_clean":int(clean_lab.isna().sum().sum()),"feature_columns":FEATURES,"target":"queue_length_m_t_plus_60s","queue_measurement":"contiguous stopped queue from front positions and actual lengths; target is exact same lane +60s","incident_quarantine_window_s":a.incident_window,"by_scenario":by_scenario.to_dict(orient="records"),"by_composition":by_mix.to_dict(orient="records"),"numeric_distributions":num_summary,"runs":run_reports,"skipped":skipped}
    (out/"dataset_validation.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps({k:summary[k] for k in ("raw_observations","raw_labelled_rows","clean_labelled_rows","run_count","duplicate_observation_keys","duplicate_label_keys","exact_60s_label_mismatches","null_cells_clean","by_scenario","by_composition")},indent=2))
    if mismatches or dup_obs or dup_labels or summary["null_cells_clean"]:raise SystemExit("Dataset validation failed; see dataset_validation.json")

if __name__=="__main__":main()
