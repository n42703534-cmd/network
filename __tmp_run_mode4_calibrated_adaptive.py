from datetime import datetime
from pathlib import Path
import csv

import network


BASE_LOADS = {
    "L2": {"platform_waiting": 236, "hall_people": 350, "transfer_people": 526},
    "L7": {"platform_waiting": 219, "hall_people": 112, "transfer_people": 169},
    "L16": {"platform_waiting": 42, "hall_people": 15, "transfer_people": 27},
    "L18": {"platform_waiting": 178, "hall_people": 125, "transfer_people": 188},
    "Maglev": {"platform_waiting": 0, "hall_people": 0, "transfer_people": 0},
}


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


def main():
    pop, total = build_mode4_pop()
    run_dir = Path("outputs") / ("mode4_calibrated_adaptive_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / "mode4_calibrated_adaptive_summary.csv"
    print(f"RUN_DIR={run_dir.resolve()}", flush=True)
    print(f"TOTAL_PEOPLE={total}", flush=True)
    print(f"CAPACITY_FACTOR={network.PATHFINDER_CAPACITY_CALIBRATION_FACTOR}", flush=True)
    metrics = network.run_simulation_for_metrics_timed(
        network.build_graph(),
        pop,
        method=network.OUR_SINGLE_PATH_METHOD,
    )
    row = {
        "scenario_mode": 4,
        "scenario_label": "mode4_bidirectional_full_train_calibrated_0.55",
        "capacity_factor": network.PATHFINDER_CAPACITY_CALIBRATION_FACTOR,
        "total_people": total,
        "method": "AdaptiveSingleNextHop",
        "time": metrics["time"],
        "avg_travel_time": metrics.get("avg_travel_time", 0.0),
        "avg_speed": metrics.get("avg_speed", 0.0),
        "queueing_time": metrics["queueing_time"],
        "congestion_exposure_time": metrics["congestion_exposure_time"],
        "severe_congestion_exposure_time": metrics.get("severe_congestion_exposure_time", 0.0),
        "edge_congestion_exposure_time": metrics.get("edge_congestion_exposure_time", 0.0),
        "edge_severe_congestion_exposure_time": metrics.get("edge_severe_congestion_exposure_time", 0.0),
        "peak_congestion_index": metrics.get("peak_congestion_index", 0.0),
        "wall_clock_runtime_s": metrics.get("wall_clock_runtime_s", 0.0),
    }
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)
    print(
        "DONE AdaptiveSingleNextHop time={time} queue={queue:.1f} congestion={cong:.1f} "
        "severe={severe:.1f} edge_cong={edge:.1f} edge_severe={edge_severe:.1f} wall={wall:.1f}".format(
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
    print(f"SAVED {out.resolve()}", flush=True)


if __name__ == "__main__":
    main()
