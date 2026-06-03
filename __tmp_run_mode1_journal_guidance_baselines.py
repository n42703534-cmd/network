from __future__ import annotations

import copy
import math
import time
from dataclasses import dataclass
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

MODE1_LABEL = "mode1_regular_emergency"
WEIGHT_KEY = "_journal_guidance_weight"

SUE_METHOD = "JournalSUE_LogitEquilibrium"
NSGA_METHOD = "JournalNSGAII_MultiObjective"
SIGN_METHOD = "JournalDynamicSign_FlowEquilibrium"

METHODS = [
    ("SUE_LogitEquilibrium", SUE_METHOD),
    ("NSGAII_MultiObjective", NSGA_METHOD),
    ("DynamicSign_FlowEquilibrium", SIGN_METHOD),
]


def build_mode1_pop():
    pop = {}
    total = 0
    for line, physics in network.TRAIN_PHYSICS.items():
        base = BASE_LOADS[line]
        pop[line] = {
            "train_1": 0,
            "train_2": 0,
            "platform_waiting": int(base["platform_waiting"]),
            "hall_people": int(base["hall_people"]),
            "transfer_people": int(base["transfer_people"]),
        }
        total += sum(pop[line].values())
    return pop, total


def _safe_node_congestion(G, node):
    if node not in G.nodes:
        return 0.0
    try:
        value, _ = network._node_congestion_index(G, node)
        return max(float(value), 0.0)
    except Exception:
        return 0.0


def _service_queue_ratio(G, node):
    if node not in G.nodes:
        return 0.0
    if not network.spr.is_capacity_service_node(G, node):
        return 0.0
    people = float(G.nodes[node].get("people", 0.0))
    cap = network.spr.node_service_capacity(G, node) * network.spr.SERVICE_QUEUE_HORIZON_SECONDS
    return people / max(cap, 0.001)


def _edge_approach_pressure(G, u, v):
    pressure = 0.0
    if v not in G.nodes:
        return 0.0
    for succ in G.successors(v):
        if G.nodes[succ].get("type") == "exit":
            pressure = max(pressure, float(network.spr.smoothed_approach_pressure(G, v, succ)))
    return pressure


def _exit_running_pressure(G, exit_node):
    if exit_node is None or exit_node not in G.nodes:
        return 0.0
    usage = float(G.graph.setdefault("_journal_exit_choice_counts", {}).get(exit_node, 0.0))
    pred_capacity = 0.0
    for pred in G.predecessors(exit_node):
        if G.has_edge(pred, exit_node):
            pred_capacity += float(G[pred][exit_node].get("capacity", 0.0))
    return usage / max(pred_capacity * 120.0, 1.0)


def _edge_generalized_cost(G, u, v, method):
    if not G.has_edge(u, v):
        return float("inf")

    travel_time = float(network._edge_travel_time(G, u, v))
    node_cong = _safe_node_congestion(G, v)
    queue_ratio = _service_queue_ratio(G, v)
    approach = _edge_approach_pressure(G, u, v)

    if method == SUE_METHOD:
        return travel_time * (1.0 + 0.25 * node_cong) + 5.0 * queue_ratio + 2.0 * approach

    if method == NSGA_METHOD:
        return travel_time * (1.0 + 0.15 * node_cong) + 3.0 * queue_ratio + 1.5 * approach

    if method == SIGN_METHOD:
        return travel_time * (1.0 + 0.20 * node_cong) + 4.0 * queue_ratio + 3.0 * approach

    return travel_time


@dataclass
class RoutingContext:
    G: object
    method: str
    distances: dict
    reverse_paths: dict


def _build_routing_context(G, method):
    network._update_smoothed_approach_pressure(G)

    for u, v in G.edges():
        G[u][v][WEIGHT_KEY] = _edge_generalized_cost(G, u, v, method)

    exits = [n for n, d in G.nodes(data=True) if d.get("type") == "exit"]
    reverse_graph = G.reverse(copy=False)
    try:
        distances, reverse_paths = nx.multi_source_dijkstra(
            reverse_graph,
            exits,
            weight=WEIGHT_KEY,
        )
    except Exception:
        distances, reverse_paths = {}, {}

    return RoutingContext(G=G, method=method, distances=distances, reverse_paths=reverse_paths)


def _candidate_successors(ctx, node):
    G = ctx.G
    rows = []
    for succ in G.successors(node):
        if not G.has_edge(node, succ):
            continue
        edge_cap = float(G[node][succ].get("capacity", 0.0))
        if edge_cap <= 0:
            continue
        edge_cost = float(G[node][succ].get(WEIGHT_KEY, float("inf")))
        downstream = float(ctx.distances.get(succ, float("inf")))
        if not math.isfinite(edge_cost) or not math.isfinite(downstream):
            continue

        reverse_path = ctx.reverse_paths.get(succ, [])
        target_exit = reverse_path[0] if reverse_path else (succ if G.nodes[succ].get("type") == "exit" else None)
        total_cost = edge_cost + downstream
        node_cong = _safe_node_congestion(G, succ)
        queue_ratio = _service_queue_ratio(G, succ)
        approach = _edge_approach_pressure(G, node, succ)
        exit_pressure = _exit_running_pressure(G, target_exit)

        rows.append(
            {
                "next_hop": succ,
                "target": target_exit,
                "cost": total_cost,
                "travel": total_cost,
                "congestion": node_cong + 2.0 * queue_ratio,
                "approach": approach,
                "exit_pressure": exit_pressure,
                "capacity": edge_cap,
            }
        )

    rows.sort(key=lambda item: item["cost"])
    return rows


def _allocate_by_weights(G, node, candidates, weights):
    people = float(G.nodes[node].get("people", 0.0))
    if people <= 0 or not candidates:
        return []

    total_weight = sum(max(float(w), 0.0) for w in weights)
    if total_weight <= 0:
        weights = [1.0 if i == 0 else 0.0 for i in range(len(candidates))]
        total_weight = 1.0

    moves = []
    for item, weight in zip(candidates, weights):
        share = max(float(weight), 0.0) / total_weight
        amount = people * share
        cap_step = float(G[node][item["next_hop"]].get("capacity", 0.0)) * network.DELTA_T
        flow = min(amount, cap_step)
        if flow > 0:
            moves.append((node, item["next_hop"], flow))
            if item.get("target"):
                counts = G.graph.setdefault("_journal_exit_choice_counts", {})
                counts[item["target"]] = counts.get(item["target"], 0.0) + flow
    return moves


def _sue_moves_for_node(ctx, node):
    candidates = _candidate_successors(ctx, node)
    if not candidates:
        return []

    best = float(candidates[0]["cost"])
    viable = [
        item for item in candidates[:6]
        if item["cost"] <= best * 1.35 or item["cost"] <= best + 12.0
    ]
    if not viable:
        viable = candidates[:1]

    scale = max(best, 1.0)
    theta = 3.0
    weights = [
        math.exp(-theta * (float(item["cost"]) - best) / scale)
        for item in viable
    ]
    return _allocate_by_weights(ctx.G, node, viable, weights)


def _dominates(a, b):
    a_obj = (a["travel"], a["congestion"], a["approach"] + a["exit_pressure"])
    b_obj = (b["travel"], b["congestion"], b["approach"] + b["exit_pressure"])
    return all(x <= y + 1e-9 for x, y in zip(a_obj, b_obj)) and any(x < y - 1e-9 for x, y in zip(a_obj, b_obj))


def _pareto_front(candidates):
    front = []
    for item in candidates:
        if not any(_dominates(other, item) for other in candidates if other is not item):
            front.append(item)
    front.sort(key=lambda x: (x["travel"], x["congestion"], x["approach"] + x["exit_pressure"]))
    return front


def _nsga_moves_for_node(ctx, node):
    candidates = _candidate_successors(ctx, node)
    if not candidates:
        return []

    pool = candidates[:8]
    front = _pareto_front(pool)
    if not front:
        front = pool[:1]

    # NSGA-II-style screening: keep a diverse Pareto front but favor low
    # normalized aggregate objective when allocating people.
    front = front[:4]
    min_travel = min(item["travel"] for item in front)
    max_travel = max(item["travel"] for item in front)
    min_cong = min(item["congestion"] for item in front)
    max_cong = max(item["congestion"] for item in front)
    min_press = min(item["approach"] + item["exit_pressure"] for item in front)
    max_press = max(item["approach"] + item["exit_pressure"] for item in front)

    def norm(value, lo, hi):
        return 0.0 if hi <= lo + 1e-9 else (value - lo) / (hi - lo)

    scores = []
    for item in front:
        pressure = item["approach"] + item["exit_pressure"]
        score = (
            0.45 * norm(item["travel"], min_travel, max_travel)
            + 0.35 * norm(item["congestion"], min_cong, max_cong)
            + 0.20 * norm(pressure, min_press, max_press)
        )
        scores.append(score)

    weights = [1.0 / (0.20 + score) for score in scores]
    return _allocate_by_weights(ctx.G, node, front, weights)


def _sign_recommendation(ctx, node):
    G = ctx.G
    current_time = float(G.graph.get("_sim_time", 0.0))
    sign_map = G.graph.setdefault("_journal_sign_next", {})
    sign_cost = G.graph.setdefault("_journal_sign_cost", {})
    last_update = float(G.graph.get("_journal_sign_last_update", -9999.0))
    update_interval = 20.0

    must_update = current_time - last_update >= update_interval - 1e-9
    prev = sign_map.get(node)
    if not must_update and prev and G.has_edge(node, prev):
        return prev

    candidates = _candidate_successors(ctx, node)
    if not candidates:
        return None

    scored = []
    for item in candidates[:6]:
        switch_penalty = 0.0
        if prev and item["next_hop"] != prev:
            old_cost = float(sign_cost.get(node, item["cost"]))
            if item["cost"] > old_cost * 0.92:
                switch_penalty = 4.0
        equilibrium_penalty = 10.0 * item["exit_pressure"]
        score = item["cost"] + equilibrium_penalty + switch_penalty
        scored.append((score, item))

    scored.sort(key=lambda x: x[0])
    chosen = scored[0][1]
    sign_map[node] = chosen["next_hop"]
    sign_cost[node] = chosen["cost"]
    return chosen["next_hop"]


def _sign_moves_for_node(ctx, node):
    G = ctx.G
    succ = _sign_recommendation(ctx, node)
    if not succ or not G.has_edge(node, succ):
        return []
    people = float(G.nodes[node].get("people", 0.0))
    cap_step = float(G[node][succ].get("capacity", 0.0)) * network.DELTA_T
    flow = min(people, cap_step)
    return [(node, succ, flow)] if flow > 0 else []


def journal_get_step_moves(original_get_step_moves, G, method, shortest_dists):
    if method not in {SUE_METHOD, NSGA_METHOD, SIGN_METHOD}:
        return original_get_step_moves(G, method, shortest_dists)

    if method == SIGN_METHOD:
        current_time = float(G.graph.get("_sim_time", 0.0))
        last_update = float(G.graph.get("_journal_sign_last_update", -9999.0))
        if current_time - last_update >= 20.0 - 1e-9:
            G.graph["_journal_sign_last_update"] = current_time

    active_nodes = [
        n for n in G.nodes()
        if G.nodes[n].get("people", 0) > 0.1 and G.nodes[n].get("type") != "exit"
    ]
    ctx = _build_routing_context(G, method)

    moves = []
    for node in active_nodes:
        if method == SUE_METHOD:
            moves.extend(_sue_moves_for_node(ctx, node))
        elif method == NSGA_METHOD:
            moves.extend(_nsga_moves_for_node(ctx, node))
        elif method == SIGN_METHOD:
            moves.extend(_sign_moves_for_node(ctx, node))

    return network._integerize_moves(G, moves)


def top_bottleneck_rows(metrics, method_label, top_k=12):
    rows = []
    for node, stat in metrics.get("node_stats", {}).items():
        queue_seconds = float(stat.get("queue_seconds", 0.0))
        peak_people = float(stat.get("peak_people", 0.0))
        peak_index = float(stat.get("peak_congestion_index", 0.0))
        if queue_seconds <= 0 and peak_people <= 0 and peak_index <= 0:
            continue
        rows.append(
            {
                "method": method_label,
                "node": node,
                "queue_person_seconds": queue_seconds,
                "peak_people": peak_people,
                "peak_congestion_index": peak_index,
                "peak_load_ratio": float(stat.get("peak_load_ratio", 0.0)),
                "peak_density": float(stat.get("peak_density", 0.0)),
            }
        )
    rows.sort(key=lambda r: (r["queue_person_seconds"], r["peak_congestion_index"]), reverse=True)
    return rows[:top_k]


def summarize_metrics(metrics, method_label, total_people, wall_clock):
    return {
        "scenario_mode": 1,
        "scenario_label": MODE1_LABEL,
        "total_people": total_people,
        "method": method_label,
        "time": metrics["time"],
        "avg_travel_time": metrics.get("avg_travel_time", 0.0),
        "queueing_time": metrics["queueing_time"],
        "moderate_congestion_exposure_time": metrics.get("congestion_exposure_time", 0.0),
        "severe_congestion_exposure_time": metrics.get("severe_congestion_exposure_time", 0.0),
        "peak_density": metrics.get("peak_density", 0.0),
        "peak_congestion_index": metrics.get("peak_congestion_index", 0.0),
        "avg_speed": metrics.get("avg_speed", 0.0),
        "wall_clock_runtime_s": wall_clock,
    }


def main():
    run_dir = Path("outputs") / (
        "mode1_journal_guidance_baselines_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"RUN_DIR={run_dir.resolve()}", flush=True)

    pop, total_people = build_mode1_pop()
    print(f"SCENARIO mode=1 label={MODE1_LABEL} total={total_people}", flush=True)
    print("NOTE=standalone screening implementations; main program files are unchanged", flush=True)

    original_get_step_moves = network.get_step_moves

    def patched_get_step_moves(G, method, shortest_dists):
        return journal_get_step_moves(original_get_step_moves, G, method, shortest_dists)

    network.get_step_moves = patched_get_step_moves

    summary_rows = []
    line_rows = []
    exit_rows = []
    bottleneck_rows = []

    try:
        for method_label, method in METHODS:
            print(f"START {method_label}", flush=True)
            graph = network.build_graph()
            start = time.perf_counter()
            metrics = network.run_simulation_for_metrics(graph, pop, method=method)
            wall_clock = time.perf_counter() - start

            row = summarize_metrics(metrics, method_label, total_people, wall_clock)
            summary_rows.append(row)

            print(
                f"DONE {method_label} "
                f"time={row['time']:.1f}s "
                f"queue={row['queueing_time']:.1f} "
                f"moderate={row['moderate_congestion_exposure_time']:.1f} "
                f"severe={row['severe_congestion_exposure_time']:.1f} "
                f"peak_index={row['peak_congestion_index']:.3f} "
                f"wall={wall_clock:.2f}s",
                flush=True,
            )

            for line in network.TRAIN_PHYSICS:
                line_rows.append(
                    {
                        "scenario_mode": 1,
                        "scenario_label": MODE1_LABEL,
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
                        "scenario_mode": 1,
                        "scenario_label": MODE1_LABEL,
                        "total_people": total_people,
                        "method": method_label,
                        "exit": exit_name,
                        "evacuated_people": amount,
                        "share": amount / total_people if total_people else 0.0,
                    }
                )

            bottleneck_rows.extend(top_bottleneck_rows(metrics, method_label))

            pd.DataFrame(summary_rows).to_csv(
                run_dir / "mode1_journal_guidance_method_summary_partial.csv",
                index=False,
                encoding="utf-8-sig",
            )

    finally:
        network.get_step_moves = original_get_step_moves

    pd.DataFrame(summary_rows).to_csv(
        run_dir / "mode1_journal_guidance_method_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(line_rows).to_csv(
        run_dir / "mode1_journal_guidance_line_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(exit_rows).to_csv(
        run_dir / "mode1_journal_guidance_exit_usage.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(bottleneck_rows).to_csv(
        run_dir / "mode1_journal_guidance_top_bottlenecks.csv",
        index=False,
        encoding="utf-8-sig",
    )

    print(f"SAVED {run_dir.resolve()}", flush=True)


if __name__ == "__main__":
    main()
