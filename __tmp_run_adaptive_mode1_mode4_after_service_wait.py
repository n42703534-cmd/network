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
            raise ValueError(mode)
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
        "adaptive_service_wait_check_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    line_rows = []
    print(f"RUN_DIR={run_dir.resolve()}", flush=True)
    print(
        f"OUR_SERVICE_WAIT_TIME_WEIGHT={network.spr.OUR_SERVICE_WAIT_TIME_WEIGHT}",
        flush=True,
    )
    for mode, label in [(1, "mode1_regular_emergency"), (4, "mode4_bidirectional_full_train")]:
        pop, total = build_pop(mode)
        print(f"START mode={mode} total={total}", flush=True)
        graph = network.build_graph()
        metrics = network.run_simulation_for_metrics_timed(
            graph, pop, method=network.OUR_SINGLE_PATH_METHOD
        )
        row = {
            "scenario_mode": mode,
            "scenario_label": label,
            "total_people": total,
            "method": "AdaptiveSingleNextHop",
            "time": metrics["time"],
            "queueing_time": metrics["queueing_time"],
            "moderate_congestion_exposure_time": metrics["congestion_exposure_time"],
            "severe_congestion_exposure_time": metrics.get("severe_congestion_exposure_time", 0.0),
            "peak_congestion_index": metrics.get("peak_congestion_index", 0.0),
            "avg_speed": metrics.get("avg_speed"),
            "avg_travel_time": metrics.get("avg_travel_time"),
            "wall_clock_runtime_s": metrics.get("wall_clock_runtime_s"),
        }
        rows.append(row)
        pd.DataFrame(rows).to_csv(
            run_dir / "adaptive_service_wait_summary_partial.csv",
            index=False,
            encoding="utf-8-sig",
        )
        print(
            f"DONE mode={mode} time={row['time']} queue={row['queueing_time']:.1f} "
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
                    "scenario_label": label,
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
    pd.DataFrame(rows).to_csv(run_dir / "adaptive_service_wait_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(line_rows).to_csv(run_dir / "adaptive_service_wait_line_summary.csv", index=False, encoding="utf-8-sig")
    print(f"SAVED {run_dir.resolve()}", flush=True)


if __name__ == "__main__":
    main()
