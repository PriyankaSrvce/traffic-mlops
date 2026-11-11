"""Create dependency-free SVG plots from saved Phase 2 evaluation reports."""

import argparse
import csv
import json
from pathlib import Path


POLICIES = ("fixed", "adaptive", "predictive60s")
POLICY_LABELS = {"fixed": "Fixed", "adaptive": "Adaptive", "predictive60s": "Predictive 60s"}
COLORS = {"fixed": "#64748b", "adaptive": "#0f766e", "predictive60s": "#7c3aed"}


def xml(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def policy_svg(rows, output):
    scenarios = ["low", "reference", "high"]
    metrics = [("mean_duration_s", "Mean trip duration (s)"),
               ("mean_waitingTime_s", "Mean waiting time (s)")]
    width, height = 1080, 660
    panel_lefts = (100, 585)
    panel_width, panel_top, panel_height = 420, 105, 430
    by_key = {(row["scenario"], row["policy"]): row for row in rows}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<style>text{font-family:Arial,sans-serif;fill:#172033}.axis{stroke:#64748b;stroke-width:1}.grid{stroke:#e2e8f0;stroke-width:1}</style>',
             '<text x="540" y="38" text-anchor="middle" font-size="23" font-weight="700">Paired controller results: perimeter P25/P50/P75 scenarios</text>',
             '<text x="540" y="65" text-anchor="middle" font-size="13">Three paired random seeds per scenario; lower trip times are better</text>']
    for panel_index, (metric, title) in enumerate(metrics):
        left = panel_lefts[panel_index]
        values = [float(by_key[(scenario, policy)][metric])
                  for scenario in scenarios for policy in POLICIES]
        max_value = max(values) * 1.12
        parts.append(f'<text x="{left + panel_width/2}" y="90" text-anchor="middle" font-size="17" font-weight="700">{xml(title)}</text>')
        parts.append(f'<line class="axis" x1="{left}" y1="{panel_top + panel_height}" x2="{left + panel_width}" y2="{panel_top + panel_height}"/>')
        parts.append(f'<line class="axis" x1="{left}" y1="{panel_top}" x2="{left}" y2="{panel_top + panel_height}"/>')
        for tick in range(5):
            value = max_value * tick / 4
            y = panel_top + panel_height - (panel_height * tick / 4)
            parts.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{left + panel_width}" y2="{y:.1f}"/>')
            parts.append(f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="11">{value:.0f}</text>')
        group_width = panel_width / len(scenarios)
        bar_width = 25
        for scenario_index, scenario in enumerate(scenarios):
            center = left + group_width * (scenario_index + 0.5)
            for policy_index, policy in enumerate(POLICIES):
                value = float(by_key[(scenario, policy)][metric])
                bar_height = value / max_value * panel_height
                x = center + (policy_index - 1) * (bar_width + 6) - bar_width / 2
                y = panel_top + panel_height - bar_height
                parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width}" height="{bar_height:.1f}" fill="{COLORS[policy]}"/>')
                parts.append(f'<text x="{x + bar_width/2:.1f}" y="{y - 5:.1f}" text-anchor="middle" font-size="10">{value:.1f}</text>')
            parts.append(f'<text x="{center:.1f}" y="{panel_top + panel_height + 22}" text-anchor="middle" font-size="12">{xml(scenario.title())}</text>')
    legend_x, legend_y = 230, 615
    for index, policy in enumerate(POLICIES):
        x = legend_x + index * 220
        parts.append(f'<rect x="{x}" y="{legend_y - 12}" width="14" height="14" fill="{COLORS[policy]}"/>')
        parts.append(f'<text x="{x + 21}" y="{legend_y}" font-size="12">{xml(POLICY_LABELS[policy])}</text>')
    parts.append('</svg>')
    output.write_text("\n".join(parts), encoding="utf-8")


def queue_svg(report, output):
    scenarios = ("low", "reference", "high")
    metrics = (("mae_m", "MAE (m)"), ("rmse_m", "RMSE (m)"))
    width, height = 1080, 520
    panel_lefts = (110, 590)
    panel_width, panel_top, panel_height = 420, 95, 320
    grouped = report["test_metrics_by_scenario"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             '<style>text{font-family:Arial,sans-serif;fill:#172033}.axis{stroke:#64748b;stroke-width:1}.grid{stroke:#e2e8f0;stroke-width:1}</style>',
             '<text x="540" y="34" text-anchor="middle" font-size="22" font-weight="700">60-second queue prediction vs persistence</text>',
             '<text x="540" y="60" text-anchor="middle" font-size="13">Held-out SUMO seed 99; queue error is measured in metres</text>']
    colors = {"model": "#7c3aed", "persistence": "#94a3b8"}
    labels = {"model": "Random Forest", "persistence": "Persistence"}
    for panel_index, (metric, title) in enumerate(metrics):
        left = panel_lefts[panel_index]
        values = [grouped[s][m][metric] for s in scenarios for m in ("model", "persistence")]
        max_value = max(values) * 1.15
        parts.append(f'<text x="{left + panel_width/2}" y="82" text-anchor="middle" font-size="16" font-weight="700">{xml(title)}</text>')
        parts.append(f'<line class="axis" x1="{left}" y1="{panel_top + panel_height}" x2="{left + panel_width}" y2="{panel_top + panel_height}"/>')
        for tick in range(5):
            value = max_value * tick / 4
            y = panel_top + panel_height - panel_height * tick / 4
            parts.append(f'<line class="grid" x1="{left}" y1="{y:.1f}" x2="{left + panel_width}" y2="{y:.1f}"/>')
            parts.append(f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" font-size="11">{value:.1f}</text>')
        group_width = panel_width / len(scenarios)
        for scenario_index, scenario in enumerate(scenarios):
            center = left + group_width * (scenario_index + 0.5)
            for item_index, item in enumerate(("model", "persistence")):
                value = grouped[scenario][item][metric]
                bar_width = 38
                bar_height = value / max_value * panel_height
                x = center + (item_index - 0.5) * (bar_width + 8) - bar_width / 2
                y = panel_top + panel_height - bar_height
                parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width}" height="{bar_height:.1f}" fill="{colors[item]}"/>')
                parts.append(f'<text x="{x + bar_width/2:.1f}" y="{y - 5:.1f}" text-anchor="middle" font-size="10">{value:.2f}</text>')
            parts.append(f'<text x="{center:.1f}" y="{panel_top + panel_height + 22}" text-anchor="middle" font-size="12">{xml(scenario.title())}</text>')
    for index, item in enumerate(("model", "persistence")):
        x = 400 + index * 180
        parts.append(f'<rect x="{x}" y="470" width="14" height="14" fill="{colors[item]}"/><text x="{x+20}" y="482" font-size="12">{xml(labels[item])}</text>')
    parts.append('</svg>')
    output.write_text("\n".join(parts), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-summary", type=Path, required=True)
    parser.add_argument("--model-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    outputs = [args.output_dir / "phase2_policy_comparison.svg",
               args.output_dir / "phase2_queue_prediction_vs_persistence.svg"]
    if any(path.exists() for path in outputs):
        raise FileExistsError("Refusing to overwrite an existing SVG result.")
    with args.policy_summary.open("r", newline="", encoding="utf-8-sig") as source:
        policy_rows = list(csv.DictReader(source))
    with args.model_report.open("r", encoding="utf-8") as source:
        model_report = json.load(source)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    policy_svg(policy_rows, outputs[0])
    queue_svg(model_report, outputs[1])
    for path in outputs:
        print(path.resolve())


if __name__ == "__main__":
    main()
