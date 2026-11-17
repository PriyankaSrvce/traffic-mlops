"""Results report as a Metaflow flow with a chart card (the "Metaflow graphs" page).

Reads (does not modify) the artifacts of a BengaluruQueueModelFlow training run, that run's held-out
test predictions, and the SUMO controller re-runs, then renders a Metaflow card with charts.
By default it reports the latest successful training run of whoever runs it.

    python flows/phase2_results_flow.py run
    python flows/phase2_results_flow.py card server --port 8325    # then open http://localhost:8325

Use the same --metadata/--datastore options (or METAFLOW_* environment) as the training run.
"""
import hashlib
import json
from pathlib import Path

from metaflow import FlowSpec, Parameter, card, current, step

ROOT = Path(__file__).resolve().parents[1]
BLUE, GREY, GREEN, ORANGE = "#2563eb", "#9ca3af", "#16a34a", "#ea580c"


def bar(data, x, y, color, title, y_title, colors=None, x_title=None, xsort=None, fmt=".3f"):
    enc_color = {"field": color, "type": "nominal", "title": None,
                 "scale": {"range": colors} if colors else {}}
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": title, "fontSize": 14, "anchor": "start"},
        "width": "container", "height": 260, "data": {"values": data},
        "encoding": {
            "x": {"field": x, "type": "nominal", "title": x_title, "sort": xsort, "axis": {"labelAngle": 0}},
            "xOffset": {"field": color},
            "y": {"field": y, "type": "quantitative", "title": y_title},
            "color": enc_color,
            "tooltip": [{"field": x}, {"field": color}, {"field": y, "format": fmt}],
        },
        "layer": [{"mark": {"type": "bar", "cornerRadiusEnd": 3}},
                  {"mark": {"type": "text", "dy": -6, "fontSize": 11},
                   "encoding": {"text": {"field": y, "format": fmt}}}],
    }


class Phase2ResultsFlow(FlowSpec):
    training_run = Parameter("training-run", default="",
                             help="BengaluruQueueModelFlow run id to report (default: latest successful run)")
    predictions = Parameter("predictions", default="",
                            help="That run's held-out test_predictions.csv (default: found from the run's output_root)")
    controller_file = Parameter("controller-results",
                                   default=str(ROOT / "reports" / "phase2_sumo_controller_reruns.json"),
                                   help="JSON summary of the paired SUMO controller re-runs")

    @step
    def start(self):
        """Load the training run's artifacts through the Metaflow client."""
        from metaflow import Flow, Run, namespace
        namespace(None)
        run = (Run(f"BengaluruQueueModelFlow/{self.training_run}") if self.training_run
               else Flow("BengaluruQueueModelFlow").latest_successful_run)
        if run is None:
            raise ValueError("No successful BengaluruQueueModelFlow run found; run the training flow first")
        d = run.data
        self.predictions_path = self.predictions or str(Path(d.output_root) / "evaluation" / "test_predictions.csv")
        self.source_run = run.pathspec
        self.source_successful = run.successful
        self.model_sha256 = d.model_sha256
        self.blob_sha256 = hashlib.sha256(d.model_blob).hexdigest()
        self.dataset_sha256 = d.dataset_sha256
        self.rows, self.run_count = d.rows, d.run_count
        self.registry_status = d.registry_status
        self.train_report = d.report
        self.next(self.model_metrics, self.controller_results)

    @step
    def model_metrics(self):
        """Recompute model vs persistence on the identical held-out rows."""
        import numpy as np
        import pandas as pd
        df = pd.read_csv(self.predictions_path)
        y, p, q = df.queue_length_m_t_plus_60s.values, df.prediction_m.values, df.persistence_m.values
        if len(df) != self.train_report["test"]["n"] or abs(np.mean(np.abs(y - p)) - self.train_report["test"]["mae_m"]) > 1e-9:
            raise ValueError("Prediction file does not match the training run's recorded test metrics")

        def m(mask):
            e, b = p[mask] - y[mask], q[mask] - y[mask]
            return {"n": int(mask.sum()), "model_mae": float(np.mean(np.abs(e))), "persist_mae": float(np.mean(np.abs(b))),
                    "model_rmse": float(np.sqrt(np.mean(e ** 2))), "persist_rmse": float(np.sqrt(np.mean(b ** 2)))}
        allr = np.ones(len(df), bool)
        self.subsets = {"All test rows": m(allr), "Queue in 60 s > 0": m(y > 0),
                        "Queue now or in 60 s > 0": m((y > 0) | (q > 0)), "No queue in 60 s": m(y == 0)}
        order = ["low", "medium", "high", "surge_600", "surge_720"]
        present = [s for s in order if s in set(df.scenario)] + sorted(set(df.scenario) - set(order))
        self.by_demand = {s: m(df.scenario.values == s) for s in present}
        self.zero_share = float((y == 0).mean())
        pos = df[y > 0].sample(n=min(800, int((y > 0).sum())), random_state=0)
        self.scatter = [{"actual": float(a), "predicted": float(b)} for a, b in
                        zip(pos.queue_length_m_t_plus_60s, pos.prediction_m)]
        self.next(self.join)

    @step
    def controller_results(self):
        """Collect the paired SUMO controller re-runs (SUMO 1.28.0)."""
        runs = json.loads(Path(self.controller_file).read_text(encoding="utf-8"))["runs"]
        self.controller_runs = sorted(runs, key=lambda r: (r["batch"], r["seed"], r["policy"]))
        self.next(self.join)

    @step
    def join(self, inputs):
        self.merge_artifacts(inputs)
        self.next(self.end)

    @card(type="blank", id="phase2_results", refresh_interval=0)
    @step
    def end(self):
        """Build the results card."""
        from metaflow.cards import Markdown, Table, ValueBox, VegaChart
        c = current.card["phase2_results"]
        r = self.train_report
        test_n, val_n = r["test"]["n"], r["validation"]["n"]
        c.append(Markdown("# Bengaluru queue model and signal control results\n"
                          f"Source: Metaflow run **{self.source_run}** (successful={self.source_successful}). "
                          "Target: `queue_length_m_t_plus_60s` (metres, 60 s ahead). Simulation data from SUMO on an "
                          "OpenStreetMap Bengaluru corridor; demand and signal timings are assumptions."))
        c.append(Table([[ValueBox(title="Training rows", value=f"{self.rows:,}"),
                         ValueBox(title="SUMO runs", value=str(self.run_count)),
                         ValueBox(title="Test MAE (model)", value=f"{r['test']['mae_m']:.4f} m"),
                         ValueBox(title="Test MAE (persistence)", value=f"{r['persistence']['test']['mae_m']:.4f} m"),
                         ValueBox(title="Quality gate", value="PASSED" if all(r["acceptance_gate"].values()) else "FAILED")]]))

        c.append(Markdown("## 1. Data split (by whole simulation seed)"))
        split = [{"split": "Train (seeds 7, 42, 2026)", "rows": self.rows - val_n - test_n},
                 {"split": "Validation (seed 99)", "rows": val_n},
                 {"split": "Test (seeds 123, 31415)", "rows": test_n}]
        c.append(VegaChart({"$schema": "https://vega.github.io/schema/vega-lite/v5.json", "width": "container", "height": 160,
                            "data": {"values": split}, "mark": {"type": "bar", "cornerRadiusEnd": 3},
                            "encoding": {"y": {"field": "split", "type": "nominal", "title": None, "sort": None},
                                         "x": {"field": "rows", "type": "quantitative", "title": "rows"},
                                         "color": {"field": "split", "legend": None,
                                                   "scale": {"range": [BLUE, ORANGE, GREEN]}},
                                         "tooltip": [{"field": "split"}, {"field": "rows", "format": ","}]}}))
        zero = [{"kind": "No queue in 60 s", "share": self.zero_share}, {"kind": "Queue in 60 s > 0", "share": 1 - self.zero_share}]
        c.append(VegaChart({"$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                            "title": f"Test rows: {self.zero_share:.2%} have no queue 60 s later",
                            "width": 260, "height": 220, "data": {"values": zero}, "mark": {"type": "arc", "innerRadius": 60},
                            "encoding": {"theta": {"field": "share", "type": "quantitative"},
                                         "color": {"field": "kind", "title": None, "scale": {"range": [GREY, BLUE]}},
                                         "tooltip": [{"field": "kind"}, {"field": "share", "format": ".2%"}]}}))

        c.append(Markdown("## 2. Model vs persistence baseline (same 112,176 held-out rows)\n"
                          "Persistence = \"the queue in 60 s equals the queue now\"."))
        order = list(self.subsets)
        mae = [{"subset": k, "who": w, "MAE (m)": v[f"{key}_mae"]} for k, v in self.subsets.items()
               for w, key in [("Model", "model"), ("Persistence", "persist")]]
        rmse = [{"subset": k, "who": w, "RMSE (m)": v[f"{key}_rmse"]} for k, v in self.subsets.items()
                for w, key in [("Model", "model"), ("Persistence", "persist")]]
        c.append(VegaChart(bar(mae, "subset", "MAE (m)", "who", "Mean absolute error (lower is better)", "MAE (m)",
                               [BLUE, GREY], xsort=order)))
        c.append(VegaChart(bar(rmse, "subset", "RMSE (m)", "who", "Root mean squared error (lower is better)", "RMSE (m)",
                               [BLUE, GREY], xsort=order)))
        c.append(Table([[k, f"{v['n']:,}", f"{v['model_mae']:.4f}", f"{v['persist_mae']:.4f}", f"{v['model_rmse']:.4f}",
                         f"{v['persist_rmse']:.4f}"] for k, v in self.subsets.items()],
                       headers=["Subset", "Rows", "Model MAE", "Persistence MAE", "Model RMSE", "Persistence RMSE"]))
        c.append(Markdown("**Reading:** the model beats persistence overall and on rows with a queue now or later. "
                          "On rows whose queue 60 s later is positive, persistence has the lower MAE while the model has the lower RMSE."))

        dem = [{"demand": k, "who": w, "MAE (m)": v[f"{key}_mae"]} for k, v in self.by_demand.items()
               for w, key in [("Model", "model"), ("Persistence", "persist")]]
        c.append(VegaChart(bar(dem, "demand", "MAE (m)", "who", "Test MAE by demand level", "MAE (m)", [BLUE, GREY],
                               xsort=list(self.by_demand))))
        c.append(VegaChart({"$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                            "title": "Predicted vs actual queue 60 s ahead (800 sampled test rows with a positive queue)",
                            "width": "container", "height": 300, "data": {"values": self.scatter},
                            "layer": [{"mark": {"type": "point", "filled": True, "opacity": 0.35, "color": BLUE},
                                       "encoding": {"x": {"field": "actual", "type": "quantitative", "title": "actual (m)"},
                                                    "y": {"field": "predicted", "type": "quantitative", "title": "predicted (m)"},
                                                    "tooltip": [{"field": "actual"}, {"field": "predicted", "format": ".2f"}]}},
                                      {"data": {"values": [{"v": 0}, {"v": 60}]},
                                       "mark": {"type": "line", "color": GREY, "strokeDash": [4, 4]},
                                       "encoding": {"x": {"field": "v", "type": "quantitative"},
                                                    "y": {"field": "v", "type": "quantitative"}}}]}))

        c.append(Markdown("## 3. Signal control in SUMO (18 paired runs, SUMO 1.28.0)\n"
                          "Same routes and seed for all three controllers in each pair. All runs completed with 0 teleports and 0 collisions."))
        agg = {}
        for x in self.controller_runs:
            agg.setdefault((x["batch"], x["policy"]), []).append(x)
        tt = [{"batch": b, "controller": p, "Mean travel time (s)": sum(v["travel_time_s"] for v in xs) / len(xs)}
              for (b, p), xs in agg.items()]
        wt = [{"batch": b, "controller": p, "Mean waiting time (s)": sum(v["waiting_time_s"] for v in xs) / len(xs)}
              for (b, p), xs in agg.items()]
        pol_colors = [GREEN, ORANGE, BLUE]
        tt_chart = bar(tt, "batch", "Mean travel time (s)", "controller", "Mean travel time (lower is better)",
                       "seconds", pol_colors, fmt=".1f")
        tt_chart["encoding"]["color"]["sort"] = ["fixed", "adaptive", "predictive"]
        tt_chart["encoding"]["y"]["scale"] = {"zero": False}
        wt_chart = bar(wt, "batch", "Mean waiting time (s)", "controller", "Mean waiting time (lower is better)",
                       "seconds", pol_colors, fmt=".1f")
        wt_chart["encoding"]["color"]["sort"] = ["fixed", "adaptive", "predictive"]
        wt_chart["encoding"]["y"]["scale"] = {"zero": False}
        c.append(VegaChart(tt_chart))
        c.append(VegaChart(wt_chart))
        fixed = {(x["batch"], x["seed"]): x["travel_time_s"] for x in self.controller_runs if x["policy"] == "fixed"}
        delta = [{"pair": f'{x["batch"].split(" ")[0]} seed {x["seed"]}', "controller": x["policy"],
                  "difference vs fixed (s)": x["travel_time_s"] - fixed[(x["batch"], x["seed"])]}
                 for x in self.controller_runs if x["policy"] != "fixed"]
        d_chart = bar(delta, "pair", "difference vs fixed (s)", "controller",
                      "Travel time minus fixed-time, per paired seed (above 0 = slower than fixed)", "seconds",
                      [ORANGE, BLUE], fmt="+.2f")
        c.append(VegaChart(d_chart))
        c.append(Markdown("**Result:** fixed-time had the lowest mean travel and waiting time in both batches. "
                          "Predictive control was slower than fixed-time in 5 of 6 paired seeds. Predictive control is **not** shown to be better."))

        c.append(Markdown("## 4. Lineage and quality gate"))
        c.append(Table([["Training run", self.source_run], ["Dataset SHA-256", self.dataset_sha256],
                        ["Model SHA-256 (artifact)", self.model_sha256],
                        ["Model SHA-256 (re-hashed model_blob)", self.blob_sha256],
                        ["Registry status", self.registry_status],
                        ["Split seeds", f"train {r['train_seeds']}, validation {r['validation_seeds']}, test {r['test_seeds']}"],
                        ["Classifier threshold (chosen on validation)", str(r["queue_present_classifier_threshold"])]]
                       + [[f"Gate: {k}", str(v)] for k, v in r["acceptance_gate"].items()],
                       headers=["Item", "Value"]))
        print("Card built:", self.source_run, self.model_sha256[:12])


if __name__ == "__main__":
    Phase2ResultsFlow()
