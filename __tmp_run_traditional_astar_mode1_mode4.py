from datetime import datetime
from pathlib import Path
import csv

import network
import networkx as nx


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
    "capacity_factor",
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


def build_pop(mode):
    pop = {}
    total = 0
    for line, physics in network.TRAIN_PHYSICS.items():
        base = BASE_LOADS[line]
        train_total = int(round(network._train_total_people(physics)))
        if mode == 1:
            train_1, train_2 = 0, 0
        elif mode == 4:
            train_1, train_2 = train_total, train_total
        else:
            raise ValueError(mode)

        pop[line] = {
            "train_1": train_1,
            "train_2": train_2,
            "platform_waiting": int(base["platform_waiting"]),
            "hall_people": int(base["hall_people"]),
            "transfer_people": int(base["transfer_people"]),
        }
        total += sum(pop[line].values())
    return pop, total


def install_static_astar_next_hops(G):
    exits = [n for n, data in G.nodes(data=True) if data.get("type") == "exit"]
    shortest = dict(nx.all_pairs_dijkstra_path_length(G, weight="length"))
    fixed_next = {}

    for node, data in G.nodes(data=True):
        if data.get("type") == "exit":
            continue
        reachable = [
            ext
            for ext in exits
            if ext in shortest.get(node, {}) and shortest[node][ext] < float("inf")
        ]
        if not reachable:
            continue
        target = min(reachable, key=lambda ext: shortest[node][ext])
        try:
            path = nx.astar_path(
                G,
                node,
                target,
                heuristic=lambda u, v: shortest.get(u, {}).get(v, 0.0),
                weight="length",
            )
        except nx.NetworkXNoPath:
            continue
        if len(path) > 1:
            fixed_next[node] = path[1]

    G.graph["_fixed_next_by_node"] = fixed_next
    return fixed_next


def run_one(mode, label):
    G = network.build_graph()
    fixed_next = install_static_astar_next_hops(G)
    pop, total = build_pop(mode)
    print(f"START mode={mode} fixed_next_nodes={len(fixed_next)} total={total}", flush=True)
    metrics = network.run_simulation_for_metrics_timed(
        G,
        pop,
        method=network.PAPER_SINGLE_PATH_METHOD,
    )
    row = {
        "scenario_mode": mode,
        "scenario_label": label,
        "capacity_factor": getattr(network, "PATHFINDER_CAPACITY_CALIBRATION_FACTOR", ""),
        "total_people": total,
        "method": "TraditionalAStar_StaticLength",
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
    print(
        "DONE mode={mode} time={time} queue={queue:.1f} congestion={cong:.1f} "
        "severe={severe:.1f} peak={peak:.3f} wall={wall:.2f}".format(
            mode=mode,
            time=row["time"],
            queue=row["queueing_time"],
            cong=row["congestion_exposure_time"],
            severe=row["severe_congestion_exposure_time"],
            peak=row["peak_congestion_index"],
            wall=row["wall_clock_runtime_s"],
        ),
        flush=True,
    )
    return row


def main():
    run_dir = Path("outputs") / ("traditional_astar_mode1_mode4_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    run_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        run_one(1, "mode1_regular_emergency"),
        run_one(4, "mode4_bidirectional_full_train"),
    ]
    out = run_dir / "traditional_astar_mode1_mode4_summary.csv"
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"SAVED {out.resolve()}", flush=True)


if __name__ == "__main__":
    main()
