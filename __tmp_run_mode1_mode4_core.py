from datetime import datetime
from pathlib import Path

import pandas as pd

import network


BASE_LOADS = {
    "L2": {"platform_waiting": 236, "hall_people": 350, "transfer_people": 526},
    "L7": {"platform_waiting": 219, "hall_people": 112, "transfer_people": 169},
    "L16": {"platform_waiting": 42, "hall_people": 15, "transfer_people": 27},
    "L18": {"platform_waiting": 178, "hall_people": 125, "transfer_people": 188},
    "Maglev": {"platform_waiting": 0, "hall_people": 0, "transfer_people": 0},
}

SCENARIOS = {
    1: "mode1_regular_emergency",
    4: "mode4_bidirectional_full_train",
}

METHODS = [
    ("ACO", network.ANT_COLONY_METHOD),
    ("ImprovedAStar", network.PAPER_SINGLE_PATH_METHOD),
    ("AdaptiveSingleNextHop", network.OUR_SINGLE_PATH_METHOD),
]


def build_pop(mode):
    pop = {}
    total = 0
    for line, physics in network.TRAIN_PHYSICS.items():
        base = BASE_LOADS[line]
        train_total = int(round(network._train_total_people(physics)))
        if mode == 1:
            t1, t2 = 0, 0
        elif mode == 4:
            t1, t2 = train_total, train_total
        else:
            raise ValueError(f"unsupported mode: {mode}")
        pop[line] = {
            "train_1": t1,
            "train_2": t2,
            "platform_waiting": int(base["platform_waiting"]),
            "hall_people": int(base["hall_people"]),
            "transfer_people": int(base["transfer_people"]),
        }
        total += sum(pop[line].values())
    return pop, total


def main():
    run_dir = Path("outputs") / (
        "mode1_mode4_core_congestion_index_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"RUN_DIR={run_dir.resolve()}", flush=True)
    print(
        "SERVICE_QUEUE_HORIZON_SECONDS="
        f"{network.spr.SERVICE_QUEUE_HORIZON_SECONDS}",
        flush=True,
    )

    rows = []
    line_rows = []
    for mode, scenario_label in SCENARIOS.items():
        pop, total_people = build_pop(mode)
        print(f"\nSCENARIO mode={mode} label={scenario_label} total={total_people}", flush=True)

        for method_label, method in METHODS:
            print(f"START {scenario_label} {method_label}", flush=True)
            graph = network.build_graph()
            metrics = network.run_simulation_for_metrics_timed(graph, pop, method=method)
            row = {
                "scenario_mode": mode,
                "scenario_label": scenario_label,
                "total_people": total_people,
                "method": method_label,
                "time": metrics["time"],
                "avg_travel_time": metrics.get("avg_travel_time"),
                "queueing_time": metrics["queueing_time"],
                "moderate_congestion_exposure_time": metrics["congestion_exposure_time"],
                "severe_congestion_exposure_time": metrics.get("severe_congestion_exposure_time", 0.0),
                "peak_density": metrics.get("peak_density", 0.0),
                "peak_congestion_index": metrics.get("peak_congestion_index", 0.0),
                "avg_speed": metrics.get("avg_speed"),
                "wall_clock_runtime_s": metrics.get("wall_clock_runtime_s"),
            }
            rows.append(row)
            pd.DataFrame(rows).to_csv(
                run_dir / "mode1_mode4_core_method_summary_partial.csv",
                index=False,
                encoding="utf-8-sig",
            )

            print(
                f"DONE {scenario_label} {method_label} "
                f"time={row['time']} queue={row['queueing_time']:.1f} "
                f"moderate={row['moderate_congestion_exposure_time']:.1f} "
                f"severe={row['severe_congestion_exposure_time']:.1f} "
                f"peak_index={row['peak_congestion_index']:.3f} "
                f"wall={row['wall_clock_runtime_s']:.2f}",
                flush=True,
            )

            for line in network.TRAIN_PHYSICS:
                line_rows.append(
                    {
                        "scenario_mode": mode,
                        "scenario_label": scenario_label,
                        "total_people": total_people,
                        "method": method_label,
                        "line": line,
                        "clearance_time": (
                            metrics["clearance_times_by_line"].get(line)
                            if metrics["clearance_times_by_line"].get(line) is not None
                            else metrics["time"]
                        ),
                        "core_clearance_time": metrics.get("clearance_times_by_line_core", {}).get(line),
                        "transfer_clearance_time": metrics.get("clearance_times_by_line_transfer", {}).get(line),
                        "moderate_congestion_exposure_time": metrics["congestion_exposure_by_line"].get(line, 0.0),
                        "severe_congestion_exposure_time": metrics["severe_congestion_exposure_by_line"].get(line, 0.0),
                    }
                )

    summary = pd.DataFrame(rows)
    summary.to_csv(run_dir / "mode1_mode4_core_method_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(line_rows).to_csv(run_dir / "mode1_mode4_core_line_summary.csv", index=False, encoding="utf-8-sig")

    improvement_rows = []
    for mode, scenario_label in SCENARIOS.items():
        sub = summary[summary["scenario_mode"] == mode].set_index("method")
        adaptive = sub.loc["AdaptiveSingleNextHop"]
        for baseline_name in ["ACO", "ImprovedAStar"]:
            baseline = sub.loc[baseline_name]
            row = {
                "scenario_mode": mode,
                "scenario_label": scenario_label,
                "baseline": baseline_name,
                "total_people": int(adaptive["total_people"]),
            }
            for metric in [
                "time",
                "queueing_time",
                "moderate_congestion_exposure_time",
                "severe_congestion_exposure_time",
            ]:
                base_value = float(baseline[metric])
                adaptive_value = float(adaptive[metric])
                row[f"{metric}_baseline"] = base_value
                row[f"{metric}_adaptive"] = adaptive_value
                row[f"{metric}_delta"] = adaptive_value - base_value
                row[f"{metric}_improvement_pct"] = (
                    (base_value - adaptive_value) / base_value * 100.0
                    if base_value
                    else 0.0
                )
            improvement_rows.append(row)
    pd.DataFrame(improvement_rows).to_csv(
        run_dir / "mode1_mode4_core_improvement_vs_baselines.csv",
        index=False,
        encoding="utf-8-sig",
    )
    print(f"\nSAVED {run_dir.resolve()}", flush=True)


if __name__ == "__main__":
    main()
