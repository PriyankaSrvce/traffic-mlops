"""Generate isolated low/medium/high SUMO observation runs without overwrites."""
from __future__ import annotations
import argparse, csv, hashlib, json, subprocess, sys, time, xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--seeds",default="7,42,99")
    ap.add_argument("--scenarios",default="low,medium,high")
    ap.add_argument("--duration",type=int,default=900)
    ap.add_argument("--step",type=int,default=10)
    ap.add_argument("--output-root",type=Path,default=HERE/"runs"/"osm_v1")
    ap.add_argument("--python",default=sys.executable)
    ap.add_argument("--sumo",default="sumo")
    ap.add_argument("--time-to-teleport",type=int,default=300)
    ap.add_argument("--batch-id",default="osm_v1")
    ap.add_argument("--composition-profile",default="balanced_assumed")
    a=ap.parse_args()
    seeds=[int(s.strip()) for s in a.seeds.split(",") if s.strip()]
    scenarios=[s.strip() for s in a.scenarios.split(",") if s.strip()]
    if len(set(seeds))!=len(seeds) or not seeds: raise SystemExit("Use one or more unique seeds.")
    if not set(scenarios)<={"low","medium","high"}: raise SystemExit("Unknown demand scenario.")
    a.output_root=a.output_root.resolve(); a.output_root.mkdir(parents=True,exist_ok=True)
    net=HERE/"bengaluru_osm_sim.net.xml"; completed=[]; failures=[]
    for scenario in scenarios:
        for seed in seeds:
            run_id=f"bengaluru_{scenario}_seed{seed}_{a.composition_profile}_{a.batch_id}"
            out=a.output_root/f"{scenario}_seed{seed}"
            if out.exists():
                meta=out/"run_metadata.json"
                if meta.exists() and json.loads(meta.read_text(encoding="utf-8")).get("status")=="complete":
                    print(f"SKIP existing complete {run_id}",flush=True); completed.append(run_id); continue
                raise SystemExit(f"Refusing to overwrite existing incomplete run directory: {out}")
            out.mkdir(parents=True)
            routes=out/"traffic.rou.xml"; observations=out/"observations.csv"; labels=out/"labeled.csv"
            trip=out/"tripinfo.xml"; stats=out/"statistics.xml"; collisions=out/"collisions.xml"
            run_meta={"run_id":run_id,"scenario":scenario,"seed":seed,"status":"running",
                      "network":"bengaluru_osm_sim.net.xml","duration_s":a.duration,"sampling_step_s":a.step,
                      "vehicle_composition":a.composition_profile,
                      "vehicle_shares_assumed":json.loads((HERE/"scenario.json").read_text(encoding="utf-8"))["vehicle_composition_profiles"][a.composition_profile],
                      "network_sha256":sha(net),"started_unix":time.time()}
            (out/"run_metadata.json").write_text(json.dumps(run_meta,indent=2),encoding="utf-8")
            start=time.perf_counter()
            try:
                gen=subprocess.run([a.python,str(HERE/"generate_scenario.py"),"--scenario",scenario,"--seed",str(seed),"--duration",str(a.duration),"--composition-profile",a.composition_profile,"--output",str(routes)],cwd=ROOT,text=True,capture_output=True)
                (out/"route_generation.log").write_text(gen.stdout+"\n"+gen.stderr,encoding="utf-8")
                if gen.returncode: raise RuntimeError(f"route generator exit={gen.returncode}")
                gen_result=json.loads(gen.stdout)
                mix={v:0 for v in ("two_wheeler","car","auto_rickshaw","bus","truck")}
                for _,e in ET.iterparse(routes,events=("end",)):
                    if e.tag=="vehicle": mix[e.get("type")]+=1
                    e.clear()
                run_meta["demand_generation"]=gen_result; run_meta["vehicle_counts"]=mix
                collect=subprocess.run([a.python,str(HERE/"collect_observations.py"),"--scenario",scenario,"--seed",str(seed),"--step",str(a.step),"--duration",str(a.duration),"--routes",str(routes),"--run-id",run_id,"--composition-profile",a.composition_profile,"--output",str(observations),"--tripinfo",str(trip),"--statistics",str(stats),"--collisions",str(collisions),"--time-to-teleport",str(a.time_to_teleport),"--sumo",a.sumo],cwd=ROOT,text=True,capture_output=True)
                (out/"collector.log").write_text(collect.stdout+"\n"+collect.stderr,encoding="utf-8")
                if collect.returncode: raise RuntimeError(f"collector exit={collect.returncode}")
                lab=subprocess.run([a.python,str(HERE/"label_observations.py"),str(observations),"--horizon","60","--output",str(labels)],cwd=ROOT,text=True,capture_output=True)
                (out/"labeling.log").write_text(lab.stdout+"\n"+lab.stderr,encoding="utf-8")
                if lab.returncode: raise RuntimeError(f"labeler exit={lab.returncode}")
                state=ET.parse(stats).getroot(); veh=state.find(".//vehicles"); tele=state.find(".//teleports")
                trips=ET.parse(trip).getroot().findall("tripinfo")
                arrived=[t for t in trips if float(t.get("arrival","-1"))>=0 and not t.get("vaporized")]
                run_meta.update({"status":"complete","elapsed_wall_s":round(time.perf_counter()-start,2),
                    "vehicles":{"planned":sum(mix.values()),"loaded":int(veh.get("loaded","0")),"inserted":int(veh.get("inserted","0")),"running_at_end":int(veh.get("running","0")),"tripinfo_records":len(trips),"completed":len(arrived)},
                    "teleports":tele.attrib if tele is not None else {},"collisions":len(ET.parse(collisions).getroot().findall("collision")) if collisions.exists() else None,
                    "observations":sum(1 for _ in observations.open(encoding="utf-8"))-1,
                    "labels":sum(1 for _ in labels.open(encoding="utf-8"))-1,
                    "sha256":{"routes":sha(routes),"observations":sha(observations),"labels":sha(labels),"tripinfo":sha(trip),"statistics":sha(stats)}})
                if run_meta["vehicles"]["planned"]!=run_meta["vehicles"]["inserted"] or run_meta["vehicles"]["running_at_end"]!=0 or run_meta["vehicles"]["completed"]!=run_meta["vehicles"]["planned"] or int(run_meta["teleports"].get("total",0))!=0:
                    run_meta["status"]="quality_failure"
                (out/"run_summary.json").write_text(json.dumps({"tripinfo_records":len(trips),"completed":len(arrived),"mean_travel_time_s":sum(float(t.get("duration",0)) for t in arrived)/max(1,len(arrived)),"mean_waiting_time_s":sum(float(t.get("waitingTime",0)) for t in arrived)/max(1,len(arrived)),"mean_speed_mps":sum(float(t.get("routeLength",0))/max(1,float(t.get("duration",1))) for t in arrived)/max(1,len(arrived)),"completed_by_type":{v:sum(t.get("vType")==v for t in arrived) for v in mix}},indent=2),encoding="utf-8")
                if run_meta["status"]=="complete": completed.append(run_id)
                else: failures.append({"run_id":run_id,"status":run_meta["status"]})
                print(f"{run_meta['status'].upper()} {run_id}: vehicles={run_meta['vehicles']['inserted']}/{run_meta['vehicles']['planned']} completed={run_meta['vehicles']['completed']} observations={run_meta['observations']} labels={run_meta['labels']} teleports={run_meta['teleports'].get('total','?')} wall_s={run_meta['elapsed_wall_s']}",flush=True)
            except Exception as exc:
                run_meta.update({"status":"failed","error":repr(exc),"elapsed_wall_s":round(time.perf_counter()-start,2)})
                failures.append({"run_id":run_id,"error":repr(exc)})
                print(f"FAILED {run_id}: {exc}",flush=True)
            finally:
                run_meta["finished_unix"]=time.time()
                (out/"run_metadata.json").write_text(json.dumps(run_meta,indent=2),encoding="utf-8")
    index={"runs":completed,"failures":failures,"created_unix":time.time()}
    (a.output_root/"batch_index.json").write_text(json.dumps(index,indent=2),encoding="utf-8")
    if failures: raise SystemExit(f"{len(failures)} run(s) failed; inspect batch index and per-run logs.")

if __name__=="__main__": main()
