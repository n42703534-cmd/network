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


def apply_capacity_factor(G, factor):
    for _, data in G.nodes(data=True):
        cap = float(data.get("capacity", 0.0) or 0.0)
        if cap > 0 and cap < 999999:
            data["capacity"] = cap * factor
    for _, _, data in G.edges(data=True):
        cap = float(data.get("capacity", 0.0) or 0.0)
        if cap > 0 and cap < 999999:
            data["capacity"] = cap * factor


def main():
    factors = [0.65, 0.55, 0.50]
    pop, total = build_mode4_pop()
    run_dir = Path("outputs") / ("mode4_calibrated_improved_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / "mode4_calibrated_improved_summary.csv"
    rows = []
    for factor in factors:
        print(f"START factor={factor}", flush=True)
        G = network.build_graph()
        apply_capacity_factor(G, factor)
        metrics = network.run_simulation_for_metrics_timed(G, pop, method=network.PAPER_SINGLE_PATH_METHOD)
        row = {
            "capacity_factor": factor,
            "total_people": total,
            "method": "ImprovedAStar",
            "time": metrics["time"],
            "queueing_time": metrics["queueing_time"],
            "congestion_exposure_time": metrics["congestion_exposure_time"],
            "severe_congestion_exposure_time": metrics.get("severe_congestion_exposure_time", 0.0),
            "peak_congestion_index": metrics.get("peak_congestion_index", 0.0),
            "wall_clock_runtime_s": metrics.get("wall_clock_runtime_s", 0.0),
        }
        rows.append(row)
        with out.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(
            "DONE factor={factor} time={time} queue={queue:.1f} congestion={cong:.1f} severe={severe:.1f} wall={wall:.1f}".format(
                factor=factor,
                time=row["time"],
                queue=row["queueing_time"],
                cong=row["congestion_exposure_time"],
                severe=row["severe_congestion_exposure_time"],
                wall=row["wall_clock_runtime_s"],
            ),
            flush=True,
        )
    print(f"SAVED {out.resolve()}", flush=True)


if __name__ == "__main__":
    main()
