from __future__ import annotations

import math
import random
import time
from datetime import datetime
from pathlib import Path

import networkx as nx
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

IACOGA_METHOD = "JournalIACOGA2026_MultiObjective"

METHODS = [
    ("ImprovedAStar", network.PAPER_SINGLE_PATH_METHOD),
    ("IACO_GA_2026", IACOGA_METHOD),
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


def _safe_congestion_index(G, node):
    if node not in G.nodes:
        return 0.0
    try:
        value, _ = network._node_congestion_index(G, node)
        return max(float(value), 0.0)
    except Exception:
        return 0.0


def _service_pressure(G, node):
    if node not in G.nodes or not network.spr.is_capacity_service_node(G, node):
        return 0.0
    people = float(G.nodes[node].get("people", 0.0))
    capacity = network.spr.node_service_capacity(G, node) * network.spr.SERVICE_QUEUE_HORIZON_SECONDS
    return people / max(capacity, 0.001)


def _edge_exit_approach_pressure(G, u, v):
    pressure = 0.0
    if v not in G.nodes:
        return 0.0
    for succ in G.successors(v):
        if G.nodes[succ].get("type") == "exit":
            pressure = max(pressure, float(network.spr.smoothed_approach_pressure(G, v, succ)))
    return pressure


def _local_edge_cost(G, u, v):
    if not G.has_edge(u, v):
        return float("inf")
    travel = float(network._edge_travel_time(G, u, v))
    congestion = _safe_congestion_index(G, v)
    service = _service_pressure(G, v)
    approach = _edge_exit_approach_pressure(G, u, v)
    return travel + 6.0 * congestion + 14.0 * service + 8.0 * approach


def _path_objectives(G, path):
    if not path or len(path) <= 1:
        return {
            "time": float("inf"),
            "risk": float("inf"),
            "pressure": float("inf"),
            "score": float("inf"),
        }
    travel = 0.0
    risk = 0.0
    pressure = 0.0
    for idx in range(len(path) - 1):
        u, v = path[idx], path[idx + 1]
        if not G.has_edge(u, v):
            return {
                "time": float("inf"),
                "risk": float("inf"),
                "pressure": float("inf"),
                "score": float("inf"),
            }
        travel += float(network._edge_travel_time(G, u, v))
        cong = _safe_congestion_index(G, v)
        risk += max(cong - 1.0, 0.0) ** 2 + 1.5 * _service_pressure(G, v)
        pressure += _edge_exit_approach_pressure(G, u, v)
    score = travel + 22.0 * risk + 10.0 * pressure
    return {"time": travel, "risk": risk, "pressure": pressure, "score": score}


def _dominates(a, b):
    ao = (a["objectives"]["time"], a["objectives"]["risk"], a["objectives"]["pressure"])
    bo = (b["objectives"]["time"], b["objectives"]["risk"], b["objectives"]["pressure"])
    return all(x <= y + 1e-9 for x, y in zip(ao, bo)) and any(x < y - 1e-9 for x, y in zip(ao, bo))


def _pareto_rank(paths):
    front = []
    for item in paths:
        if not any(_dominates(other, item) for other in paths if other is not item):
            front.append(item)
    front.sort(key=lambda item: item["objectives"]["score"])
    return front


def _candidate_seed_paths(G, source, exits, max_paths=10):
    seeds = []
    for exit_node in exits:
        try:
            path = nx.shortest_path(G, source, exit_node, weight="length")
        except nx.NetworkXNoPath:
            continue
        if len(path) > 1:
            seeds.append(path)

    for u, v in G.edges():
        G[u][v]["_iacoga_seed_weight"] = _local_edge_cost(G, u, v)

    for exit_node in exits:
        try:
            path = nx.shortest_path(G, source, exit_node, weight="_iacoga_seed_weight")
        except nx.NetworkXNoPath:
            continue
        if len(path) > 1:
            seeds.append(path)

    unique = []
    seen = set()
    for path in seeds:
        key = tuple(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)

    scored = [
        {"path": path, "objectives": _path_objectives(G, path)}
        for path in unique
    ]
    scored = [item for item in scored if math.isfinite(item["objectives"]["score"])]
    scored.sort(key=lambda item: item["objectives"]["score"])
    return [item["path"] for item in scored[:max_paths]]


def _roulette(items, weights, rng):
    total = sum(max(float(w), 0.0) for w in weights)
    if total <= 0:
        return rng.choice(items)
    pick = rng.random() * total
    acc = 0.0
    for item, weight in zip(items, weights):
        acc += max(float(weight), 0.0)
        if acc >= pick:
            return item
    return items[-1]


def _construct_ant_path(G, source, exits, shortest_dists, pheromone, rng, max_hops=80):
    path = [source]
    visited = {source}
    current = source

    for _ in range(max_hops):
        if current in exits:
            return path

        successors = [
            succ for succ in G.successors(current)
            if succ not in visited and G.has_edge(current, succ)
        ]
        if not successors:
            return None

        desirabilities = []
        for succ in successors:
            nearest_exit_dist = min(
                float(shortest_dists.get(succ, {}).get(exit_node, float("inf")))
                for exit_node in exits
            )
            if not math.isfinite(nearest_exit_dist):
                desirabilities.append(0.0)
                continue
            local_cost = _local_edge_cost(G, current, succ)
            eta = 1.0 / max(local_cost + nearest_exit_dist / network.spr.PAPER_FREE_SPEED, 1e-6)
            tau = float(pheromone.get((current, succ), 1.0))
            desirabilities.append((tau ** 1.2) * (eta ** 3.0))

        nxt = _roulette(successors, desirabilities, rng)
        path.append(nxt)
        visited.add(nxt)
        current = nxt

    return path if current in exits else None


def _seed_pheromone_from_ga(G, seed_paths, pheromone):
    for path in seed_paths:
        obj = _path_objectives(G, path)
        if not math.isfinite(obj["score"]):
            continue
        deposit = 30.0 / max(obj["score"], 1e-6)
        for idx in range(len(path) - 1):
            edge = (path[idx], path[idx + 1])
            pheromone[edge] = pheromone.get(edge, 1.0) + deposit


def _iacoga_candidate_paths(G, source, shortest_dists, top_k=3):
    if source not in G.nodes:
        return []
    exits = [n for n, d in G.nodes(data=True) if d.get("type") == "exit"]
    if not exits:
        return []

    current_time = float(G.graph.get("_sim_time", 0.0))
    cache = G.graph.setdefault("_iacoga_path_cache", {})
    cache_key = (source, int(current_time // 20.0))
    cached = cache.get(cache_key)
    if cached:
        usable = [
            item for item in cached
            if item["path"] and len(item["path"]) > 1 and G.has_edge(item["path"][0], item["path"][1])
        ]
        if usable:
            return usable

    rng = G.graph.setdefault("_iacoga_rng", random.Random(20260601))
    pheromone = G.graph.setdefault("_iacoga_pheromone", {})

    seeds = _candidate_seed_paths(G, source, exits, max_paths=10)
    _seed_pheromone_from_ga(G, seeds, pheromone)

    candidates = []
    for path in seeds:
        candidates.append({"path": path, "objectives": _path_objectives(G, path)})

    ant_count = 24
    iterations = 18
    evaporation = 0.25
    for _ in range(iterations):
        ant_paths = []
        for _ant in range(ant_count):
            path = _construct_ant_path(G, source, set(exits), shortest_dists, pheromone, rng)
            if not path or len(path) <= 1 or path[-1] not in exits:
                continue
            obj = _path_objectives(G, path)
            if not math.isfinite(obj["score"]):
                continue
            ant_paths.append({"path": path, "objectives": obj})
            candidates.append({"path": path, "objectives": obj})

        for edge in list(pheromone):
            pheromone[edge] = max(pheromone[edge] * (1.0 - evaporation), 0.05)

        ant_paths.sort(key=lambda item: item["objectives"]["score"])
        for item in ant_paths[:8]:
            deposit = 80.0 / max(item["objectives"]["score"], 1e-6)
            for idx in range(len(item["path"]) - 1):
                edge = (item["path"][idx], item["path"][idx + 1])
                pheromone[edge] = pheromone.get(edge, 1.0) + deposit

    unique = {}
    for item in candidates:
        path = item["path"]
        if not path or len(path) <= 1:
            continue
        key = tuple(path)
        old = unique.get(key)
        if old is None or item["objectives"]["score"] < old["objectives"]["score"]:
            unique[key] = item

    front = _pareto_rank(list(unique.values()))
    if not front:
        front = sorted(unique.values(), key=lambda item: item["objectives"]["score"])

    by_next = {}
    for item in front:
        next_hop = item["path"][1]
        old = by_next.get(next_hop)
        if old is None or item["objectives"]["score"] < old["objectives"]["score"]:
            by_next[next_hop] = item

    selected = sorted(by_next.values(), key=lambda item: item["objectives"]["score"])[:top_k]
    cache[cache_key] = selected
    return selected


def _allocate_iacoga_moves(G, source, candidates):
    people = float(G.nodes[source].get("people", 0.0))
    if people <= 0 or not candidates:
        return []
    weights = []
    for item in candidates:
        score = max(float(item["objectives"]["score"]), 1e-6)
        weights.append(1.0 / score)
    total = sum(weights)
    if total <= 0:
        return []

    moves = []
    for item, weight in zip(candidates, weights):
        nxt = item["path"][1]
        if not G.has_edge(source, nxt):
            continue
        requested = people * weight / total
        cap_step = float(G[source][nxt].get("capacity", 0.0)) * network.DELTA_T
        flow = min(requested, cap_step)
        if flow > 0:
            moves.append((source, nxt, flow))
    return moves


def iacoga_get_step_moves(original_get_step_moves, G, method, shortest_dists):
    # Update EMA in this standalone runner. The main program is unchanged.
    network._update_smoothed_approach_pressure(G)

    if method != IACOGA_METHOD:
        return original_get_step_moves(G, method, shortest_dists)

    active_nodes = [
        n for n in G.nodes()
        if G.nodes[n].get("people", 0) > 0.1 and G.nodes[n].get("type") != "exit"
    ]
    moves = []
    for node in active_nodes:
        candidates = _iacoga_candidate_paths(G, node, shortest_dists, top_k=3)
        moves.extend(_allocate_iacoga_moves(G, node, candidates))
    return network._integerize_moves(G, moves)


def _top_bottleneck_rows(metrics, scenario_mode, scenario_label, total_people, method_label, top_k=15):
    rows = []
    for node, stat in metrics.get("node_stats", {}).items():
        queue_seconds = float(stat.get("queue_seconds", 0.0))
        peak_people = float(stat.get("peak_people", 0.0))
        peak_index = float(stat.get("peak_congestion_index", 0.0))
        if queue_seconds <= 0 and peak_people <= 0 and peak_index <= 0:
            continue
        rows.append(
            {
                "scenario_mode": scenario_mode,
                "scenario_label": scenario_label,
                "total_people": total_people,
                "method": method_label,
                "node": node,
                "queue_person_seconds": queue_seconds,
                "peak_people": peak_people,
                "peak_congestion_index": peak_index,
                "peak_load_ratio": float(stat.get("peak_load_ratio", 0.0)),
                "peak_density": float(stat.get("peak_density", 0.0)),
            }
        )
    rows.sort(key=lambda row: (row["queue_person_seconds"], row["peak_congestion_index"]), reverse=True)
    return rows[:top_k]


def _summary_row(metrics, mode, scenario_label, total_people, method_label):
    return {
        "scenario_mode": mode,
        "scenario_label": scenario_label,
        "total_people": total_people,
        "method": method_label,
        "time": metrics["time"],
        "avg_travel_time": metrics.get("avg_travel_time", 0.0),
        "queueing_time": metrics["queueing_time"],
        "moderate_congestion_exposure_time": metrics.get("congestion_exposure_time", 0.0),
        "severe_congestion_exposure_time": metrics.get("severe_congestion_exposure_time", 0.0),
        "edge_congestion_exposure_time": metrics.get("edge_congestion_exposure_time", 0.0),
        "edge_severe_congestion_exposure_time": metrics.get("edge_severe_congestion_exposure_time", 0.0),
        "peak_density": metrics.get("peak_density", 0.0),
        "peak_congestion_index": metrics.get("peak_congestion_index", 0.0),
        "avg_speed": metrics.get("avg_speed", 0.0),
        "wall_clock_runtime_s": metrics.get("wall_clock_runtime_s", 0.0),
    }


def main():
    run_dir = Path("outputs") / (
        "group1_iacoga_mode1_mode4_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"RUN_DIR={run_dir.resolve()}", flush=True)
    print("NOTE=standalone IACO-GA-style strong baseline; main program files are unchanged", flush=True)
    print(f"CAPACITY_FACTOR={network.PATHFINDER_CAPACITY_CALIBRATION_FACTOR}", flush=True)

    original_get_step_moves = network.get_step_moves

    def patched_get_step_moves(G, method, shortest_dists):
        return iacoga_get_step_moves(original_get_step_moves, G, method, shortest_dists)

    network.get_step_moves = patched_get_step_moves

    summary_rows = []
    line_rows = []
    exit_rows = []
    bottleneck_rows = []

    try:
        for mode, scenario_label in SCENARIOS.items():
            pop, total_people = build_pop(mode)
            print(f"\nSCENARIO mode={mode} label={scenario_label} total={total_people}", flush=True)
            for method_label, method in METHODS:
                print(f"START {scenario_label} {method_label}", flush=True)
                graph = network.build_graph()
                metrics = network.run_simulation_for_metrics_timed(graph, pop, method=method)
                row = _summary_row(metrics, mode, scenario_label, total_people, method_label)
                summary_rows.append(row)
                print(
                    f"DONE {scenario_label} {method_label} "
                    f"time={row['time']:.1f}s "
                    f"avg_tt={row['avg_travel_time']:.2f}s "
                    f"queue={row['queueing_time']:.1f} "
                    f"moderate={row['moderate_congestion_exposure_time']:.1f} "
                    f"severe={row['severe_congestion_exposure_time']:.1f} "
                    f"peak_index={row['peak_congestion_index']:.3f} "
                    f"wall={row['wall_clock_runtime_s']:.2f}s",
                    flush=True,
                )

                pd.DataFrame(summary_rows).to_csv(
                    run_dir / "group1_method_summary_partial.csv",
                    index=False,
                    encoding="utf-8-sig",
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

                for exit_name, amount in sorted(metrics.get("exit_usage", {}).items()):
                    if amount <= 0:
                        continue
                    exit_rows.append(
                        {
                            "scenario_mode": mode,
                            "scenario_label": scenario_label,
                            "total_people": total_people,
                            "method": method_label,
                            "exit": exit_name,
                            "evacuated_people": amount,
                            "share": amount / total_people if total_people else 0.0,
                        }
                    )

                bottleneck_rows.extend(
                    _top_bottleneck_rows(metrics, mode, scenario_label, total_people, method_label)
                )

    finally:
        network.get_step_moves = original_get_step_moves

    pd.DataFrame(summary_rows).to_csv(
        run_dir / "group1_method_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(line_rows).to_csv(
        run_dir / "group1_line_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(exit_rows).to_csv(
        run_dir / "group1_exit_usage.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(bottleneck_rows).to_csv(
        run_dir / "group1_top_bottlenecks.csv",
        index=False,
        encoding="utf-8-sig",
    )

    summary = pd.DataFrame(summary_rows)
    improvement_rows = []
    for mode, scenario_label in SCENARIOS.items():
        sub = summary[summary["scenario_mode"] == mode].set_index("method")
        if "AdaptiveSingleNextHop" not in sub.index:
            continue
        adaptive = sub.loc["AdaptiveSingleNextHop"]
        for baseline_name in ["ImprovedAStar", "IACO_GA_2026"]:
            if baseline_name not in sub.index:
                continue
            baseline = sub.loc[baseline_name]
            row = {
                "scenario_mode": mode,
                "scenario_label": scenario_label,
                "baseline": baseline_name,
                "total_people": int(adaptive["total_people"]),
            }
            for metric in [
                "time",
                "avg_travel_time",
                "queueing_time",
                "moderate_congestion_exposure_time",
                "severe_congestion_exposure_time",
                "peak_congestion_index",
            ]:
                base_value = float(baseline[metric])
                adaptive_value = float(adaptive[metric])
                row[f"{metric}_baseline"] = base_value
                row[f"{metric}_adaptive"] = adaptive_value
                row[f"{metric}_delta"] = adaptive_value - base_value
                row[f"{metric}_improvement_pct"] = (
                    (base_value - adaptive_value) / base_value * 100.0
                    if abs(base_value) > 1e-9
                    else 0.0
                )
            improvement_rows.append(row)

    pd.DataFrame(improvement_rows).to_csv(
        run_dir / "group1_adaptive_improvement_vs_baselines.csv",
        index=False,
        encoding="utf-8-sig",
    )
    print(f"\nSAVED {run_dir.resolve()}", flush=True)


if __name__ == "__main__":
    main()
