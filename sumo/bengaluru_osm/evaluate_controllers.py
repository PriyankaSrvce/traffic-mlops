"""Paired fixed/adaptive/predictive evaluation on identical OSM routes/seeds."""
from __future__ import annotations
import argparse,csv,hashlib,json,subprocess,sys,time,xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
POLICIES=("fixed","adaptive","predictive")
PROFILES={"42":"balanced_assumed","99":"balanced_assumed","123":"balanced_assumed","31415":"motorcycle_heavy_assumed","27183":"balanced_assumed"}
def sha(p):
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1048576),b""):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--seeds",default="123,31415,27183");ap.add_argument("--scenarios",default="low,medium,high");ap.add_argument("--policies",default="fixed,adaptive,predictive");ap.add_argument("--duration",type=int,default=900);ap.add_argument("--output-root",type=Path,default=HERE/"runs"/"controller_eval_v1");ap.add_argument("--python",default=sys.executable);ap.add_argument("--sumo",default="sumo");ap.add_argument("--demand-overrides",default="",help="Optional comma-separated scenario=vehicles/hour assumptions, e.g. high=480");ap.add_argument("--allow-partial-seeds",action="store_true",help="Allow a supplemental batch with fewer than three seeds; aggregate with a prior paired batch.");a=ap.parse_args()
 overrides={}
 for item in filter(None,(part.strip() for part in a.demand_overrides.split(","))):
  name,value=item.split("=",1);rate=int(value)
  if name not in {"low","medium","high"} or rate<=0:raise SystemExit(f"Invalid demand override: {item}")
  overrides[name]=rate
 seeds=[int(x) for x in a.seeds.split(",") if x.strip()];scenarios=[x.strip() for x in a.scenarios.split(",") if x.strip()];policies=[x.strip() for x in a.policies.split(",") if x.strip()]
 if not seeds or len(set(seeds))!=len(seeds):raise SystemExit("Seeds must be non-empty and unique.")
 if len(set(seeds))<3 and not a.allow_partial_seeds:raise SystemExit("At least three paired random seeds are required unless --allow-partial-seeds is set for a supplemental batch.")
 if set(policies)!=set(POLICIES):raise SystemExit(f"Evaluation must include all policies {POLICIES}.")
 outroot=a.output_root.resolve();outroot.mkdir(parents=True,exist_ok=True);runs=[]
 network=HERE/"bengaluru_osm_sim.net.xml"
 for scenario in scenarios:
  for seed in seeds:
   profile=PROFILES.get(str(seed),"balanced_assumed")
   pairdir=outroot/f"{scenario}_seed{seed}";pairdir.mkdir(parents=True,exist_ok=True)
   routes=pairdir/"routes.rou.xml"
   if not routes.exists():
    gen_cmd=[a.python,str(HERE/"generate_scenario.py"),"--scenario",scenario,"--seed",str(seed),"--duration",str(a.duration),"--composition-profile",profile,"--output",str(routes)]
    if scenario in overrides:gen_cmd += ["--vehicles-per-hour",str(overrides[scenario])]
    gen=subprocess.run(gen_cmd,cwd=ROOT,text=True,capture_output=True)
    (pairdir/"route_generation.log").write_text(gen.stdout+"\n"+gen.stderr,encoding="utf-8")
    if gen.returncode:raise SystemExit(f"Route generation failed for {scenario}/{seed}: {gen.stderr}")
   assumed_rate=overrides.get(scenario,json.loads((HERE/"scenario.json").read_text(encoding="utf-8"))["demand"][scenario]["vehicles_per_hour"])
   route_sha=sha(routes)
   for policy in policies:
    run_id=f"bengaluru_{scenario}_seed{seed}_{profile}_{policy}_rate{assumed_rate}_eval2";rundir=pairdir/policy
    if rundir.exists():
     mp=rundir/"run_metadata.json"
     if mp.exists() and json.loads(mp.read_text(encoding="utf-8")).get("status") in ("complete","quality_failure"):
      runs.append(json.loads((rundir/"run_summary.json").read_text(encoding="utf-8")));print(f"SKIP existing {run_id}",flush=True);continue
     raise SystemExit(f"Refusing to overwrite partial evaluation directory: {rundir}")
    rundir.mkdir(parents=True);start=time.perf_counter()
    trip=rundir/"tripinfo.xml";stats=rundir/"statistics.xml";obs=rundir/"observations.csv";coll=rundir/"collisions.xml";dec=rundir/"decisions.csv";log=rundir/"controller.log"
    cmd=[a.python,str(HERE/"controller.py"),"--policy",policy,"--scenario",scenario,"--seed",str(seed),"--duration",str(a.duration),"--composition-profile",profile,"--routes",str(routes),"--run-id",run_id,"--log",str(dec),"--tripinfo",str(trip),"--statistics",str(stats),"--observations",str(obs),"--collisions",str(coll),"--sumo",a.sumo]
    meta={"run_id":run_id,"scenario":scenario,"seed":seed,"policy":policy,"vehicle_composition":profile,"assumed_demand_vehicles_per_hour":assumed_rate,"network":"bengaluru_osm_sim.net.xml","network_sha256":sha(network),"routes_sha256":route_sha,"duration_s":a.duration,"status":"running"}
    if policy=="predictive":
     model=ROOT/"models"/"bengaluru"/"bengaluru_queue_hurdle_v1_2026-11.joblib";model_meta=model.with_suffix(".json")
     cmd += ["--model",str(model),"--metadata",str(model_meta)];meta["model_sha256"]=sha(model)
    (rundir/"run_metadata.json").write_text(json.dumps(meta,indent=2),encoding="utf-8")
    proc=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
    log.write_text(proc.stdout+"\n"+proc.stderr,encoding="utf-8")
    if proc.returncode:
     meta.update({"status":"failed","error":f"controller exit {proc.returncode}","elapsed_wall_s":round(time.perf_counter()-start,2)});(rundir/"run_metadata.json").write_text(json.dumps(meta,indent=2),encoding="utf-8");print(f"FAILED {run_id}: {proc.stderr[-300:]}",flush=True);continue
    stat=ET.parse(stats).getroot();v=stat.find(".//vehicles");tp=stat.find(".//teleports");collisions=ET.parse(coll).getroot().findall("collision") if coll.exists() else []
    trips=ET.parse(trip).getroot().findall("tripinfo");complete=[x for x in trips if float(x.get("arrival","-1"))>=0 and not x.get("vaporized")]
    df=pd.read_csv(obs);queue=pd.to_numeric(df.queue_length_m,errors="coerce");speeds=pd.to_numeric(df.mean_speed_mps,errors="coerce")
    trip_durations=[float(x.get("duration",0)) for x in complete];waits=[float(x.get("waitingTime",0)) for x in complete];trip_speeds=[float(x.get("routeLength",0))/max(1,float(x.get("duration",1))) for x in complete]
    fallback=sum(r.get("prediction_fallback")=="True" for r in csv.DictReader(dec.open(encoding="utf-8"))) if dec.exists() and policy=="predictive" else 0
    summary={"run_id":run_id,"scenario":scenario,"assumed_demand_vehicles_per_hour":assumed_rate,"seed":seed,"policy":policy,"vehicle_composition":profile,"status":"complete","planned":int(v.get("loaded",0)),"inserted":int(v.get("inserted",0)),"running_at_end":int(v.get("running",0)),"completed":len(complete),"teleports":int(tp.get("total",0)) if tp is not None else None,"teleport_jam":int(tp.get("jam",0)) if tp is not None else None,"collisions":len(collisions),"mean_travel_time_s":sum(trip_durations)/max(1,len(trip_durations)),"mean_waiting_time_s":sum(waits)/max(1,len(waits)),"mean_speed_mps":sum(trip_speeds)/max(1,len(trip_speeds)),"mean_queue_length_m":float(queue.mean()),"max_queue_length_m":float(queue.max()),"throughput_veh":len(complete),"mean_lane_observed_speed_mps":float(speeds.mean()),"observations":len(df),"controller_decisions":sum(1 for _ in csv.DictReader(dec.open(encoding="utf-8"))),"prediction_fallbacks":fallback,"completed_by_type":{t:sum(x.get("vType")==t for x in complete) for t in sorted({x.get("vType") for x in complete})},"elapsed_wall_s":round(time.perf_counter()-start,2)}
    if summary["inserted"]!=summary["planned"] or summary["running_at_end"]!=0 or summary["completed"]!=summary["planned"] or summary["teleports"] or summary["collisions"] or fallback:summary["status"]="quality_failure"
    (rundir/"run_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8");meta.update({"status":summary["status"],"elapsed_wall_s":summary["elapsed_wall_s"],"summary":summary});(rundir/"run_metadata.json").write_text(json.dumps(meta,indent=2),encoding="utf-8");runs.append(summary)
    print(f"{summary['status'].upper()} {run_id}: trips={summary['completed']}/{summary['planned']} teleports={summary['teleports']} collisions={summary['collisions']} mean_tt={summary['mean_travel_time_s']:.1f}s queue={summary['mean_queue_length_m']:.2f}m",flush=True)
 flat=[]
 for run in runs:flat.append(run)
 if flat:
  pd.DataFrame(flat).to_csv(outroot/"per_run_metrics.csv",index=False)
  df=pd.DataFrame(flat);agg=df.groupby(["scenario","policy"]).agg(runs=("run_id","size"),mean_travel_time_s=("mean_travel_time_s","mean"),sd_travel_time_s=("mean_travel_time_s","std"),mean_waiting_time_s=("mean_waiting_time_s","mean"),sd_waiting_time_s=("mean_waiting_time_s","std"),mean_queue_length_m=("mean_queue_length_m","mean"),max_queue_length_m=("max_queue_length_m","max"),mean_speed_mps=("mean_speed_mps","mean"),throughput_veh=("throughput_veh","mean"),teleports=("teleports","sum"),collisions=("collisions","sum")).reset_index();agg.to_csv(outroot/"aggregate_metrics.csv",index=False)
  (outroot/"evaluation_summary.json").write_text(agg.to_json(orient="records",indent=2),encoding="utf-8")
  print(agg.to_string(index=False),flush=True)
if __name__=="__main__":main()
