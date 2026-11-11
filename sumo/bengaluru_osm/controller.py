"""Bounded green-extension policies that preserve each imported TLS phase sequence."""
from __future__ import annotations
import argparse, csv, hashlib, json, os, sys
from collections import defaultdict
from pathlib import Path
import joblib
import pandas as pd
import numpy as np
import sumolib
from queue_measurement import measure_lane_queue

HERE=Path(__file__).resolve().parent
FEATURES=["queue_length_m","vehicle_count","halting_vehicle_count","mean_speed_mps","phase_elapsed_s","intersection_id","approach_id","lane_id","signal_phase_id","signal_state","vehicle_composition"]
ANCHORS=("1208112310#1","-133945864","558765859#3")

def main():
    model_default=HERE.parents[1]/"models"/"bengaluru"/"bengaluru_queue_hurdle_v1_2026-11.joblib"
    metadata_default=model_default.with_suffix(".json")
    ap=argparse.ArgumentParser(); ap.add_argument("--policy",choices=("fixed","adaptive","predictive"),default="fixed"); ap.add_argument("--scenario",choices=("low","medium","high"),default="low"); ap.add_argument("--seed",type=int,default=21); ap.add_argument("--duration",type=int,default=900); ap.add_argument("--max-drain",type=int,default=3600); ap.add_argument("--time-to-teleport",type=int,default=300); ap.add_argument("--sumo",default="sumo"); ap.add_argument("--routes",type=Path,default=HERE/"traffic.rou.xml"); ap.add_argument("--run-id",default=None);ap.add_argument("--model",type=Path,default=model_default); ap.add_argument("--metadata",type=Path,default=metadata_default); ap.add_argument("--composition-profile",choices=("balanced_assumed","motorcycle_heavy_assumed"),default="balanced_assumed"); ap.add_argument("--log",type=Path,default=None); ap.add_argument("--tripinfo",type=Path,default=None); ap.add_argument("--statistics",type=Path,default=None); ap.add_argument("--observations",type=Path,default=None);ap.add_argument("--collisions",type=Path,default=None);a=ap.parse_args()
    model=None
    if a.policy=="predictive":
        if not a.metadata.exists(): raise SystemExit("Predictive control blocked: no Bengaluru model metadata; transfer model is not validated.")
        meta=json.loads(a.metadata.read_text(encoding="utf-8"))
        if meta.get("validation_status")!="passed" or meta.get("network")!="bengaluru_osm_sim.net.xml": raise SystemExit("Predictive control blocked: model metadata does not establish validated Bengaluru compatibility.")
        if not a.model.exists(): raise SystemExit("Validated Bengaluru model file is missing.")
        digest=hashlib.sha256(a.model.read_bytes()).hexdigest()
        if digest.lower()!=str(meta.get("sha256","")).lower(): raise SystemExit("Predictive control blocked: model SHA-256 differs from validation metadata.")
        model=joblib.load(a.model)
        if list(getattr(model,"feature_names_in_",[]))!=meta.get("features") or meta.get("features")!=FEATURES: raise SystemExit("Model feature schema mismatch.")
    net=sumolib.net.readNet(str(HERE/"bengaluru_osm_sim.net.xml"),withInternal=False)
    relevant=defaultdict(set)
    for x,y in ((0,1),(1,0),(1,2),(2,1),(0,2),(2,0)):
        route,_=net.getShortestPath(net.getEdge(ANCHORS[x]),net.getEdge(ANCHORS[y]),vClass="passenger")
        for edge in route or []:
            for _,conns in edge.getOutgoing().items():
                for c in conns:
                    if c.getTLSID(): relevant[c.getTLSID()].add(c.getFromLane().getID())
    import traci
    run=a.run_id or f"bengaluru_{a.scenario}_seed{a.seed}_{a.composition_profile}_{a.policy}"
    log=a.log or HERE/f"controller_{a.policy}_{a.scenario}_seed{a.seed}.csv"
    fields=["run_id","time_s","intersection_id","policy","phase_id","signal_state","green_elapsed_s","observed_queue_score","predicted_queue_score","decision","prediction_fallback"]
    output=[]; last_phase={}; green_since={}
    observation_rows=[]
    max_end=a.duration+a.max_drain
    cmd=[a.sumo,"-c",str(HERE/"demo.sumocfg"),"--route-files",str(a.routes.resolve()),"--end",str(max_end),"--time-to-teleport",str(a.time_to_teleport),"--seed",str(a.seed),"--no-step-log","true"]
    if a.tripinfo: cmd += ["--tripinfo-output",str(a.tripinfo.resolve())]
    if a.statistics: cmd += ["--statistic-output",str(a.statistics.resolve())]
    if a.collisions: cmd += ["--collision-output",str(a.collisions.resolve()),"--collision.check-junctions"]
    traci.start(cmd)
    try:
        while True:
            before=traci.simulation.getTime()
            if before>=max_end or (before>=a.duration and traci.simulation.getMinExpectedNumber()<=0):break
            traci.simulationStep(); now=traci.simulation.getTime()
            if now<=before:break
            if int(now)%5: continue
            live_tls=set(traci.trafficlight.getIDList())
            pending=[];all_features=[]
            for tls,lanes in relevant.items():
                if tls not in live_tls: continue
                phase=traci.trafficlight.getPhase(tls); state=traci.trafficlight.getRedYellowGreenState(tls)
                if last_phase.get(tls)!=phase: last_phase[tls]=phase; green_since[tls]=now
                elapsed=now-green_since[tls]
                if a.policy=="fixed" or not any(c in "Gg" for c in state) or elapsed<8: continue
                links=traci.trafficlight.getControlledLinks(tls)
                phase_logics=traci.trafficlight.getAllProgramLogics(tls)
                program=next((p for p in phase_logics if p.programID==traci.trafficlight.getProgram(tls)),None)
                if program is None: continue
                serving_by_phase=[]
                for ph in program.phases:
                    serving=set()
                    for ix,ch in enumerate(ph.state):
                        if ch in "Gg" and ix<len(links):serving.update(link[0] for link in links[ix] if link and link[0] in lanes)
                    serving_by_phase.append(serving)
                sample_lanes=sorted(set().union(*serving_by_phase)) if serving_by_phase else []
                queue_by_lane={};feature_rows=[]
                for lane in sample_lanes:
                    vids=traci.lane.getLastStepVehicleIDs(lane);speeds=[traci.vehicle.getSpeed(v) for v in vids]
                    queue=measure_lane_queue([{"lanePosition":traci.vehicle.getLanePosition(v),"length":traci.vehicle.getLength(v),"speed":sp} for v,sp in zip(vids,speeds)])
                    queue_by_lane[lane]=queue["queue_length_m"]
                    feature_rows.append({"queue_length_m":queue["queue_length_m"],"vehicle_count":len(vids),"halting_vehicle_count":queue["halting_vehicle_count"],"mean_speed_mps":sum(speeds)/len(speeds) if speeds else 0.0,"phase_elapsed_s":elapsed,"intersection_id":tls,"approach_id":lane.rsplit("_",1)[0],"lane_id":lane,"signal_phase_id":str(phase),"signal_state":state,"vehicle_composition":a.composition_profile})
                start=len(all_features);all_features.extend(feature_rows)
                pending.append({"tls":tls,"phase":phase,"state":state,"elapsed":elapsed,"program":program,"serving":serving_by_phase,"lanes":sample_lanes,"queues":queue_by_lane,"feature_start":start,"feature_count":len(feature_rows)})
            all_predictions=None;global_prediction_failed=False
            if a.policy=="predictive" and all_features:
                try:
                    all_predictions=np.asarray(model.predict(pd.DataFrame(all_features,columns=FEATURES)),dtype=float).reshape(-1)
                    if len(all_predictions)!=len(all_features) or not np.all(np.isfinite(all_predictions)) or np.any(all_predictions<0):raise ValueError("Invalid predicted queue outputs")
                except (ValueError,TypeError,KeyError,RuntimeError):global_prediction_failed=True
            for ctx in pending:
                begin=ctx["feature_start"];end=begin+ctx["feature_count"]
                lane_pred=dict(zip(ctx["lanes"],all_predictions[begin:end])) if all_predictions is not None and not global_prediction_failed else {}
                scores=[];observed_scores=[]
                for serving in ctx["serving"]:
                    observed=sum(ctx["queues"].get(lane,0.0) for lane in serving);observed_scores.append(observed)
                    score=sum(float(lane_pred.get(lane,0.0)) for lane in serving) if a.policy=="predictive" and not global_prediction_failed else observed
                    scores.append(score)
                phase=ctx["phase"];current=scores[phase] if phase<len(scores) else 0.0;observed=observed_scores[phase] if phase<len(observed_scores) else 0.0
                best=max((v for ix,v in enumerate(scores) if ix!=phase),default=0.0);remain=max(0.0,traci.trafficlight.getNextSwitch(ctx["tls"])-now)
                fallback=a.policy=="predictive" and global_prediction_failed
                decision="prediction_fallback_adaptive" if fallback else "hold_existing_phase"
                if ctx["elapsed"]<45 and current>best+2.0:
                    traci.trafficlight.setPhaseDuration(ctx["tls"],min(45-ctx["elapsed"],remain+5.0));decision="extend_green_5s"
                output.append({"run_id":run,"time_s":now,"intersection_id":ctx["tls"],"policy":a.policy,"phase_id":phase,"signal_state":ctx["state"],"green_elapsed_s":ctx["elapsed"],"observed_queue_score":observed,"predicted_queue_score":current if a.policy=="predictive" and not fallback else "","decision":decision,"prediction_fallback":fallback})
            if a.observations and int(now)%10==0:
                for tls,lane_ids in relevant.items():
                    if tls not in live_tls:continue
                    ph=traci.trafficlight.getPhase(tls);sig=traci.trafficlight.getRedYellowGreenState(tls)
                    if last_phase.get(tls)!=ph:last_phase[tls]=ph;green_since[tls]=now
                    elapsed=now-green_since[tls]
                    for lane in lane_ids:
                        vids=traci.lane.getLastStepVehicleIDs(lane);speeds=[traci.vehicle.getSpeed(v) for v in vids]
                        q=measure_lane_queue([{"lanePosition":traci.vehicle.getLanePosition(v),"length":traci.vehicle.getLength(v),"speed":s} for v,s in zip(vids,speeds)])
                        types={}
                        for v in vids:
                            vt=traci.vehicle.getTypeID(v);types[vt]=types.get(vt,0)+1
                        observation_rows.append({"run_id":run,"seed":a.seed,"scenario":a.scenario,"policy":a.policy,"vehicle_composition":a.composition_profile,"time_s":now,"intersection_id":tls,"approach_id":lane.rsplit("_",1)[0],"lane_id":lane,"queue_length_m":q["queue_length_m"],"queue_vehicle_count":q["queue_vehicle_count"],"queue_proxy_5m":q["queue_proxy_5m"],"vehicle_count":len(vids),"halting_vehicle_count":q["halting_vehicle_count"],"mean_speed_mps":sum(speeds)/len(speeds) if speeds else 0.0,"waiting_time_s":sum(traci.vehicle.getWaitingTime(v) for v in vids),"occupancy_pct":traci.lane.getLastStepOccupancy(lane),"vehicle_type_mix":";".join(f"{k}:{types[k]}" for k in sorted(types)) or "none","signal_phase_id":ph,"signal_state":sig,"phase_elapsed_s":elapsed})
    finally: traci.close()
    log.parent.mkdir(parents=True,exist_ok=True)
    with log.open("w",newline="",encoding="utf-8") as f: w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(output)
    if a.observations:
        a.observations.parent.mkdir(parents=True,exist_ok=True)
        obs_fields=["run_id","seed","scenario","policy","vehicle_composition","time_s","intersection_id","approach_id","lane_id","queue_length_m","queue_vehicle_count","queue_proxy_5m","vehicle_count","halting_vehicle_count","mean_speed_mps","waiting_time_s","occupancy_pct","vehicle_type_mix","signal_phase_id","signal_state","phase_elapsed_s"]
        with a.observations.open("w",newline="",encoding="utf-8") as f:w=csv.DictWriter(f,fieldnames=obs_fields);w.writeheader();w.writerows(observation_rows)
    print(f"policy={a.policy} run={run} tls_candidates={len(relevant)} decisions={len(output)} log={log}")

if __name__=="__main__": main()
