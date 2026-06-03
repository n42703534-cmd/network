from datetime import datetime
from pathlib import Path
import csv
import time

import network


BASE_LOADS = {
    "L2": {"platform_waiting": 236, "hall_people": 350, "transfer_people": 526},
    "L7": {"platform_waiting": 219, "hall_people": 112, "transfer_people": 169},
    "L16": {"platform_waiting": 42, "hall_people": 15, "transfer_people": 27},
    "L18": {"platform_waiting": 178, "hall_people": 125, "transfer_people": 188},
    "Maglev": {"platform_waiting": 0, "hall_people": 0, "transfer_people": 0},
}


FIELDS = [
    "scenario_mode",
    "scenario_label",
    "total_people",
    "method",
    "time",
    "avg_travel_time",
    "avg_speed",
    "queueing_time",
    "congestion_exposure_time",
    "severe_congestion_exposure_time",
    "edge_congestion_exposure_time",
    "edge_severe_congestion_exposure_time",
    "peak_congestion_index",
    "wall_clock_runtime_s",
]


def build_mode4_pop():
    pop = {}
    total = 0
    for line, physics in network.TRAIN_PHYSICS.items():
        base = BASE_LOADS[line]
        train_total = int(round(network._train_total_people(physics)))
        pop[line] = {
            "train_1": train_total,
            "train_2": train_total,
            "platform_waiting": int(base["platform_waiting"]),
            "hall_people": int(base["hall_people"]),
            "transfer_people": int(base["transfer_people"]),
        }
        total += sum(pop[line].values())
    return pop, total


def write_rows(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    run_dir = Path("outputs") / ("mode4_edge_density_full_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    run_dir.mkdir(parents=True, exist_ok=True)
    summary_path = run_dir / "mode4_edge_density_method_summary.csv"
    pop, total = build_mode4_pop()
    rows = []
    methods = [
        ("ACO", network.ANT_COLONY_METHOD),
        ("ImprovedAStar", network.PAPER_SINGLE_PATH_METHOD),
        ("AdaptiveSingleNextHop", network.OUR_SINGLE_PATH_METHOD),
    ]

    print(f"RUN_DIR={run_dir.resolve()}", flush=True)
    print(f"TOTAL_PEOPLE={total}", flush=True)
    for label, method in methods:
        print(f"START {label}", flush=True)
        start = time.perf_counter()
        metrics = network.run_simulation_for_metrics_timed(network.build_graph(), pop, method=method)
        row = {
            "scenario_mode": 4,
            "scenario_label": "mode4_bidirectional_full_train_edge_density",
            "total_people": total,
            "method": label,
            "time": metrics["time"],
            "avg_travel_time": metrics.get("avg_travel_time", 0.0),
            "avg_speed": metrics.get("avg_speed", 0.0),
            "queueing_time": metrics["queueing_time"],
            "congestion_exposure_time": metrics["congestion_exposure_time"],
            "severe_congestion_exposure_time": metrics.get("severe_congestion_exposure_time", 0.0),
            "edge_congestion_exposure_time": metrics.get("edge_congestion_exposure_time", 0.0),
            "edge_severe_congestion_exposure_time": metrics.get("edge_severe_congestion_exposure_time", 0.0),
            "peak_congestion_index": metrics.get("peak_congestion_index", 0.0),
            "wall_clock_runtime_s": metrics.get("wall_clock_runtime_s", time.perf_counter() - start),
        }
        rows.append(row)
        write_rows(summary_path, rows)
        print(
            "DONE {method} time={time} queue={queue:.1f} congestion={cong:.1f} "
            "severe={severe:.1f} edge_cong={edge:.1f} edge_severe={edge_severe:.1f} wall={wall:.2f}".format(
                method=label,
                time=row["time"],
                queue=row["queueing_time"],
                cong=row["congestion_exposure_time"],
                severe=row["severe_congestion_exposure_time"],
                edge=row["edge_congestion_exposure_time"],
                edge_severe=row["edge_severe_congestion_exposure_time"],
                wall=row["wall_clock_runtime_s"],
            ),
            flush=True,
        )
    print(f"SAVED {summary_path.resolve()}", flush=True)


if __name__ == "__main__":
    main()
