import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import random
import numpy as np
import platform
import copy
import statistics
import os
import pandas as pd
import math
import sys
import time

from calc_platform_dists import PATHFINDER_CONFIG
import single_path_routing as spr
import split_guidance as split_router


def _span_from_train_cfg(train_cfg):
    return {
        "start": train_cfg["start_pos"],
        "end": train_cfg["end_pos"],
    }


def _mid_span(train_a, train_b):
    return {
        "start": (
            (train_a["start_pos"][0] + train_b["start_pos"][0]) / 2.0,
            (train_a["start_pos"][1] + train_b["start_pos"][1]) / 2.0,
        ),
        "end": (
            (train_a["end_pos"][0] + train_b["end_pos"][0]) / 2.0,
            (train_a["end_pos"][1] + train_b["end_pos"][1]) / 2.0,
        ),
    }


def _span_mean_y(span):
    start = span.get("start")
    end = span.get("end")
    if not start or not end:
        return 0.0
    return (start[1] + end[1]) / 2.0


def _maglev_band_spans_by_train():
    train_cfgs = PATHFINDER_CONFIG.get("Maglev", {}).get("trains", [])
    if len(train_cfgs) < 4:
        return {}

    train_1_spans = [_span_from_train_cfg(train_cfgs[0]), _span_from_train_cfg(train_cfgs[1])]
    train_2_spans = [_span_from_train_cfg(train_cfgs[2]), _span_from_train_cfg(train_cfgs[3])]

    train_1_spans.sort(key=_span_mean_y, reverse=True)
    train_2_spans.sort(key=_span_mean_y, reverse=True)

    return {
        1: {
            "upper": train_1_spans[0],
            "middle": train_1_spans[1],
        },
        2: {
            "middle": train_2_spans[0],
            "lower": train_2_spans[1],
        },
    }


def _train_total_people(physics):
    if "train_people" in physics:
        return float(physics["train_people"])
    return float(physics["car_people"]) * float(physics["cars"])


def _car_people_from_physics(physics):
    return _train_total_people(physics) / max(float(physics["cars"]), 1.0)


def _interp_point(start, end, ratio):
    return (
        start[0] + (end[0] - start[0]) * ratio,
        start[1] + (end[1] - start[1]) * ratio,
    )


def _layout_point_from_span(train_span, car_idx, door_idx, car_count, door_count, fallback_pos):
    """
    train_span: 该列车的轴线 start/end
    car_idx:    第几节车厢
    door_idx:   0 表示车厢中心；1..door_count 表示车门
    """
    if not train_span or not train_span.get("start") or not train_span.get("end"):
        return fallback_pos

    start = train_span["start"]
    end = train_span["end"]

    car_start = _interp_point(start, end, (car_idx - 1) / car_count)
    car_end = _interp_point(start, end, car_idx / car_count)

    if door_idx == 0:
        return _interp_point(car_start, car_end, 0.5)

    return _interp_point(car_start, car_end, door_idx / (door_count + 1))
def _sorted_train_car_nodes(G, line_id, train_idx):
    prefix = f"Train_{line_id}_{train_idx}_Car"
    nodes = [
        n for n, d in G.nodes(data=True)
        if d.get("type") == "train_car" and n.startswith(prefix)
    ]

    def sort_key(name):
        car_idx = 0
        for part in name.split("_"):
            if part.startswith("Car"):
                try:
                    car_idx = int(part[3:])
                except ValueError:
                    car_idx = 0
        return (car_idx, name)

    return sorted(nodes, key=sort_key)


TRADITIONAL_METHOD = spr.TRADITIONAL_METHOD
PAPER_SINGLE_PATH_METHOD = spr.PAPER_SINGLE_PATH_METHOD
OUR_SINGLE_PATH_METHOD = spr.OUR_SINGLE_PATH_METHOD
OUR_SPLIT_GUIDANCE_METHOD = spr.OUR_SPLIT_GUIDANCE_METHOD
ANT_COLONY_METHOD = spr.ANT_COLONY_METHOD
METHOD_ALIASES = spr.METHOD_ALIASES

METHOD_DISPLAY_NAMES = {
    TRADITIONAL_METHOD: "Traditional",
    PAPER_SINGLE_PATH_METHOD: "ImprovedAStar",
    OUR_SINGLE_PATH_METHOD: "OurSinglePath",
    OUR_SPLIT_GUIDANCE_METHOD: "Our Split Guidance",
    ANT_COLONY_METHOD: "ACO",
}

METHOD_OUTPUT_TAGS = {
    TRADITIONAL_METHOD: "traditional",
    PAPER_SINGLE_PATH_METHOD: "improved_astar",
    OUR_SINGLE_PATH_METHOD: "our_single_path",
    OUR_SPLIT_GUIDANCE_METHOD: "our_split_guidance",
    ANT_COLONY_METHOD: "aco",
}

OUR_GUIDANCE_MIN_HOLD_SECONDS = 4.0
OUR_GUIDANCE_SWITCH_MARGIN = 0.08
OUR_GUIDANCE_FORCE_SWITCH_MARGIN = 0.20

SINGLE_PATH_CASE_POPULATION = 100.0
SINGLE_PATH_CASE_SPECS = [
    {"case_id": "L2_C1", "line": "L2", "origin": "Platform_L2", "start_role": "platform"},
    {"case_id": "L2_C2", "line": "L2", "origin": "Stair_L2_1", "start_role": "stair_a"},
    {"case_id": "L2_C3", "line": "L2", "origin": "Stair_L2_3", "start_role": "stair_b"},
    {"case_id": "L2_C4", "line": "L2", "origin": "Escalator_L2_up1", "start_role": "escalator"},
    {"case_id": "L7_C1", "line": "L7", "origin": "Platform_L7", "start_role": "platform"},
    {"case_id": "L7_C2", "line": "L7", "origin": "Stair_L7_1", "start_role": "stair_a"},
    {"case_id": "L7_C3", "line": "L7", "origin": "Stair_L7_2", "start_role": "stair_b"},
    {"case_id": "L7_C4", "line": "L7", "origin": "Escalator_L7_up1", "start_role": "escalator"},
    {"case_id": "L18_C1", "line": "L18", "origin": "Platform_L18", "start_role": "platform"},
    {"case_id": "L18_C2", "line": "L18", "origin": "Stair_L18_1", "start_role": "stair_a"},
    {"case_id": "L18_C3", "line": "L18", "origin": "Stair_L18_2", "start_role": "stair_b"},
    {"case_id": "L18_C4", "line": "L18", "origin": "Escalator_L18_down3", "start_role": "escalator"},
]


def _normalize_method(method):
    return spr.normalize_method(method)


def _method_display_name(method):
    return METHOD_DISPLAY_NAMES.get(_normalize_method(method), _normalize_method(method))


def _method_output_tag(method):
    return METHOD_OUTPUT_TAGS.get(_normalize_method(method), _normalize_method(method).lower())


def _routing_base_method(method):
    return spr.routing_base_method(method)


def _uses_dynamic_a_star(method):
    return spr.uses_dynamic_a_star(method)


def _uses_multi_split(method):
    return _normalize_method(method) == OUR_SPLIT_GUIDANCE_METHOD


def _uses_paper_single_path(method):
    return _routing_base_method(method) == PAPER_SINGLE_PATH_METHOD


def _uses_predictive_single_path(method):
    return spr.uses_predictive_single_path(method)


def _uses_ant_colony(method):
    return spr.uses_ant_colony(method)


def _is_key_facility_node(node_name, node_data):
    node_type = str(node_data.get("type", "")).lower()
    name = str(node_name)
    if name.startswith("VN_") or node_type == "virtual":
        return False
    if node_type in {"platform", "platform_waiting_zone", "exit"}:
        return False
    if "exit" in name.lower() and node_type in {"escalator", "stair"}:
        return False
    return node_type in {"gate", "escalator", "stair", "transfer"}


def _select_key_facility_nodes(G_base, method_metrics, top_k=8):
    candidates = []
    for node, data in G_base.nodes(data=True):
        if not _is_key_facility_node(node, data):
            continue
        total_queue_seconds = 0.0
        max_peak_density = 0.0
        for _, metrics in method_metrics:
            stat = metrics.get("node_stats", {}).get(node, {})
            total_queue_seconds += float(stat.get("queue_seconds", 0.0))
            max_peak_density = max(max_peak_density, float(stat.get("peak_density", 0.0)))
        if total_queue_seconds <= 0.0 and max_peak_density <= 0.0:
            continue
        candidates.append((total_queue_seconds, max_peak_density, node))

    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return [node for _, _, node in candidates[:top_k]]


def _heuristic_cost(u, v, d_dict, method):
    return spr.heuristic_cost(u, v, d_dict, method)


def _node_out_capacity(G, node):
    return spr.node_out_capacity(G, node)


def _exit_approach_pressure(G, exit_node):
    return spr.exit_approach_pressure(G, exit_node)


def _path_total_cost(G, path, method, weight_key="sim_weight"):
    if not path or len(path) <= 1:
        return float("inf")

    total = 0.0
    for idx in range(len(path) - 1):
        u = path[idx]
        v = path[idx + 1]
        if not G.has_edge(u, v):
            return float("inf")
        edge_cost = float(G[u][v].get(weight_key, float("inf")))
        if not math.isfinite(edge_cost):
            return float("inf")
        total += edge_cost

    if _routing_base_method(method) == OUR_SINGLE_PATH_METHOD:
        total += 0.20 * _exit_approach_pressure(G, path[-1])
    return total


def _our_path_is_usable(G, current_node, path):
    if not path or len(path) <= 1 or path[0] != current_node:
        return False
    for idx in range(len(path) - 1):
        if not G.has_edge(path[idx], path[idx + 1]):
            return False
    return True


def _edge_dynamic_cost(G, u, v, method):
    return spr.edge_dynamic_cost(G, u, v, method, fruin_speed)


def update_dynamic_weights(G, method):
    spr.update_dynamic_weights(G, method, fruin_speed)


def get_split_next_moves(
    G,
    current_node,
    method,
    shortest_dists,
    score_ratio=1.15,
    score_slack=2.0,
    min_split_share=0.05,
):
    return split_router.get_split_next_moves(
        G,
        current_node,
        method,
        shortest_dists,
        fruin_speed,
        DELTA_T,
        score_ratio=score_ratio,
        score_slack=score_slack,
        min_split_share=min_split_share,
    )


def _choose_our_single_path_with_inertia(G, current_node, shortest_dists):
    candidates = spr.enumerate_exit_paths(
        G,
        current_node,
        OUR_SINGLE_PATH_METHOD,
        shortest_dists,
        fruin_speed,
    )
    if not candidates:
        return None

    best = candidates[0]
    guidance_state = G.graph.setdefault("_our_guidance_state", {})
    sim_time = float(G.graph.get("_sim_time", 0.0))
    prev = guidance_state.get(current_node)

    chosen = best
    switched_at = sim_time

    if prev and _our_path_is_usable(G, current_node, prev.get("path")):
        prev_path = prev["path"]
        prev_cost = _path_total_cost(G, prev_path, OUR_SINGLE_PATH_METHOD)
        best_cost = float(best["cost"])
        prev_next = prev.get("next_hop")
        best_next = best.get("next_hop")
        held_for = sim_time - float(prev.get("switched_at", sim_time))

        if best_next == prev_next:
            switched_at = float(prev.get("switched_at", sim_time))
        elif math.isfinite(prev_cost):
            clearly_better = best_cost <= prev_cost * (1.0 - OUR_GUIDANCE_SWITCH_MARGIN)
            force_switch = best_cost <= prev_cost * (1.0 - OUR_GUIDANCE_FORCE_SWITCH_MARGIN)
            if (held_for < OUR_GUIDANCE_MIN_HOLD_SECONDS and not force_switch) or (
                not clearly_better and not force_switch
            ):
                chosen = {
                    "target": prev_path[-1],
                    "path": prev_path,
                    "next_hop": prev_next,
                    "cost": prev_cost,
                }
                switched_at = float(prev.get("switched_at", sim_time))

    guidance_state[current_node] = {
        "path": chosen["path"],
        "next_hop": chosen["next_hop"],
        "switched_at": switched_at,
    }
    return chosen["path"]


import random

def standard_aco_pathfinder(G, source_node, shortest_dists, fruin_speed_func, alpha=1.0, beta=2.0, rho=0.1, Q=100.0,
                            num_ants=5, max_iter=10):
    """标准的蚁群算法路径规划"""
    if "_aco_pheromones" not in G.graph:
        G.graph["_aco_pheromones"] = {edge: 1.0 for edge in G.edges()}
    pheromones = G.graph["_aco_pheromones"]

    best_path = None
    best_cost = float('inf')
    exits = {n for n, d in G.nodes(data=True) if d.get("type") == "exit"}
    if not exits: return [source_node]

    for iteration in range(max_iter):
        ant_paths = []
        for ant in range(num_ants):
            path = [source_node]
            current = source_node
            visited = {source_node}
            path_cost = 0.0

            while current not in exits:
                neighbors = [v for v in G.successors(current) if v not in visited]
                if not neighbors: break

                probabilities = []
                for v in neighbors:
                    length = float(G[current][v].get("length", 1.0))
                    density = float(G.nodes[current].get("people", 0)) / max(float(G.nodes[current].get("area", 1.0)),
                                                                             0.001)
                    speed = fruin_speed_func(density)
                    edge_cost = length / speed if speed > 0 else float('inf')
                    eta = 1.0 / max(edge_cost, 0.01)
                    tau = pheromones.get((current, v), 1.0)
                    prob = (tau ** alpha) * (eta ** beta)
                    probabilities.append((v, prob, edge_cost))

                total_prob = sum(p[1] for p in probabilities)
                if total_prob <= 0: break

                rand_val = random.uniform(0, total_prob)
                cumulative = 0.0
                chosen_next, chosen_cost = neighbors[0], probabilities[0][2]

                for v, prob, cost in probabilities:
                    cumulative += prob
                    if rand_val <= cumulative:
                        chosen_next = v
                        chosen_cost = cost
                        break

                path.append(chosen_next)
                visited.add(chosen_next)
                path_cost += chosen_cost
                current = chosen_next

            if current in exits:
                ant_paths.append((path, path_cost))
                if path_cost < best_cost:
                    best_cost = path_cost
                    best_path = path

        for edge in pheromones:
            pheromones[edge] = max(pheromones[edge] * (1.0 - rho), 0.01)
        for p, cost in ant_paths:
            delta_tau = Q / max(cost, 0.01)
            for i in range(len(p) - 1):
                edge = (p[i], p[i + 1])
                if edge in pheromones: pheromones[edge] += delta_tau

    return best_path if best_path else [source_node]


def get_step_moves(G, method, shortest_dists):
    method = _normalize_method(method)
    active_nodes = [
        n for n in G.nodes()
        if G.nodes[n].get("people", 0) > 0.1 and G.nodes[n].get("type") != "exit"
    ]

    moves = []

    # 封印解除：这段被注释掉，不再允许用 fixed_next 直接查表跳过计算
    # fixed_next = G.graph.get("_fixed_next_by_node")
    # if fixed_next: ...

    if method == PAPER_SINGLE_PATH_METHOD:
        return _get_paper_step_moves(G, active_nodes)

    if method in {TRADITIONAL_METHOD, PAPER_SINGLE_PATH_METHOD, ANT_COLONY_METHOD, OUR_SINGLE_PATH_METHOD}:
        if method == OUR_SINGLE_PATH_METHOD:
            guidance_state = G.graph.setdefault("_our_guidance_state", {})
            for node in list(guidance_state):
                if node not in active_nodes:
                    guidance_state.pop(node, None)

        for u in active_nodes:
            # 核心修改：如果是 ACO，调用我们刚刚写好的真正动态 ACO 函数
            if method == OUR_SINGLE_PATH_METHOD:
                path = _choose_our_single_path_with_inertia(G, u, shortest_dists)
            elif method == ANT_COLONY_METHOD:
                path = standard_aco_pathfinder(G, u, shortest_dists, fruin_speed)
            else:
                path = get_best_path_to_exit(G, u, method, shortest_dists)

            if path and len(path) > 1:
                v = path[1]
                flow = min(float(G.nodes[u]["people"]), float(G[u][v]["capacity"]) * DELTA_T)
                if flow > 0:
                    moves.append((u, v, flow))
        return _integerize_moves(G, moves)

    update_dynamic_weights(G, method)
    for u in active_nodes:
        moves.extend(get_split_next_moves(G, u, method, shortest_dists))

    return _integerize_moves(G, moves)


def _node_density(G, node):
    people = float(G.nodes[node].get("people", 0.0))
    area = max(float(G.nodes[node].get("area", 1.0)), 0.001)
    return people / area


def _paper_congested_nodes(G):
    blocked = set()
    for node, data in G.nodes(data=True):
        if data.get("type") == "exit":
            continue
        if _node_density(G, node) > spr.PAPER_DENSITY_CUTOFF:
            blocked.add(node)
    return blocked


def _paper_build_routing_graph(G, current_node, blocked_nodes):
    removable = {node for node in blocked_nodes if node != current_node and node in G.nodes}
    if not removable:
        return G
    H = G.copy()
    H.remove_nodes_from(removable)
    return H


def _paper_plan_path(G, current_node, blocked_nodes):
    routing_graph = _paper_build_routing_graph(G, current_node, blocked_nodes)
    local_shortest = dict(nx.all_pairs_dijkstra_path_length(routing_graph, weight="length"))
    path = spr.get_best_path_to_exit(
        routing_graph,
        current_node,
        PAPER_SINGLE_PATH_METHOD,
        local_shortest,
        fruin_speed,
    )
    if path or routing_graph is G:
        return path

    fallback_shortest = dict(nx.all_pairs_dijkstra_path_length(G, weight="length"))
    return spr.get_best_path_to_exit(
        G,
        current_node,
        PAPER_SINGLE_PATH_METHOD,
        fallback_shortest,
        fruin_speed,
    )


def _paper_path_blocked(path, blocked_nodes):
    if not path:
        return True
    for node in path[1:]:
        if node in blocked_nodes:
            return True
    return False


def _get_paper_step_moves(G, active_nodes):
    moves = []
    blocked_nodes = _paper_congested_nodes(G)
    blocked_signature = tuple(sorted(blocked_nodes))

    cached_signature = G.graph.get("_paper_blocked_signature")
    paper_paths = G.graph.setdefault("_paper_path_by_node", {})
    paper_next = G.graph.setdefault("_paper_fixed_next_by_node", {})

    if cached_signature != blocked_signature:
        paper_paths.clear()
        paper_next.clear()
        G.graph["_paper_blocked_signature"] = blocked_signature

    for u in active_nodes:
        path = paper_paths.get(u)
        if _paper_path_blocked(path, blocked_nodes):
            path = _paper_plan_path(G, u, blocked_nodes)
            if not path or len(path) <= 1:
                continue
            for idx, node in enumerate(path[:-1]):
                paper_next[node] = path[idx + 1]
                paper_paths[node] = path[idx:]

        v = paper_next.get(u)
        if v and G.has_edge(u, v):
            flow = min(float(G.nodes[u]["people"]), float(G[u][v]["capacity"]) * DELTA_T)
            if flow > 0:
                moves.append((u, v, flow))

    return _integerize_moves(G, moves)


def _ensure_transit_state(G):
    if "_sim_time" not in G.graph:
        G.graph["_sim_time"] = 0.0
    if "_transit_queue" not in G.graph:
        G.graph["_transit_queue"] = []
    return G.graph["_sim_time"], G.graph["_transit_queue"]


def _edge_travel_time(G, u, v):
    data = G[u][v]
    length = max(float(data.get("length", 0.0)), 0.0)
    speed = 1.4
    travel_time = length / speed if speed > 0 else length
    return max(1.0, travel_time)


def _process_transit_arrivals(
    G,
    current_time,
    evacuated_by_line=None,
    exit_usage_dict=None,
    exit_usage_by_source_group=None,
):
    transit_queue = G.graph.setdefault("_transit_queue", [])
    if not transit_queue:
        return 0.0

    remaining = []
    evac_total = 0.0

    for item in transit_queue:
        if item["arrive_time"] > current_time + 1e-9:
            remaining.append(item)
            continue

        dest = item.get("dest", item.get("v"))
        if dest is None or dest not in G.nodes:
            continue
        amount = item["amount"]
        line_shares = item["line_shares"]
        source_group_shares = item.get("source_group_shares", {})
        dest_type = G.nodes[dest].get("type", "")

        for line_id, flow in line_shares.items():
            if flow <= 0:
                continue

            G.nodes[dest]["people_dict"][line_id] += flow

            if dest_type == "exit":
                if evacuated_by_line is not None:
                    evacuated_by_line[line_id] += flow
                if exit_usage_dict is not None and dest in exit_usage_dict:
                    exit_usage_dict[dest][line_id] += flow

        for source_group_id, flow in source_group_shares.items():
            if flow <= 0:
                continue
            G.nodes[dest].setdefault("source_group_dict", {})
            G.nodes[dest]["source_group_dict"][source_group_id] = (
                G.nodes[dest]["source_group_dict"].get(source_group_id, 0) + flow
            )
            if dest_type == "exit" and exit_usage_by_source_group is not None and dest in exit_usage_by_source_group:
                exit_usage_by_source_group[dest][source_group_id] = (
                    exit_usage_by_source_group[dest].get(source_group_id, 0) + flow
                )

        G.nodes[dest]["people"] += amount

        if dest_type == "exit":
            evac_total += amount

    G.graph["_transit_queue"] = remaining
    return evac_total


def _schedule_moves_as_transit(G, moves):
    _, transit_queue = _ensure_transit_state(G)
    current_time = float(G.graph.get("_sim_time", 0.0))
    scheduled = []

    for u, v, amount in moves:
        sum_u = max(int(math.floor(float(G.nodes[u].get("people", 0.0)) + 1e-9)), 0)
        amount = max(int(amount), 0)
        if sum_u <= 0 or amount <= 0:
            continue

        line_shares = {}
        source_group_shares = {}
        source_group_dict = G.nodes[u].get("source_group_dict", {})
        active_groups = []
        group_weights = []
        group_caps = []

        for source_group_id, ppl in source_group_dict.items():
            ppl_int = max(int(math.floor(float(ppl) + 1e-9)), 0)
            if ppl_int <= 0:
                continue
            active_groups.append(source_group_id)
            group_weights.append(ppl_int)
            group_caps.append(ppl_int)

        if active_groups:
            group_alloc = _integer_capped_allocation(amount, group_weights, group_caps)
            for source_group_id, flow in zip(active_groups, group_alloc):
                if flow <= 0:
                    continue
                source_group_shares[source_group_id] = flow
                G.nodes[u]["source_group_dict"][source_group_id] = max(
                    int(G.nodes[u]["source_group_dict"].get(source_group_id, 0)) - flow,
                    0,
                )
                line_id = _source_group_line_id(source_group_id)
                line_shares[line_id] = line_shares.get(line_id, 0) + flow

            for line_id, flow in line_shares.items():
                G.nodes[u]["people_dict"][line_id] = max(
                    int(G.nodes[u]["people_dict"].get(line_id, 0)) - flow,
                    0,
                )
        else:
            active_lines = []
            line_weights = []
            line_caps = []
            for line_id, ppl in G.nodes[u].get("people_dict", {}).items():
                ppl_int = max(int(math.floor(float(ppl) + 1e-9)), 0)
                if ppl_int <= 0:
                    continue
                active_lines.append(line_id)
                line_weights.append(ppl_int)
                line_caps.append(ppl_int)

            line_alloc = _integer_capped_allocation(amount, line_weights, line_caps)
            for line_id, flow in zip(active_lines, line_alloc):
                if flow <= 0:
                    continue
                line_shares[line_id] = flow
                G.nodes[u]["people_dict"][line_id] = max(int(G.nodes[u]["people_dict"][line_id]) - flow, 0)

        G.nodes[u]["people"] = max(sum_u - amount, 0)
        travel_time = _edge_travel_time(G, u, v)

        transit_queue.append({
            "depart_time": current_time,
            "arrive_time": current_time + travel_time,
            "u": u,
            "v": v,
            "amount": amount,
            "line_shares": line_shares,
            "source_group_shares": source_group_shares,
            "travel_time": travel_time,
        })
        scheduled.append({
            "u": u,
            "v": v,
            "amount": amount,
            "travel_time": travel_time,
            "line_shares": line_shares,
            "source_group_shares": source_group_shares,
        })

    return scheduled


def _node_edge_types(G, node):
    edge_types = []
    for pred in G.predecessors(node):
        edge_types.append(G[pred][node].get("edge_type", ""))
    for succ in G.successors(node):
        edge_types.append(G[node][succ].get("edge_type", ""))
    return edge_types


def _is_queue_node(G, node):
    """
    排队节点的操作性定义：
    - 闸机
    - 楼扶梯 / 楼梯
    - 窄通道
    - 与 gate / exit 直接相连、承担入口等待功能的 virtual 节点

    注意：exit 在本模型里是 sink，真正的等待通常体现在出口前一级的节点。
    """
    node_type = G.nodes[node].get("type", "")
    node_type_l = str(node_type).lower()
    node_name_l = str(node).lower()

    if node_type_l.startswith("gate"):
        return True
    if node_type_l in {"stair", "escalator"}:
        return True
    if node_type_l == "passageway":
        width = float(G.nodes[node].get("width", float("inf")))
        return width <= 8.0

    if node_type_l == "virtual":
        if "entrance" in node_name_l or "exit" in node_name_l:
            return True
        edge_types = _node_edge_types(G, node)
        if any(("gate" in et.lower()) or ("exit" in et.lower()) for et in edge_types):
            return True

    return False


def _infer_node_line_ids(G, node):
    """根据节点名和邻接平台，推断该节点可能对应的线路集合。"""
    node_name_l = str(node).lower()
    line_ids = set()

    for line_id in ALL_LINE_IDS:
        if line_id.lower() in node_name_l:
            line_ids.add(line_id)
        platform_node = f"platform_{line_id}".lower()
        if node_name_l == platform_node:
            line_ids.add(line_id)

    if node in G.nodes:
        for pred in G.predecessors(node):
            pred_name_l = str(pred).lower()
            for line_id in ALL_LINE_IDS:
                if f"platform_{line_id}".lower() == pred_name_l or line_id.lower() in pred_name_l:
                    line_ids.add(line_id)
        for succ in G.successors(node):
            succ_name_l = str(succ).lower()
            for line_id in ALL_LINE_IDS:
                if f"platform_{line_id}".lower() == succ_name_l or line_id.lower() in succ_name_l:
                    line_ids.add(line_id)

    return line_ids


def _infer_node_line_ids_strict(node):
    """仅根据节点名直接包含的线路标识判断归属，避免跨线串扰。"""
    node_name_l = str(node).lower()
    line_ids = set()
    for line_id in ALL_LINE_IDS:
        if line_id.lower() in node_name_l:
            line_ids.add(line_id)
    return line_ids


def _get_node_series(metrics, node, key):
    node_series = metrics.get("node_series", {}).get(node, {})
    return (
        np.array(node_series.get("times", []), dtype=float),
        np.array(node_series.get(key, []), dtype=float),
    )


def _select_critical_queue_node(G, metrics, line_id):
    """为每条线路选一个最关键的排队节点，优先用传统算法下的队列累积。"""
    node_stats = metrics.get("node_stats", {})
    candidates = []

    for node in metrics.get("node_series", {}).keys():
        if not _is_queue_node(G, node):
            continue
        if line_id not in _infer_node_line_ids_strict(node):
            continue

        stat = node_stats.get(node, {})
        q_seconds = float(stat.get("queue_seconds", 0.0))
        peak_people = float(stat.get("peak_people", 0.0))
        candidates.append((q_seconds, peak_people, node))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2]


def _smooth_display_series(values, window=5):
    series = pd.Series(values, dtype=float).replace(0.0, np.nan).interpolate(limit_direction="both")
    if window and window > 1:
        series = series.rolling(window=window, min_periods=1).mean()
    return series.to_numpy()


MONITORED_EDGE_TYPES = {
    "platform_zone_to_vertical",
    "platform_to_vertical",
    "vertical_to_gate",
    "gate_to_vertical",
    "gate_to_exit",
    "gate_to_virtual",
    "vertical_to_exit",
    "vertical_to_transfer",
    "vertical_to_virtual",
    "transfer_to_gate",
    "transfer_to_exit",
    "transfer_to_vertical",
    "transfer_to_virtual",
    "virtual_to_exit",
    "virtual_to_gate",
}


def _edge_key(u, v):
    return f"{u} -> {v}"


def _is_monitored_edge(data):
    edge_type = str(data.get("edge_type", "")).lower()
    if edge_type in {"car_to_door", "train_door"}:
        return False
    return edge_type in MONITORED_EDGE_TYPES


def _edge_width_proxy(G, u, v):
    data = G[u][v]
    width_limit = data.get("width_limit")
    if width_limit is not None and float(width_limit) > 0:
        return float(width_limit)

    capacity = float(data.get("capacity", 0.0))
    if capacity > 0:
        return max(capacity / (5000.0 / 3600.0), 0.6)

    return 1.0


def _select_top_edges(edge_stats, top_k=12):
    rows = []
    for edge_key, stat in edge_stats.items():
        rows.append((float(stat.get("flow_total", 0.0)), float(stat.get("peak_passengers", 0.0)), edge_key))
    rows.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [edge_key for _, _, edge_key in rows[:top_k]]


def _select_top_queue_nodes(metrics, top_k=8):
    rows = []
    for node, stat in metrics.get("node_stats", {}).items():
        if stat.get("queue_seconds", 0.0) <= 0:
            continue
        rows.append((float(stat.get("queue_seconds", 0.0)), float(stat.get("peak_people", 0.0)), node))
    rows.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [node for _, _, node in rows[:top_k]]


def _edge_line_ids(G, edge_key):
    try:
        u, v = [part.strip() for part in edge_key.split("->", 1)]
    except ValueError:
        return set()
    return _infer_node_line_ids_strict(u) | _infer_node_line_ids_strict(v)


def _edge_line_ids_from_key(edge_key):
    try:
        u, v = [part.strip() for part in edge_key.split("->", 1)]
    except ValueError:
        return set()
    return _infer_node_line_ids_strict(u) | _infer_node_line_ids_strict(v)


def _select_representative_edges_for_line(G, metrics, line_id, top_k=2):
    def _safe_nanstd(arr):
        arr = np.asarray(arr, dtype=float)
        arr = arr[~np.isnan(arr)]
        if arr.size <= 1:
            return 0.0
        return float(np.std(arr))

    rows = []
    for edge_key, series in metrics.get("edge_series", {}).items():
        if line_id not in _edge_line_ids(G, edge_key):
            continue
        passengers = np.array(series.get("passengers", []), dtype=float)
        speed = np.array(series.get("speed", []), dtype=float)
        if passengers.size == 0:
            continue
        valid_passengers = passengers[~np.isnan(passengers)]
        if valid_passengers.size == 0:
            continue

        peak_passengers = float(np.nanmax(valid_passengers))
        mean_passengers = float(np.nanmean(valid_passengers))
        passenger_std = _safe_nanstd(valid_passengers)
        speed_std = _safe_nanstd(speed)
        finite_speed = speed[np.isfinite(speed)]
        min_speed = float(np.nanmin(finite_speed)) if finite_speed.size > 0 else 1.427
        active_ratio = float(np.mean(valid_passengers > 0.5))

        # 优先选“真正有载荷、且会发生拥挤波动”的链路，而不是自由流边
        if peak_passengers < 1.0 and mean_passengers < 0.5:
            continue

        line_count = len(_edge_line_ids(G, edge_key))
        multi_line_penalty = 0.75 if line_count > 1 else 1.0

        score = (
            2.2 * peak_passengers
            + 1.4 * mean_passengers
            + 6.0 * passenger_std
            + 10.0 * speed_std
            + 20.0 * max(0.0, 1.427 - min_speed)
            + 2.0 * active_ratio
        ) * multi_line_penalty
        rows.append((score, peak_passengers, mean_passengers, line_count, edge_key))

    if any(item[3] == 1 for item in rows):
        rows = [item for item in rows if item[3] == 1]
    rows.sort(key=lambda x: x[0], reverse=True)
    return [edge_key for _, _, _, _, edge_key in rows[:top_k]]


def _select_snapshot_time_for_edges(metrics, edge_keys):
    if not edge_keys:
        return float(metrics.get("time", 0.0))

    ref_times = None
    for edge_key in edge_keys:
        series = metrics.get("edge_series", {}).get(edge_key, {})
        times = np.array(series.get("times", []), dtype=float)
        if times.size > 0:
            ref_times = times
            break

    if ref_times is None or ref_times.size == 0:
        return float(metrics.get("time", 0.0))

    total = np.zeros_like(ref_times, dtype=float)
    for edge_key in edge_keys:
        series = metrics.get("edge_series", {}).get(edge_key, {})
        times = np.array(series.get("times", []), dtype=float)
        passengers = np.array(series.get("passengers", []), dtype=float)
        if times.size == 0 or passengers.size == 0:
            continue
        if times.size != ref_times.size or not np.allclose(times, ref_times):
            passengers = np.interp(ref_times, times, np.nan_to_num(passengers, nan=0.0), left=0.0, right=0.0)
        else:
            passengers = np.nan_to_num(passengers, nan=0.0)
        total += passengers

    return float(ref_times[int(np.argmax(total))])


def _select_representative_nodes_for_line(G, metrics, line_id, top_k=2):
    rows = []
    for node in metrics.get("node_series", {}).keys():
        if line_id not in _infer_node_line_ids_strict(node):
            continue
        stat = metrics.get("node_stats", {}).get(node, {})
        q_seconds = float(stat.get("queue_seconds", 0.0))
        peak_people = float(stat.get("peak_people", 0.0))
        if q_seconds <= 0 and peak_people <= 0:
            continue
        rows.append((q_seconds + 0.25 * peak_people, node))
    rows.sort(key=lambda x: x[0], reverse=True)
    return [node for _, node in rows[:top_k]]


def _select_global_critical_queue_node(metrics):
    nodes = _select_top_queue_nodes(metrics, top_k=1)
    return nodes[0] if nodes else None


def _nearest_index(times, target_time):
    if len(times) == 0:
        return None
    times = np.asarray(times, dtype=float)
    return int(np.argmin(np.abs(times - float(target_time))))


def _capture_edge_snapshot(G, current_time, monitored_edges):
    transit_queue = G.graph.get("_transit_queue", [])
    monitored = set(monitored_edges)
    snapshot = {
        edge_key: {"passengers": 0.0, "speed_sum": 0.0}
        for edge_key in monitored
    }

    for item in transit_queue:
        if item.get("depart_time", 0.0) > current_time + 1e-9:
            continue
        if item.get("arrive_time", 0.0) <= current_time + 1e-9:
            continue

        u = item.get("u")
        v = item.get("v")
        edge_key = _edge_key(u, v)
        if edge_key not in snapshot:
            continue

        amount = float(item.get("amount", 0.0))
        if amount <= 0:
            continue

        travel_time = max(float(item.get("travel_time", _edge_travel_time(G, u, v))), 0.001)
        length = max(float(G[u][v].get("length", 0.0)), 0.0)
        speed = length / travel_time if length > 0 else spr.PAPER_FREE_SPEED

        snapshot[edge_key]["passengers"] += amount
        snapshot[edge_key]["speed_sum"] += amount * speed

    return snapshot


def _apply_node_disruption(G, node, factor=0.35):
    """节点中断：将目标节点及其相邻连边完全切断。"""
    if node not in G.nodes:
        return
    G.nodes[node]["capacity"] = 0.0
    G.nodes[node]["blocked"] = True

    # 原文的设定是“节点中断 + 与该节点相连的连接中断”，这里直接移除入边/出边。
    for pred, _ in list(G.in_edges(node)):
        if G.has_edge(pred, node):
            G.remove_edge(pred, node)
    for _, succ in list(G.out_edges(node)):
        if G.has_edge(node, succ):
            G.remove_edge(node, succ)


def _collect_line_queue_nodes(G, metrics, line_id):
    """收集某条线对应的所有排队节点，按排队累计从高到低排序。"""
    nodes = []
    node_stats = metrics.get("node_stats", {})
    for node in metrics.get("node_series", {}).keys():
        if not _is_queue_node(G, node):
            continue
        if line_id not in _infer_node_line_ids_strict(node):
            continue
        stat = node_stats.get(node, {})
        q_seconds = float(stat.get("queue_seconds", 0.0))
        peak_people = float(stat.get("peak_people", 0.0))
        nodes.append((q_seconds, peak_people, node))

    nodes.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [node for _, _, node in nodes]


def _select_critical_node_for_line(G, metrics, line_id):
    nodes = _collect_line_queue_nodes(G, metrics, line_id)
    return nodes[0] if nodes else None


def _select_article_links(metrics, top_k=16):
    """按论文 Fig.13/Fig.15 的口径，选出全局最关键的 link。"""
    rows = []
    for edge_key, series in metrics.get("edge_series", {}).items():
        passengers = np.array(series.get("passengers", []), dtype=float)
        speed = np.array(series.get("speed", []), dtype=float)
        if passengers.size == 0:
            continue

        valid_passengers = passengers[np.isfinite(passengers)]
        if valid_passengers.size == 0:
            continue
        finite_speed = speed[np.isfinite(speed)]
        if finite_speed.size < 8:
            continue

        peak_passengers = float(np.nanmax(valid_passengers))
        mean_passengers = float(np.nanmean(valid_passengers))
        passenger_std = float(np.nanstd(valid_passengers)) if valid_passengers.size > 1 else 0.0
        speed_std = float(np.nanstd(finite_speed)) if finite_speed.size > 1 else 0.0
        min_speed = float(np.nanmin(finite_speed)) if finite_speed.size > 0 else 1.427
        speed_range = float(np.nanmax(finite_speed) - np.nanmin(finite_speed)) if finite_speed.size > 0 else 0.0
        active_ratio = float(np.mean(valid_passengers > 0.5))

        if peak_passengers < 1.0 and mean_passengers < 0.5:
            continue
        # 只保留真正“会动”的 link，避免 Fig.13 里出现几乎贴自由流的直线。
        if speed_range < 0.05 and passenger_std < 0.5 and mean_passengers < 1.0:
            continue

        score = (
            2.3 * peak_passengers
            + 1.1 * mean_passengers
            + 4.8 * passenger_std
            + 12.0 * speed_std
            + 24.0 * speed_range
            + 16.0 * max(0.0, 1.427 - min_speed)
            + 2.0 * active_ratio
        )
        rows.append((score, peak_passengers, edge_key))

    rows.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [edge_key for _, _, edge_key in rows[:top_k]]


def _select_article_nodes(metrics, top_k=16):
    """按论文 Fig.14 的口径，选出全局最关键的 queue nodes。"""
    rows = []
    for node, series in metrics.get("node_series", {}).items():
        queue = np.array(series.get("queue", []), dtype=float)
        if queue.size == 0:
            continue
        valid_queue = queue[np.isfinite(queue)]
        if valid_queue.size == 0:
            continue

        stat = metrics.get("node_stats", {}).get(node, {})
        q_seconds = float(stat.get("queue_seconds", 0.0))
        peak_people = float(stat.get("peak_people", 0.0))
        queue_std = float(np.nanstd(valid_queue)) if valid_queue.size > 1 else 0.0
        if q_seconds <= 0 and peak_people <= 0:
            continue

        score = 1.2 * q_seconds + 1.0 * peak_people + 4.0 * queue_std
        rows.append((score, q_seconds, node))

    rows.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [node for _, _, node in rows[:top_k]]


def _select_snapshot_edges_for_comparison(base_metrics, disrupted_metrics, snapshot_time, top_k=14, focus_line_ids=None):
    """按 Fig.15 的口径，选出在观察时刻真正有客流、且正常/扰动差异最大的 link。

    如果提供 focus_line_ids，则优先保留与故障设施所在线路相关的 link，
    避免全局筛选把局部故障效应冲淡。
    """
    rows = []
    base_series_map = base_metrics.get("edge_series", {})
    dis_series_map = disrupted_metrics.get("edge_series", {}) if disrupted_metrics else {}
    all_edges = sorted(set(base_series_map.keys()) | set(dis_series_map.keys()))
    focus_line_ids = set(focus_line_ids or [])

    for edge_key in all_edges:
        if focus_line_ids:
            edge_line_ids = _edge_line_ids_from_key(edge_key)
            if edge_line_ids.isdisjoint(focus_line_ids):
                continue
        base_series = base_series_map.get(edge_key, {})
        dis_series = dis_series_map.get(edge_key, {})
        base_times = np.array(base_series.get("times", []), dtype=float)
        dis_times = np.array(dis_series.get("times", []), dtype=float)
        base_pass = np.array(base_series.get("passengers", []), dtype=float)
        dis_pass = np.array(dis_series.get("passengers", []), dtype=float)

        if base_times.size == 0 and dis_times.size == 0:
            continue

        idx_base = _nearest_index(base_times, snapshot_time) if base_times.size > 0 else None
        idx_dis = _nearest_index(dis_times, snapshot_time) if dis_times.size > 0 else None

        base_val = float(base_pass[idx_base]) if idx_base is not None and idx_base < len(base_pass) else 0.0
        dis_val = float(dis_pass[idx_dis]) if idx_dis is not None and idx_dis < len(dis_pass) else 0.0
        combined = base_val + dis_val
        delta = abs(dis_val - base_val)

        # 观察时刻没有客流的边不进入 Fig.15。
        if combined < 0.5:
            continue

        rows.append((delta, combined, edge_key))

    rows.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [edge_key for _, _, edge_key in rows[:top_k]]


def _select_representative_snapshot_time_for_comparison(base_metrics, disrupted_metrics, edge_keys):
    """
    给 Fig.15 选一个差异最大时刻：
    - 同一组 link 在正常/扰动两边都要有流量
    - 优先挑“正常/扰动差异最大、同时不至于空载”的活跃时刻

    这比把 period 固定成 15 min 更符合疏散场景中的故障影响展示。
    """
    if not edge_keys:
        return float(base_metrics.get("time", 0.0))

    base_series_map = base_metrics.get("edge_series", {})
    dis_series_map = disrupted_metrics.get("edge_series", {}) if disrupted_metrics else {}
    candidate_times = []

    for edge_key in edge_keys:
        for series_map in (base_series_map, dis_series_map):
            times = np.array(series_map.get(edge_key, {}).get("times", []), dtype=float)
            if times.size > 0:
                candidate_times.append(times)

    if not candidate_times:
        return float(base_metrics.get("time", 0.0))

    ref_times = np.unique(np.concatenate(candidate_times))
    best_time = float(ref_times[0])
    best_score = -1.0

    for t in ref_times:
        base_total = 0.0
        dis_total = 0.0
        for edge_key in edge_keys:
            base_series = base_series_map.get(edge_key, {})
            dis_series = dis_series_map.get(edge_key, {})

            base_times = np.array(base_series.get("times", []), dtype=float)
            dis_times = np.array(dis_series.get("times", []), dtype=float)
            base_pass = np.array(base_series.get("passengers", []), dtype=float)
            dis_pass = np.array(dis_series.get("passengers", []), dtype=float)

            idx_base = _nearest_index(base_times, t) if base_times.size > 0 else None
            idx_dis = _nearest_index(dis_times, t) if dis_times.size > 0 else None

            if idx_base is not None and idx_base < len(base_pass):
                base_total += float(base_pass[idx_base])
            if idx_dis is not None and idx_dis < len(dis_pass):
                dis_total += float(dis_pass[idx_dis])

        combined = base_total + dis_total
        delta = abs(dis_total - base_total)
        # 差异优先，但保留一个轻微的总流量加权，避免选到噪声型低流时刻。
        score = delta + 0.08 * combined
        if combined < 1.0:
            continue
        if score > best_score:
            best_score = score
            best_time = float(t)

    return best_time


def _aggregate_line_node_series(G, metrics, line_id, key, normalize_by_area=False):
    """把某条线的多个排队节点时间序列聚合成一条均值曲线。"""
    nodes = _collect_line_queue_nodes(G, metrics, line_id)
    if not nodes:
        return np.array([]), np.array([]), []

    ref_node = nodes[0]
    ref_times = np.array(metrics.get("node_series", {}).get(ref_node, {}).get("times", []), dtype=float)
    if ref_times.size == 0:
        return np.array([]), np.array([]), nodes

    stack = []
    for node in nodes:
        node_series = metrics.get("node_series", {}).get(node, {})
        values = np.array(node_series.get(key, []), dtype=float)
        if values.size == 0:
            continue
        if normalize_by_area:
            area = max(float(G.nodes[node].get("area", 1.0)), 0.001)
            values = values / area
        stack.append(values[:ref_times.size])

    if not stack:
        return ref_times, np.full(ref_times.shape, np.nan), nodes

    matrix = np.vstack([row if row.size == ref_times.size else np.pad(row, (0, max(0, ref_times.size - row.size)), constant_values=np.nan)[:ref_times.size] for row in stack])
    valid_counts = np.sum(~np.isnan(matrix), axis=0)
    summed = np.nansum(matrix, axis=0)
    agg = np.divide(summed, valid_counts, out=np.full(ref_times.shape, np.nan), where=valid_counts > 0)

    return ref_times, agg, nodes


# 🌟 从配置文件导入纯数据
from lines_config import (
    NODES_DATA,
    EDGES_DATA,
    STATION_LEVELS,
    PLATFORM_VERTICAL_SPECS,
    PLATFORM_WAITING_ZONE_SPECS,
    PRECALCULATED_PLATFORM_DISTS,
    OBSTACLE_AREAS,
)
# ==============================================================================
# 0. 中文支持与全局参数
# ==============================================================================
system_name = platform.system()
if system_name == "Windows":
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
elif system_name == "Darwin":
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
else:
    plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

MODE = "EVACUATION"
DELTA_T = 0.5

ALL_LINE_IDS = ["L2", "L7", "L16", "L18", "Maglev"]
MODERATE_CONGESTION_DENSITY_THRESHOLD = 3.0
SEVERE_CONGESTION_DENSITY_THRESHOLD = 5.0

SOURCE_GROUP_SUFFIXES = {
    "train_1": "train1",
    "train_2": "train2",
    "platform_waiting": "platform",
    "hall_people": "hall",
    "transfer_people": "transfer",
}

SOURCE_GROUP_LABELS = {
    "train1": "train_1",
    "train2": "train_2",
    "platform": "platform_waiting",
    "hall": "hall_people",
    "transfer": "transfer_people",
}

HALL_STAGING_SPECS = {
    "L7": [
        {
            "name": "VN_L7_Hall_Arrival",
            "targets": ["Gate_L7_N_West", "Gate_L7_N_Mid", "Gate_L7_N_East", "Gate_L7_West_Vert"],
            "manual_area": 90.0,
        }
    ],
    "L2": [
        {
            "name": "VN_L2_Hall_Arrival",
            "targets": ["Gate_L2_N_West", "Gate_L2_N_East", "Gate_L2_S_West", "Gate_L2_S_East"],
            "manual_area": 120.0,
        }
    ],
    "L16": [
        {
            "name": "VN_L16_Hall_Arrival",
            "targets": ["Gate_L16_N1", "Gate_L16_N2", "Gate_L16_S1", "Gate_L16_S2"],
            "manual_area": 110.0,
        }
    ],
    "L18": [
        {
            "name": "VN_L18_Hall_Arrival_Base",
            "targets": ["VN_L18_Hall_Split_A", "VN_L18_Hall_Split_B"],
            "manual_area": 250.0,
        }
    ],
}


def _source_group_id(line_id, bucket_key):
    suffix = SOURCE_GROUP_SUFFIXES.get(bucket_key, bucket_key)
    return f"{line_id}_{suffix}"


def _platform_waiting_zone_source_group_id(line_id, zone_name):
    return f"{_source_group_id(line_id, 'platform_waiting')}::{zone_name}"


def _transfer_relation_source_group_id(line_id, transfer_node_name):
    normalized = transfer_node_name.replace("-", "_")
    tokens = [token for token in normalized.split("_") if token]
    line_tokens = [token for token in ALL_LINE_IDS if token in tokens]
    counterpart = ""
    for token in line_tokens:
        if token != line_id:
            counterpart = token
            break
    if not counterpart:
        return _source_group_id(line_id, "transfer_people")
    return f"{line_id}_{counterpart}_transfer"


def _transfer_source_line(transfer_node_name):
    prefix = "Transfer_"
    if not transfer_node_name.startswith(prefix):
        return ""
    tail = transfer_node_name[len(prefix):]
    if not tail:
        return ""
    first_chunk = tail.split("_", 1)[0]
    if "-" in first_chunk:
        return first_chunk.split("-", 1)[0]
    return first_chunk


def _transfer_nodes_for_source_line(G, line_id):
    if "TRANSFERS" not in NODES_DATA:
        return []
    nodes = []
    for node_name in NODES_DATA["TRANSFERS"].keys():
        if node_name not in G.nodes:
            continue
        if _transfer_source_line(node_name) == line_id:
            nodes.append(node_name)
    return nodes


def _parse_source_group_id(source_group_id):
    zone_name = ""
    base_group_id = source_group_id
    if "::" in source_group_id:
        base_group_id, zone_name = source_group_id.split("::", 1)
    if "_" not in base_group_id:
        return base_group_id, base_group_id, zone_name
    line_id, suffix = base_group_id.split("_", 1)
    if suffix in SOURCE_GROUP_LABELS:
        return line_id, SOURCE_GROUP_LABELS.get(suffix, suffix), zone_name
    if suffix.endswith("_transfer"):
        relation = suffix[: -len("_transfer")]
        if not zone_name:
            zone_name = relation
        return line_id, "transfer_people", zone_name
    return line_id, suffix, zone_name


def _source_group_line_id(source_group_id):
    line_id, _, _ = _parse_source_group_id(source_group_id)
    return line_id


def _source_group_totals_from_pop_dict(pop_dict):
    totals = {}
    for line_id, line_data in pop_dict.items():
        for bucket_key in SOURCE_GROUP_SUFFIXES:
            amount = int(round(float(line_data.get(bucket_key, 0))))
            if amount > 0:
                totals[_source_group_id(line_id, bucket_key)] = amount
    return totals


def _source_group_totals_from_graph(G):
    totals = {}
    for _, node_data in G.nodes(data=True):
        for source_group_id, amount in node_data.get("source_group_dict", {}).items():
            amount_int = int(round(float(amount)))
            if amount_int <= 0:
                continue
            totals[source_group_id] = totals.get(source_group_id, 0) + amount_int
    return totals
TRAIN_PHYSICS = {
    "L7": {
        "trains": 2,
        "cars": 6,
        "car_people": 270,
        "doors_per_car": 5,
        "door_w": 1.4,
        "area_per_car": 70.62,
        "train_spans": [
            _span_from_train_cfg(PATHFINDER_CONFIG["L7"]["trains"][0]),
            _span_from_train_cfg(PATHFINDER_CONFIG["L7"]["trains"][1]),
        ],
    },
    "L2": {
        "trains": 2,
        "cars": 8,
        "car_people": 300,
        "doors_per_car": 5,
        "door_w": 1.4,
        "area_per_car": 70.62,
        "train_spans": [
            _span_from_train_cfg(PATHFINDER_CONFIG["L2"]["trains"][0]),
            _span_from_train_cfg(PATHFINDER_CONFIG["L2"]["trains"][1]),
        ],
    },
    "L16": {
        "trains": 2,
        "cars": 6,
        "car_people": 205,
        "doors_per_car": 3,
        "door_w": 1.4,
        "area_per_car": 70.62,
        "train_spans": [
            _span_from_train_cfg(PATHFINDER_CONFIG["L16_Island1"]["trains"][0]),
            _span_from_train_cfg(PATHFINDER_CONFIG["L16_Island2"]["trains"][0]),
        ],
    },
    "L18": {
        "trains": 2,
        "cars": 6,
        "car_people": 275,
        "doors_per_car": 5,
        "door_w": 1.4,
        "area_per_car": 66,
        "train_spans": [
            _span_from_train_cfg(PATHFINDER_CONFIG["L18"]["trains"][0]),
            _span_from_train_cfg(PATHFINDER_CONFIG["L18"]["trains"][1]),
        ],
    },
    "Maglev": {
        "trains": 2,
        "cars": 5,
        "train_people": 959,
        "doors_per_car": 4,
        "door_w": 1.4,
        "area_per_car": 89,
        "train_spans": [
            _mid_span(PATHFINDER_CONFIG["Maglev"]["trains"][0], PATHFINDER_CONFIG["Maglev"]["trains"][1]),
            _mid_span(PATHFINDER_CONFIG["Maglev"]["trains"][2], PATHFINDER_CONFIG["Maglev"]["trains"][3]),
        ],
    },
}


def _platform_waiting_zone_config(line_id):
    return PLATFORM_WAITING_ZONE_SPECS.get(line_id, {})


def _platform_waiting_zone_defs(line_id):
    return _platform_waiting_zone_config(line_id).get("zones", [])


def _platform_waiting_zone_spec_complete(zone_def):
    return zone_def.get("area") is not None and zone_def.get("pos") is not None


def _platform_waiting_zone_defs_ready(line_id):
    zone_defs = _platform_waiting_zone_defs(line_id)
    return bool(zone_defs) and all(_platform_waiting_zone_spec_complete(zone_def) for zone_def in zone_defs)


def _platform_waiting_zone_name(line_id, train_idx, car_idx, band=None):
    for zone in _platform_waiting_zone_defs(line_id):
        car_indices = zone.get("car_indices")
        if car_indices is None:
            car_indices = [zone.get("car_index", -1)]
        if int(car_idx) not in {int(idx) for idx in car_indices}:
            continue
        zone_band = zone.get("band")
        if band is not None and zone_band is not None and str(zone_band).lower() != str(band).lower():
            continue
        train_indices = zone.get("train_indices")
        if train_indices is None:
            train_indices = [zone.get("train_index", 1)]
        if int(train_idx) in {int(idx) for idx in train_indices}:
            return zone["name"]
    return f"Platform_{line_id}_T{train_idx}_C{car_idx}_Wait"


def _platform_waiting_zone_area_weights(zone_defs):
    return [max(float(zone.get("area", 1.0)), 0.001) for zone in zone_defs]


def _pathfinder_distance(pos_a, pos_b):
    ax, ay = pos_a
    bx, by = pos_b
    return math.hypot(ax - bx, ay - by)


def _square_zone_average_distance(center_pos, area, target_pos, samples_per_side=5):
    """
    将等待区视为以 center_pos 为中心的正方形，
    用规则采样近似“区内均匀分布乘客”到 target_pos 的平均距离。
    """
    area = max(float(area), 0.001)
    side = math.sqrt(area)
    half = side / 2.0
    sample_n = max(int(samples_per_side), 1)
    step = side / sample_n
    cx, cy = center_pos
    tx, ty = target_pos

    total_dist = 0.0
    sample_count = 0
    for ix in range(sample_n):
        sx = cx - half + (ix + 0.5) * step
        for iy in range(sample_n):
            sy = cy - half + (iy + 0.5) * step
            total_dist += math.hypot(sx - tx, sy - ty)
            sample_count += 1

    if sample_count <= 0:
        return _pathfinder_distance(center_pos, target_pos)
    return total_dist / sample_count


def _platform_waiting_zone_pos(line_id, zone_def, fallback_pos):
    manual_pos = zone_def.get("pos")
    if manual_pos is None:
        raise ValueError(
            f"Platform waiting zone '{zone_def.get('name')}' is missing a Pathfinder midpoint position. "
            f"Please fill {line_id}_PLATFORM_WAITING_ZONE_CONFIG['{zone_def.get('zone_key')}']['pos'] in lines_config.py."
        )
    if manual_pos:
        return tuple(manual_pos)

    car_idx = int(zone_def.get("car_index", 1))
    train_indices = zone_def.get("train_indices")
    if train_indices is None:
        train_indices = [zone_def.get("train_index", 1)]
    physics = TRAIN_PHYSICS.get(line_id, {})
    train_spans = physics.get("train_spans", [])
    door_count = max(int(physics.get("doors_per_car", 1)), 1)
    car_count = max(int(physics.get("cars", 1)), 1)
    zone_positions = []
    for train_idx in train_indices:
        train_idx = int(train_idx)
        if train_idx - 1 >= len(train_spans):
            continue
        zone_positions.append(
            _layout_point_from_span(
                train_spans[train_idx - 1],
                car_idx,
                0,
                car_count,
                door_count,
                fallback_pos,
            )
        )
    if not zone_positions:
        return fallback_pos
    return (
        sum(pos[0] for pos in zone_positions) / len(zone_positions),
        sum(pos[1] for pos in zone_positions) / len(zone_positions),
    )


def _platform_vertical_pf_map(line_id, zone_def=None):
    if line_id == "L16":
        train_indices = zone_def.get("train_indices") if zone_def else None
        if train_indices:
            train_idx = int(train_indices[0])
            if train_idx == 1:
                return PATHFINDER_CONFIG.get("L16_Island1", {}).get("verticals", {})
            if train_idx == 2:
                return PATHFINDER_CONFIG.get("L16_Island2", {}).get("verticals", {})

        merged = {}
        merged.update(PATHFINDER_CONFIG.get("L16_Island1", {}).get("verticals", {}))
        merged.update(PATHFINDER_CONFIG.get("L16_Island2", {}).get("verticals", {}))
        return merged

    return PATHFINDER_CONFIG.get(line_id, {}).get("verticals", {})


def _platform_waiting_zone_nodes(G, line_id):
    return [
        zone["name"]
        for zone in _platform_waiting_zone_defs(line_id)
        if zone.get("name") in G.nodes
    ]


def _line_id_for_platform_parent(platform_node):
    for line_id, cfg in PLATFORM_WAITING_ZONE_SPECS.items():
        if cfg.get("parent_platform") == platform_node:
            return line_id
    return None


def _representative_routing_source(G, current_node):
    line_id = _line_id_for_platform_parent(current_node)
    if not line_id:
        return current_node

    zone_nodes = _platform_waiting_zone_nodes(G, line_id)
    if not zone_nodes:
        return current_node

    active_zone_nodes = [
        n for n in zone_nodes if float(G.nodes[n].get("people", 0.0)) > 0.1
    ]
    if not active_zone_nodes:
        return current_node

    active_zone_nodes.sort(
        key=lambda n: (
            float(G.nodes[n].get("people", 0.0)),
            -int(G.nodes[n].get("car_index", 0)),
        ),
        reverse=True,
    )
    return active_zone_nodes[0]


def _is_hidden_visual_node(data):
    return data.get("type") in {"train", "train_car", "platform_waiting_zone"}


def _visual_people_at_node(G, node, node_people):
    total = max(float(node_people.get(node, 0.0)), 0.0)
    line_id = _line_id_for_platform_parent(node)
    if not line_id:
        return total
    for zone_name in _platform_waiting_zone_nodes(G, line_id):
        total += max(float(node_people.get(zone_name, 0.0)), 0.0)
    return total


def _integer_capped_allocation(total_people, weights, caps=None):
    total_int = max(int(round(float(total_people))), 0)
    if total_int <= 0 or not weights:
        return [0] * len(weights)

    clean_weights = [max(float(w), 0.0) for w in weights]
    weight_sum = sum(clean_weights)
    if weight_sum <= 0:
        clean_weights = [1.0] * len(weights)
        weight_sum = float(len(weights))

    if caps is None:
        caps_int = [total_int] * len(weights)
    else:
        caps_int = []
        for cap in caps:
            if cap is None or math.isinf(float(cap)):
                caps_int.append(total_int)
            else:
                caps_int.append(max(int(math.floor(float(cap) + 1e-9)), 0))

    target_total = min(total_int, sum(caps_int))
    if target_total <= 0:
        return [0] * len(weights)

    raw_alloc = [target_total * (w / weight_sum) for w in clean_weights]
    alloc = [min(cap, int(math.floor(raw + 1e-9))) for raw, cap in zip(raw_alloc, caps_int)]
    remaining = target_total - sum(alloc)

    while remaining > 0:
        candidates = [i for i in range(len(alloc)) if alloc[i] < caps_int[i]]
        if not candidates:
            break
        candidates.sort(
            key=lambda i: (
                raw_alloc[i] - alloc[i],
                clean_weights[i],
                caps_int[i] - alloc[i],
                -i,
            ),
            reverse=True,
        )
        for idx in candidates:
            if remaining <= 0:
                break
            if alloc[idx] >= caps_int[idx]:
                continue
            alloc[idx] += 1
            remaining -= 1

    return alloc


def _edge_integer_capacity_for_step(G, u, v):
    credit_map = G.graph.setdefault("_edge_flow_credit", {})
    key = (u, v)
    capacity = float(G[u][v].get("capacity", 0.0))
    if math.isinf(capacity):
        return max(int(math.floor(float(G.nodes[u].get("people", 0.0)) + 1e-9)), 0)

    carry = float(credit_map.get(key, 0.0))
    raw_credit = max(capacity, 0.0) * DELTA_T + carry
    whole_capacity = max(int(math.floor(raw_credit + 1e-9)), 0)
    credit_map[key] = raw_credit - math.floor(raw_credit + 1e-9)
    return whole_capacity


def _integerize_moves(G, moves):
    if not moves:
        return []

    grouped = {}
    for u, v, amount in moves:
        if amount <= 0 or u not in G.nodes or v not in G.nodes:
            continue
        grouped.setdefault(u, []).append((v, float(amount)))

    integer_moves = []
    for u, proposals in grouped.items():
        available = max(int(math.floor(float(G.nodes[u].get("people", 0.0)) + 1e-9)), 0)
        if available <= 0:
            continue

        edge_targets = []
        req_weights = []
        edge_caps = []
        for v, amount in proposals:
            edge_cap = _edge_integer_capacity_for_step(G, u, v)
            if edge_cap <= 0:
                continue
            edge_targets.append(v)
            req_weights.append(max(amount, 0.0))
            edge_caps.append(edge_cap)

        if not edge_targets:
            continue

        flow_alloc = _integer_capped_allocation(available, req_weights, edge_caps)
        for v, flow in zip(edge_targets, flow_alloc):
            if flow > 0:
                integer_moves.append((u, v, int(flow)))

    return integer_moves


def _add_people_to_nodes_by_weights(
    G,
    node_names,
    line_id,
    total_people,
    weights,
    source_group_id=None,
    source_group_ids=None,
):
    if total_people <= 0 or not node_names:
        return

    allocations = _integer_capped_allocation(total_people, weights)
    for idx, (node_name, amount) in enumerate(zip(node_names, allocations)):
        if amount <= 0:
            continue
        G.nodes[node_name]["people"] += amount
        G.nodes[node_name]["people_dict"][line_id] += amount
        active_source_group_id = source_group_id
        if source_group_ids is not None and idx < len(source_group_ids):
            active_source_group_id = source_group_ids[idx]
        if active_source_group_id is not None:
            G.nodes[node_name].setdefault("source_group_dict", {})
            G.nodes[node_name]["source_group_dict"][active_source_group_id] = (
                G.nodes[node_name]["source_group_dict"].get(active_source_group_id, 0) + amount
            )


def _add_platform_waiting_zone_nodes_and_edges(G):
    for line_id, cfg in PLATFORM_WAITING_ZONE_SPECS.items():
        if not _platform_waiting_zone_defs_ready(line_id):
            continue
        parent_platform = cfg.get("parent_platform", f"Platform_{line_id}")
        if parent_platform not in G.nodes:
            continue

        vertical_group = PLATFORM_VERTICAL_SPECS.get(line_id, {}).get("vertical_group")
        if not vertical_group or vertical_group not in NODES_DATA:
            continue

        fallback_pos = G.nodes[parent_platform].get("pos", (0.0, 0.0))
        delta_h = get_delta_h(line_id)

        for zone_def in cfg.get("zones", []):
            zone_name = zone_def["name"]
            zone_pos = _platform_waiting_zone_pos(line_id, zone_def, fallback_pos)
            vertical_pf_map = _platform_vertical_pf_map(line_id, zone_def)
            raw_area = zone_def.get("area")
            if raw_area is None:
                raise ValueError(
                    f"Platform waiting zone '{zone_name}' is missing an area value. "
                    f"Please fill {line_id}_PLATFORM_WAITING_ZONE_CONFIG['{zone_def.get('zone_key')}']['area'] in lines_config.py."
                )
            zone_area = max(float(raw_area), 1.0)
            G.add_node(
                zone_name,
                type="platform_waiting_zone",
                capacity=999999,
                area=zone_area,
                people=0.0,
                pos=zone_pos,
                pathfinder_pos=zone_pos,
                line_id=line_id,
                parent_platform=parent_platform,
                car_index=int(zone_def.get("car_index", 1)),
                car_indices=zone_def.get("car_indices"),
                band=zone_def.get("band"),
                train_indices=zone_def.get("train_indices"),
            )

            candidate_verticals = vertical_pf_map.keys() if vertical_pf_map else NODES_DATA[vertical_group].keys()
            for vertical_name in candidate_verticals:
                if vertical_name not in G.nodes:
                    continue
                vertical_pf_pos = vertical_pf_map.get(vertical_name)
                if not vertical_pf_pos:
                    continue
                horizontal_dist = _square_zone_average_distance(zone_pos, zone_area, vertical_pf_pos)
                total_edge_length = horizontal_dist + 2.0 * delta_h
                G.add_edge(
                    zone_name,
                    vertical_name,
                    length=total_edge_length,
                    capacity=G.nodes[vertical_name]["capacity"],
                    edge_type="platform_zone_to_vertical",
                )


def _hall_staging_nodes_for_line(G, line_id):
    specs = HALL_STAGING_SPECS.get(line_id, [])
    return [cfg["name"] for cfg in specs if cfg["name"] in G.nodes]


def _ensure_hall_staging_nodes(G):
    for line_id, staging_specs in HALL_STAGING_SPECS.items():
        for cfg in staging_specs:
            node_name = cfg["name"]
            target_nodes = [n for n in cfg.get("targets", []) if n in G.nodes]
            if not target_nodes:
                continue

            if node_name not in G.nodes:
                xs, ys = [], []
                cap_sum = 0.0
                for target in target_nodes:
                    pos = G.nodes[target].get("pos", (0.0, 0.0))
                    xs.append(float(pos[0]))
                    ys.append(float(pos[1]))
                    cap_sum += float(G.nodes[target].get("capacity", 1.0))

                center_x = float(sum(xs) / max(len(xs), 1))
                center_y = float(sum(ys) / max(len(ys), 1)) + 6.0
                G.add_node(
                    node_name,
                    type="virtual",
                    people=0,
                    capacity=max(cap_sum, 1.0),
                    manual_area=float(cfg.get("manual_area", 80.0)),
                    pos=(center_x, center_y),
                    line_id=line_id,
                )

            source_pos = G.nodes[node_name].get("pos", (0.0, 0.0))
            for target in target_nodes:
                if G.has_edge(node_name, target):
                    continue
                target_pos = G.nodes[target].get("pos", source_pos)
                length = max(float(np.linalg.norm(np.array(target_pos) - np.array(source_pos))), 4.0)
                capacity = float(G.nodes[target].get("capacity", 1.0))
                G.add_edge(
                    node_name,
                    target,
                    length=length,
                    capacity=capacity,
                    edge_type="hall_to_gate",
                )

# ==============================================================================
# 1. 严格的线路检测器 (已恢复：nx.has_path 终极物理连通性检验)
# ==============================================================================
def get_real_active_lines(G):
    """极其严格的线路存活判定：节点必须存在，且拓扑必须物理连通至出口"""
    active_count = 0
    exits = [n for n, d in G.nodes(data=True) if d.get('type') == 'exit']

    if not exits:
        raise ValueError("\n[拓扑致命错误] 整个图中没有任何出口 (exit) 节点！")

    for line_id, spec in PLATFORM_VERTICAL_SPECS.items():
        p_node = spec["platform_node"]

        # 1. 如果连站台节点都没有，说明这条线完全没配，正常忽略
        if p_node not in G.nodes:
            print(f"⚠️ 忽略: 线路 {line_id} 未接入 (无站台节点)。")
            continue

        # 2. 终极连通性检验：站台是否能通达至少一个出口？
        is_connected = False
        for ext in exits:
            if nx.has_path(G, p_node, ext):
                is_connected = True
                break

        if is_connected:
            active_count += 1
            print(f"✔️ 检测到拓扑连通的有效线路: {line_id}")
        else:
            # 阻断式报错：有站台却没有连通出路，拓扑断裂！
            raise ValueError(
                f"\n[拓扑断裂致命错误] 线路 {line_id} 的站台已创建，但无法通达任何出口！请检查 EDGES_DATA 是否漏连了边！")

    return active_count


# ==============================================================================
# 2. 核心计算
# ==============================================================================
def get_delta_h(line_id):
    if line_id in STATION_LEVELS:
        return abs(STATION_LEVELS[line_id]["hall"] - STATION_LEVELS[line_id]["platform"])
    else:
        raise ValueError(f"\n[致命错误]：未找到线路 '{line_id}' 的标高配置！")



def calculate_gb_capacity_per_second(facility_type, width_or_count, direction="one_way"):
    cap_h = 0
    if facility_type == "stair":
        if direction in ["down", "stop down"]:
            cap_h = 4200 * width_or_count
        elif direction in ["up", "stop up"]:
            cap_h = 3700 * width_or_count
        else:
            cap_h = 3200 * width_or_count
    elif facility_type == "passageway":
        if direction in ["one_way", "up", "down", "out"]:
            cap_h = 5000 * width_or_count
        else:
            cap_h = 4000 * width_or_count
    elif facility_type == "escalator":
        if direction == "stop up":
            cap_h = 3900 * width_or_count
        elif direction == "stop down":
            cap_h = 4400 * width_or_count
        else:
            cap_h = 6720 * width_or_count
    elif "gate" in facility_type:
        count = width_or_count
        cap_h = 1200 * count if "tripod" in facility_type else 2500 * count
    else:
        cap_h = 5000 * width_or_count
    return cap_h / 3600.0


def fruin_speed(density):
    if density <= spr.PAPER_DENSITY_FREE:
        return spr.PAPER_FREE_SPEED
    if density <= spr.PAPER_DENSITY_JAM:
        return max(spr.PAPER_FREE_SPEED - spr.PAPER_DENSITY_SLOPE * density, 0.1)
    return 0.1


# ==============================================================================
# 3. 动态建图与改进放人引擎
# ==============================================================================


def _median_positive(values, default=None):
    positive = [float(v) for v in values if v is not None and float(v) > 0]
    if not positive:
        return default
    return float(statistics.median(positive))


def _estimate_virtual_representative_length(G, node):
    """为通道型 virtual 节点估算其代表长度，用于 area = width * length。

    virtual 节点代表“到达该节点前的一段通道空间”，所以优先使用入边长度。
    例如 Gate -> VN_L7_Corner_1，VN 的面积就按闸机到该 VN 的通道长度估算。
    """
    in_lengths = [
        float(G[pred][node].get("length", 0.0))
        for pred in G.predecessors(node)
        if float(G[pred][node].get("length", 0.0)) > 0
    ]
    out_lengths = [
        float(G[node][succ].get("length", 0.0))
        for succ in G.successors(node)
        if float(G[node][succ].get("length", 0.0)) > 0
    ]

    in_med = _median_positive(in_lengths)
    out_med = _median_positive(out_lengths)
    if in_med is not None:
        return in_med, "incoming_edge_median"
    if out_med is not None:
        return out_med, "outgoing_edge_median"
    return 2.0, "fallback_2m"


def _estimate_virtual_area(G, node):
    """为 virtual 节点估算局部节点面积。

    每条入边的通道面积会单独写入 edge_area，不在这里相加，避免多条路径
    部分重合时把同一片空间重复计入节点面积。
    """
    incident_areas = []
    for pred in G.predecessors(node):
        edge_data = G[pred][node]
        length = float(edge_data.get("length", 0.0))
        if length <= 0:
            continue
        width = edge_data.get("width_limit")
        if width is None or float(width) <= 0:
            width = G.nodes[node].get("width", 0.0)
        width = float(width)
        if width <= 0:
            continue
        edge_data["edge_area"] = length * width
        incident_areas.append(edge_data["edge_area"])

    for succ in G.successors(node):
        edge_data = G[node][succ]
        length = float(edge_data.get("length", 0.0))
        if length <= 0:
            continue
        width = edge_data.get("width_limit")
        if width is None or float(width) <= 0:
            width = G.nodes[node].get("downstream_width") or G.nodes[node].get("width", 0.0)
        width = float(width)
        if width <= 0:
            continue
        edge_data["edge_area"] = length * width
        incident_areas.append(edge_data["edge_area"])

    explicit_area = float(G.nodes[node].get("manual_area", 0.0) or 0.0)
    if explicit_area > 0:
        width = max(float(G.nodes[node].get("width", 1.0)), 0.1)
        return explicit_area, explicit_area / width, "manual_local_area"

    if incident_areas:
        local_area = max(min(incident_areas), 0.1)
        width = max(float(G.nodes[node].get("width", 1.0)), 0.1)
        return local_area, local_area / width, "fallback_min_incident_edge_area"

    representative_length, source = _estimate_virtual_representative_length(G, node)
    width = max(float(G.nodes[node].get("width", 1.0)), 0.1)
    return max(width * representative_length, 0.1), representative_length, source


def _auto_update_virtual_node_areas(G):
    """virtual 节点保留局部面积；相邻通道面积逐条写入边属性 edge_area。"""
    for node, data in G.nodes(data=True):
        if data.get("type") != "virtual":
            continue
        width = float(data.get("width", 0.0))
        if width <= 0:
            width = _median_positive(
                [G[pred][node].get("width_limit") for pred in G.predecessors(node)]
                + [G[node][succ].get("width_limit") for succ in G.successors(node)],
                default=1.0,
            )
        auto_area, representative_length, source = _estimate_virtual_area(G, node)
        data["representative_length"] = representative_length
        data["area"] = auto_area
        data["area_source"] = f"auto_virtual:{source}"


def build_graph():
    G = nx.DiGraph()

    # 1. 自动加平台与出口
    for name, attr in NODES_DATA.items():
        if isinstance(attr, dict) and attr.get("type") == "platform":
            G.add_node(name, **attr, people=0, capacity=999999)

    for name, attr in NODES_DATA.get("ALL_EXITS", {}).items():
        G.add_node(name, **attr, type="exit", people=0, area=100.0, capacity=float("inf"))

    # 2. 自动加其他所有设施 (安全解析字典)
    for group_name, items in NODES_DATA.items():
        if group_name.endswith("_VERTICALS") or group_name == "TRANSFERS":
            for name, attr in items.items():
                ftype, w, direction, pos = attr[0], attr[1], attr[2], attr[3]
                area = attr[4] if len(attr) == 5 else w * 2.0
                cap_s = calculate_gb_capacity_per_second(ftype, w, direction)
                G.add_node(name, pos=pos, type=ftype, width=w, capacity=cap_s, area=area, people=0)
        elif group_name.endswith("_GATES"):
            for name, attr in items.items():
                ftype, count, direction, pos = attr[0], attr[1], attr[2], attr[3]
                cap_s = calculate_gb_capacity_per_second(ftype, count)
                G.add_node(name, pos=pos, type=ftype, width=count, capacity=cap_s, area=count * 2.0, people=0)
        elif group_name.endswith("_VIRTUALS"):
            for name, attr in items.items():
                ftype, w_down, measured_area, pos = attr[0], attr[1], attr[2], attr[3]
                downstream_width = float(attr[4]) if len(attr) >= 5 else None
                cap_out = calculate_gb_capacity_per_second("passageway", w_down)
                G.add_node(
                    name,
                    pos=pos,
                    type=ftype,
                    width=w_down,
                    capacity=cap_out,
                    area=measured_area,
                    manual_area=measured_area,
                    downstream_width=downstream_width,
                    people=0,
                )

    # 3. 为需要细分的站台动态构建“等待区分区节点”
    _add_platform_waiting_zone_nodes_and_edges(G)

    # 4. 动态构建 站台->垂直设施 的边
    for line_id, spec in PLATFORM_VERTICAL_SPECS.items():
        platform_node = spec["platform_node"]
        vertical_group = spec["vertical_group"]

        if _platform_waiting_zone_defs_ready(line_id):
            continue

        if vertical_group not in NODES_DATA:
            raise ValueError(f"\n[配置致命错误] 线路 '{line_id}' 引用了不存在的垂直设施组 '{vertical_group}'！")

        delta_h = get_delta_h(line_id)

        for v_name in NODES_DATA[vertical_group].keys():
            if v_name not in PRECALCULATED_PLATFORM_DISTS:
                raise ValueError(f"\n[数据缺失]：字典中未找到 '{v_name}' 的距离，请检查 calc_platform_dists.py！")

            horizontal_dist = PRECALCULATED_PLATFORM_DISTS[v_name]
            total_edge_length = horizontal_dist + 2.0 * delta_h
            G.add_edge(platform_node, v_name, length=total_edge_length, capacity=G.nodes[v_name]["capacity"], edge_type="platform_to_vertical")

    # 5. 读取其余静态边
    CAD_TO_METER_SCALE = 0.01
    for e in EDGES_DATA:
        u, v, orig_dist, w_limit = e["u"], e["v"], e["length"], e.get("width_limit")
        edge_type = e.get("edge_type", "")

        if u not in G.nodes or v not in G.nodes:
            continue

        if edge_type in ["vertical_to_exit", "virtual_to_exit"]:
            line_key = None
            for key in sorted(STATION_LEVELS.keys(), key=len, reverse=True):
                if key in u:
                    line_key = key
                    break
            if line_key:
                hall_height = STATION_LEVELS[line_key]["hall"]
                stair_length = abs(hall_height - 0.0) * 2.0
                dist = stair_length + 2.0
            else:
                dist = 2.0
        elif orig_dist is None:
            pos_u = G.nodes[u].get("pos")
            pos_v = G.nodes[v].get("pos")
            if pos_u and pos_v:
                plane_dist = math.sqrt((pos_u[0] - pos_v[0]) ** 2 + (pos_u[1] - pos_v[1]) ** 2)
                dist = plane_dist * CAD_TO_METER_SCALE
            else:
                raise ValueError(f"\n[距离缺失致命错误] 边 {u} -> {v} 填了 None，但节点没有配置 pos 坐标！")
        else:
            dist = float(orig_dist)

        cap = min(G.nodes[u].get("capacity", float("inf")), G.nodes[v].get("capacity", float("inf")))
        if w_limit is not None:
            cap = min(cap, calculate_gb_capacity_per_second("passageway", w_limit))

        G.add_edge(u, v, length=dist, capacity=cap, edge_type=edge_type, width_limit=w_limit)
    _auto_update_virtual_node_areas(G)
    # =================================================================
    # 🌟 动态构建“列车车厢节点”与“车门瓶颈连线”
    # =================================================================
    for line_id, physics in TRAIN_PHYSICS.items():
        p_node = f"Platform_{line_id}"
        if p_node not in G.nodes:
            continue

        door_capacity = calculate_gb_capacity_per_second("passageway", physics["door_w"])
        car_area = physics["area_per_car"]
        door_count = max(int(physics.get("doors_per_car", 1)), 1)
        car_count = max(int(physics.get("cars", 1)), 1)
        train_count = max(int(physics.get("trains", 2)), 1)
        train_spans = physics.get("train_spans", [])
        platform_pos = G.nodes[p_node].get("pos", (0, 0))

        for train_idx in range(1, train_count + 1):
            train_span = train_spans[train_idx - 1] if train_idx - 1 < len(train_spans) else None

            for car_idx in range(1, car_count + 1):
                car_node = f"Train_{line_id}_{train_idx}_Car{car_idx}"
                car_pos = _layout_point_from_span(train_span, car_idx, 0, car_count, door_count, platform_pos)

                G.add_node(
                    car_node,
                    type="train_car",
                    capacity=999999,
                    area=car_area,
                    people=0,
                    pos=car_pos,
                    line_id=line_id,
                    train_index=train_idx,
                    car_index=car_idx,
                )

                door_specs = []
                if line_id == "Maglev":
                    band_spans = _maglev_band_spans_by_train().get(train_idx, {})
                    if band_spans:
                        side_door_count = max(door_count // max(len(band_spans), 1), 1)
                        door_seq = 1
                        for band_name, side_span in band_spans.items():
                            for side_door_idx in range(1, side_door_count + 1):
                                door_specs.append(
                                    {
                                        "door_index": door_seq,
                                        "band": band_name,
                                        "pos": _layout_point_from_span(
                                            side_span,
                                            car_idx,
                                            side_door_idx,
                                            car_count,
                                            side_door_count,
                                            platform_pos,
                                        ),
                                    }
                                )
                                door_seq += 1

                if not door_specs:
                    for door_idx in range(1, door_count + 1):
                        door_specs.append(
                            {
                                "door_index": door_idx,
                                "band": None,
                                "pos": _layout_point_from_span(
                                    train_span,
                                    car_idx,
                                    door_idx,
                                    car_count,
                                    door_count,
                                    platform_pos,
                                ),
                            }
                        )

                for door_spec in door_specs:
                    door_idx = int(door_spec["door_index"])
                    door_node = f"{car_node}_Door{door_idx}"
                    door_pos = door_spec["pos"]
                    wait_zone_name = _platform_waiting_zone_name(
                        line_id,
                        train_idx,
                        car_idx,
                        band=door_spec.get("band"),
                    )
                    door_target = wait_zone_name if wait_zone_name in G.nodes else p_node

                    G.add_node(
                        door_node,
                        type="train",
                        capacity=999999,
                        area=max(car_area / max(len(door_specs), 1), 1.0),
                        people=0,
                        pos=door_pos,
                        line_id=line_id,
                        train_index=train_idx,
                        car_index=car_idx,
                        door_index=door_idx,
                        waiting_band=door_spec.get("band"),
                    )

                    G.add_edge(
                        car_node,
                        door_node,
                        length=0.2,
                        capacity=door_capacity,
                        edge_type="car_to_door",
                    )
                    G.add_edge(
                        door_node,
                        door_target,
                        length=1.0,
                        capacity=door_capacity,
                        edge_type="train_door",
                    )

    _ensure_hall_staging_nodes(G)
    _apply_obstacle_areas(G)
    return G



def init_people(G, pop_dict, apply_noise=False, rng=None):
    # 重置清空
    for n in G.nodes():
        G.nodes[n]["people"] = 0
        G.nodes[n]["people_dict"] = {l: 0 for l in ALL_LINE_IDS}
        G.nodes[n]["source_group_dict"] = {}

    has_detailed_train = any(d.get("type") == "train_car" for _, d in G.nodes(data=True))

    for line_id, spec in PLATFORM_VERTICAL_SPECS.items():
        p_node = spec["platform_node"]
        if p_node in G.nodes and line_id in pop_dict:
            line_data = pop_dict[line_id]
            physics = TRAIN_PHYSICS.get(line_id, {})
            train_count = max(int(physics.get("trains", 2)), 1)

            # 1. 放入车厢
            if has_detailed_train:
                for train_idx in range(1, train_count + 1):
                    key = f"train_{train_idx}"
                    source_group_id = _source_group_id(line_id, key)
                    car_nodes = _sorted_train_car_nodes(G, line_id, train_idx)
                    total_people = int(round(float(line_data.get(key, 0))))

                    if not car_nodes or total_people <= 0:
                        continue

                    car_alloc = _integer_capped_allocation(total_people, [1.0] * len(car_nodes))
                    for car_node, assigned in zip(car_nodes, car_alloc):
                        if assigned <= 0:
                            continue
                        G.nodes[car_node]["people"] = assigned
                        G.nodes[car_node]["people_dict"][line_id] = assigned
                        G.nodes[car_node]["source_group_dict"][source_group_id] = assigned
            else:
                if f"Train_{line_id}_1" in G.nodes:
                    assigned = int(round(float(line_data.get("train_1", 0))))
                    G.nodes[f"Train_{line_id}_1"]["people"] = assigned
                    G.nodes[f"Train_{line_id}_1"]["people_dict"][line_id] = assigned
                    if assigned > 0:
                        G.nodes[f"Train_{line_id}_1"]["source_group_dict"][_source_group_id(line_id, "train_1")] = assigned
                if f"Train_{line_id}_2" in G.nodes:
                    assigned = int(round(float(line_data.get("train_2", 0))))
                    G.nodes[f"Train_{line_id}_2"]["people"] = assigned
                    G.nodes[f"Train_{line_id}_2"]["people_dict"][line_id] = assigned
                    if assigned > 0:
                        G.nodes[f"Train_{line_id}_2"]["source_group_dict"][_source_group_id(line_id, "train_2")] = assigned

            # 2. 放入【站台等待区】
            platform_waiting = int(round(float(line_data.get("platform_waiting", 0))))
            waiting_zone_defs = _platform_waiting_zone_defs(line_id)
            waiting_zone_nodes = _platform_waiting_zone_nodes(G, line_id)
            if waiting_zone_defs and waiting_zone_nodes:
                waiting_zone_source_groups = [
                    _platform_waiting_zone_source_group_id(line_id, zone_name)
                    for zone_name in waiting_zone_nodes
                ]
                _add_people_to_nodes_by_weights(
                    G,
                    waiting_zone_nodes,
                    line_id,
                    platform_waiting,
                    _platform_waiting_zone_area_weights(waiting_zone_defs),
                    source_group_ids=waiting_zone_source_groups,
                )
            else:
                G.nodes[p_node]["people"] = platform_waiting
                G.nodes[p_node]["people_dict"][line_id] = platform_waiting
                if platform_waiting > 0:
                    G.nodes[p_node]["source_group_dict"][_source_group_id(line_id, "platform_waiting")] = platform_waiting

            # 3. 放入【站厅闸机区】
            hall_people = int(round(float(line_data.get("hall_people", 0))))
            gate_group_name = spec.get("gate_group", f"{line_id}_GATES")
            valid_gates = [n for n in NODES_DATA.get(gate_group_name, {}) if n in G.nodes]

            if valid_gates and hall_people > 0:
                base_weights = [G.nodes[n].get("capacity", 1.0) for n in valid_gates]
                _add_people_to_nodes_by_weights(
                    G,
                    valid_gates,
                    line_id,
                    hall_people,
                    base_weights,
                    source_group_id=_source_group_id(line_id, "hall_people"),
                )

            # 4. 放入【换乘通道区】
            transfer_people = int(round(float(line_data.get("transfer_people", 0))))
            valid_transfers = _transfer_nodes_for_source_line(G, line_id)

            if valid_transfers and transfer_people > 0:
                base_weights = [G.nodes[n].get("capacity", 1.0) for n in valid_transfers]
                transfer_source_groups = [
                    _transfer_relation_source_group_id(line_id, node_name)
                    for node_name in valid_transfers
                ]
                _add_people_to_nodes_by_weights(
                    G,
                    valid_transfers,
                    line_id,
                    transfer_people,
                    base_weights,
                    source_group_ids=transfer_source_groups,
                )

    # 每次初始化都重置仿真时钟和在途队列，避免上一次运行残留影响本次结果
    G.graph["_sim_time"] = 0.0
    G.graph["_transit_queue"] = []
    G.graph["_edge_flow_credit"] = {}
    G.graph.pop("_arrival_queue", None)
    G.graph.pop("_single_path_case_line", None)
    G.graph.pop("_paper_blocked_signature", None)
    G.graph.pop("_paper_path_by_node", None)
    G.graph.pop("_paper_fixed_next_by_node", None)
    G.graph.pop("_our_guidance_state", None)



def apply_capacity_noise(G, rng, low=0.95, high=1.05):
    for u, v, edge_data in G.edges(data=True):
        if "capacity" in edge_data and edge_data["capacity"] != float("inf"):
            edge_data["capacity"] *= rng.uniform(low, high)


# ==============================================================================
# 4. 动态仿真与路径算法
# ==============================================================================
def get_best_next_node(G, current_node, method, shortest_dists):
    source_node = _representative_routing_source(G, current_node)
    return spr.get_best_next_node(G, source_node, method, shortest_dists, fruin_speed)


def get_best_path_to_exit(G, current_node, method, shortest_dists):
    source_node = _representative_routing_source(G, current_node)
    return spr.get_best_path_to_exit(G, source_node, method, shortest_dists, fruin_speed)

def simulate_to_time(G_base, pop_dict, method, target_time):
    G = copy.deepcopy(G_base)
    init_people(G, pop_dict, apply_noise=False)
    shortest_dists = dict(nx.all_pairs_dijkstra_path_length(G, weight="length"))

    time = 0
    while time < target_time:
        advance_simulation_step(G, method, shortest_dists)
        time += DELTA_T

    return G, shortest_dists



def format_path(path):
    if not path:
        return "N/A"
    return " -> ".join([n.replace("Platform_", "").replace("Gate_", "").replace("Exit_", "") for n in path])


def first_divergence(path_a, path_b):
    if not path_a or not path_b:
        return "N/A"
    n = min(len(path_a), len(path_b))
    for i in range(n):
        if path_a[i] != path_b[i]:
            return path_a[i]
    return "None"


def save_route_comparison_table(G_trad, G_guided, shortest_dists, source_nodes, filename, guided_method=OUR_SINGLE_PATH_METHOD):
    rows = []
    for src in source_nodes:
        trad_path = get_best_path_to_exit(G_trad, src, TRADITIONAL_METHOD, shortest_dists)
        guided_path = get_best_path_to_exit(G_guided, src, guided_method, shortest_dists)

        trad_len = _path_total_length(G_trad, trad_path) if trad_path else None
        guided_len = _path_total_length(G_guided, guided_path) if guided_path else None

        rows.append({
            "source": src,
            "traditional_path": format_path(trad_path),
            "guided_method": _method_display_name(guided_method),
            "guided_path": format_path(guided_path),
            "first_divergence": first_divergence(trad_path, guided_path),
            "trad_length": trad_len,
            "guided_length": guided_len,
            "length_reduction_pct": ((trad_len - guided_len) / trad_len * 100) if trad_len and guided_len and trad_len > 0 else 0.0
        })

    pd.DataFrame(rows).to_csv(filename, index=False, encoding="utf-8-sig")
    return rows


def rank_bottlenecks(G, metrics, top_k=10):
    rows = []
    node_stats = metrics.get("node_stats", {})
    for n, stat in node_stats.items():
        if G.nodes[n].get("type") == "exit":
            continue
        rows.append({
            "node": n,
            "type": G.nodes[n].get("type", ""),
            "peak_people": stat.get("peak_people", 0.0),
            "peak_density": stat.get("peak_density", 0.0),
            "queue_seconds": stat.get("queue_seconds", 0.0),
            "congestion_seconds": stat.get("congestion_seconds", 0.0)
        })

    rows.sort(key=lambda x: (x["queue_seconds"], x["peak_density"]), reverse=True)
    return rows[:top_k]

def rank_instantaneous_bottlenecks(G_state, top_k=10):
    """专门针对特定时刻切片的瞬时瓶颈排名，只看当下的排队人数和密度"""
    rows = []
    for n in G_state.nodes():
        if G_state.nodes[n].get("type") == "exit":
            continue
        ppl = G_state.nodes[n].get("people", 0)
        area = G_state.nodes[n].get("area", 1.0)
        density = ppl / max(area, 0.001)
        rows.append({
            "node": n,
            "type": G_state.nodes[n].get("type", ""),
            "instant_people": ppl,
            "instant_density": density
        })
    # 按瞬时排队人数降序排列
    rows.sort(key=lambda x: x["instant_density"], reverse=True)
    return rows[:top_k]

def advance_simulation_step(G, method, shortest_dists):
    """推进单个仿真步。支持在途旅行时间与多后继分流。"""
    current_time, _ = _ensure_transit_state(G)
    _process_transit_arrivals(G, current_time)

    moves = get_step_moves(G, method, shortest_dists)
    _schedule_moves_as_transit(G, moves)

    G.graph["_sim_time"] = current_time + DELTA_T
    return moves



def collect_route_event_log(
    G_base,
    pop_dict,
    source_nodes,
    target_time,
    filename,
    compare_method=OUR_SINGLE_PATH_METHOD,
    verbose=False,
):
    """只记录“路由发生变化”的事件，不记录每一秒。"""
    G_trad = copy.deepcopy(G_base)
    G_guided = copy.deepcopy(G_base)

    init_people(G_trad, pop_dict, apply_noise=False)
    init_people(G_guided, pop_dict, apply_noise=False)

    shortest_dists = dict(nx.all_pairs_dijkstra_path_length(G_base, weight="length"))
    prev_trad = {src: None for src in source_nodes}
    prev_guided = {src: None for src in source_nodes}
    rows = []

    time = 0
    while time <= target_time:
        trad_hot = rank_instantaneous_bottlenecks(G_trad, top_k=1)
        guided_hot = rank_instantaneous_bottlenecks(G_guided, top_k=1)

        trad_hot_node = trad_hot[0]["node"] if trad_hot else None
        trad_hot_people = trad_hot[0]["instant_people"] if trad_hot else 0.0
        trad_hot_density = trad_hot[0]["instant_density"] if trad_hot else 0.0

        guided_hot_node = guided_hot[0]["node"] if guided_hot else None
        guided_hot_people = guided_hot[0]["instant_people"] if guided_hot else 0.0
        guided_hot_density = guided_hot[0]["instant_density"] if guided_hot else 0.0

        for src in source_nodes:
            line = src.split("_")[1] if "_" in src else src

            trad_path = get_best_path_to_exit(G_trad, src, TRADITIONAL_METHOD, shortest_dists)
            guided_path = get_best_path_to_exit(G_guided, src, compare_method, shortest_dists)

            trad_next = trad_path[1] if trad_path and len(trad_path) > 1 else None
            guided_next = guided_path[1] if guided_path and len(guided_path) > 1 else None

            trad_changed = trad_next != prev_trad[src]
            guided_changed = guided_next != prev_guided[src]
            route_diverged = trad_next != guided_next

            if time == 0:
                event_type = "initial"
            else:
                flags = []
                if trad_changed:
                    flags.append("trad_change")
                if guided_changed:
                    flags.append("guided_change")
                if route_diverged:
                    flags.append("diverged")
                if not flags:
                    prev_trad[src] = trad_next
                    prev_guided[src] = guided_next
                    continue
                event_type = "+".join(flags)

            trad_next_people = G_trad.nodes[trad_next].get("people", 0.0) if trad_next in G_trad.nodes else 0.0
            guided_next_people = G_guided.nodes[guided_next].get("people", 0.0) if guided_next in G_guided.nodes else 0.0

            trad_next_density = trad_next_people / max(G_trad.nodes[trad_next].get("area", 1.0), 0.001) if trad_next in G_trad.nodes else 0.0
            guided_next_density = guided_next_people / max(G_guided.nodes[guided_next].get("area", 1.0), 0.001) if guided_next in G_guided.nodes else 0.0

            trad_len = _path_total_length(G_trad, trad_path) if trad_path else None
            guided_len = _path_total_length(G_guided, guided_path) if guided_path else None

            reason = "same-route"
            if route_diverged and trad_next and guided_next:
                if guided_next_density < trad_next_density:
                    reason = "guided_detour_lower_density"
                elif guided_next_density < trad_hot_density:
                    reason = "guided_avoids_traditional_bottleneck"
                else:
                    reason = "guided_reroute"
            elif trad_changed and not guided_changed:
                reason = "traditional_changed_only"
            elif guided_changed and not trad_changed:
                reason = "guided_changed_only"

            rows.append({
                "time": time,
                "line": line,
                "source": src,
                "event_type": event_type,
                "traditional_prev_next": prev_trad[src],
                "traditional_curr_next": trad_next,
                "guided_prev_next": prev_guided[src],
                "guided_curr_next": guided_next,
                "route_diverged": route_diverged,
                "traditional_path": format_path(trad_path),
                "guided_method": _method_display_name(compare_method),
                "guided_path": format_path(guided_path),
                "first_divergence": first_divergence(trad_path, guided_path),
                "trad_path_length": trad_len,
                "guided_path_length": guided_len,
                "trad_next_people": trad_next_people,
                "guided_next_people": guided_next_people,
                "trad_next_density": trad_next_density,
                "guided_next_density": guided_next_density,
                "trad_bottleneck_node": trad_hot_node,
                "trad_bottleneck_people": trad_hot_people,
                "trad_bottleneck_density": trad_hot_density,
                "guided_bottleneck_node": guided_hot_node,
                "guided_bottleneck_people": guided_hot_people,
                "guided_bottleneck_density": guided_hot_density,
                "reason": reason
            })

            if verbose and event_type != "initial":
                print(
                    f"[T={int(time)}s] {src} | Trad={trad_next or 'None'} | Guided={guided_next or 'None'} | "
                    f"分叉={route_diverged} | 传统瓶颈={trad_hot_node or 'None'} | 引导瓶颈={guided_hot_node or 'None'}"
                )

            prev_trad[src] = trad_next
            prev_guided[src] = guided_next

        advance_simulation_step(G_trad, TRADITIONAL_METHOD, shortest_dists)
        advance_simulation_step(G_guided, compare_method, shortest_dists)
        def still_has_people(G):
            return any(
                G.nodes[n].get("people", 0) > 0.1 and G.nodes[n].get("type") != "exit"
                for n in G.nodes()
            )

        if not still_has_people(G_trad) and not still_has_people(G_guided):
            break

        time += DELTA_T

    route_log_df = pd.DataFrame(rows)
    route_log_df.to_csv(filename, index=False, encoding="utf-8-sig")
    return route_log_df, G_trad, G_guided, shortest_dists


def collect_route_event_log_three_methods(
    G_base,
    pop_dict,
    source_nodes,
    target_time,
    filename,
    verbose=False,
):
    """三算法同场记录换路与分叉事件：ACO / ImprovedAStar / OurSinglePath。"""
    method_specs = [
        ("aco", ANT_COLONY_METHOD),
        ("paper", PAPER_SINGLE_PATH_METHOD),
        ("our", OUR_SINGLE_PATH_METHOD),
    ]
    states = {}
    prev_next = {}
    for key, method in method_specs:
        state = copy.deepcopy(G_base)
        init_people(state, pop_dict, apply_noise=False)
        states[key] = state
        prev_next[key] = {src: None for src in source_nodes}

    shortest_dists = dict(nx.all_pairs_dijkstra_path_length(G_base, weight="length"))
    rows = []
    time = 0

    while time <= target_time:
        hot_map = {
            key: rank_instantaneous_bottlenecks(state, top_k=1)
            for key, state in states.items()
        }

        for src in source_nodes:
            line = src.split("_")[1] if "_" in src else src
            path_map = {}
            next_map = {}
            changed_map = {}
            next_people_map = {}
            next_density_map = {}
            path_len_map = {}

            for key, method in method_specs:
                state = states[key]
                # 核心修改：ACO 也要实时计算寻路，而不是去 recover fixed path
                if key == "aco":
                    path = standard_aco_pathfinder(state, src, shortest_dists, fruin_speed)
                else:
                    path = get_best_path_to_exit(state, src, method, shortest_dists)
                next_hop = path[1] if path and len(path) > 1 else None
                path_map[key] = path
                next_map[key] = next_hop
                changed_map[key] = next_hop != prev_next[key][src]
                path_len_map[key] = _path_total_length(state, path) if path else None
                next_people_map[key] = state.nodes[next_hop].get("people", 0.0) if next_hop in state.nodes else 0.0
                next_density_map[key] = (
                    next_people_map[key] / max(state.nodes[next_hop].get("area", 1.0), 0.001)
                    if next_hop in state.nodes else 0.0
                )

            aco_vs_paper = next_map["aco"] != next_map["paper"]
            aco_vs_our = next_map["aco"] != next_map["our"]
            paper_vs_our = next_map["paper"] != next_map["our"]

            if time == 0:
                event_type = "initial"
            else:
                flags = []
                if changed_map["aco"]:
                    flags.append("aco_change")
                if changed_map["paper"]:
                    flags.append("paper_change")
                if changed_map["our"]:
                    flags.append("our_change")
                if aco_vs_paper:
                    flags.append("aco_vs_paper")
                if aco_vs_our:
                    flags.append("aco_vs_our")
                if paper_vs_our:
                    flags.append("paper_vs_our")
                if not flags:
                    for key, _ in method_specs:
                        prev_next[key][src] = next_map[key]
                    continue
                event_type = "+".join(flags)

            aco_hot = hot_map["aco"][0] if hot_map["aco"] else {}
            paper_hot = hot_map["paper"][0] if hot_map["paper"] else {}
            our_hot = hot_map["our"][0] if hot_map["our"] else {}

            rows.append({
                "time": time,
                "line": line,
                "source": src,
                "event_type": event_type,
                "aco_prev_next": prev_next["aco"][src],
                "aco_curr_next": next_map["aco"],
                "paper_prev_next": prev_next["paper"][src],
                "paper_curr_next": next_map["paper"],
                "our_prev_next": prev_next["our"][src],
                "our_curr_next": next_map["our"],
                "aco_vs_paper_diverged": aco_vs_paper,
                "aco_vs_our_diverged": aco_vs_our,
                "paper_vs_our_diverged": paper_vs_our,
                "aco_path": format_path(path_map["aco"]),
                "paper_path": format_path(path_map["paper"]),
                "our_path": format_path(path_map["our"]),
                "first_divergence_aco_vs_paper": first_divergence(path_map["aco"], path_map["paper"]),
                "first_divergence_aco_vs_our": first_divergence(path_map["aco"], path_map["our"]),
                "first_divergence_paper_vs_our": first_divergence(path_map["paper"], path_map["our"]),
                "aco_path_length": path_len_map["aco"],
                "paper_path_length": path_len_map["paper"],
                "our_path_length": path_len_map["our"],
                "aco_next_people": next_people_map["aco"],
                "paper_next_people": next_people_map["paper"],
                "our_next_people": next_people_map["our"],
                "aco_next_density": next_density_map["aco"],
                "paper_next_density": next_density_map["paper"],
                "our_next_density": next_density_map["our"],
                "aco_bottleneck_node": aco_hot.get("node"),
                "aco_bottleneck_people": aco_hot.get("instant_people", 0.0),
                "aco_bottleneck_density": aco_hot.get("instant_density", 0.0),
                "paper_bottleneck_node": paper_hot.get("node"),
                "paper_bottleneck_people": paper_hot.get("instant_people", 0.0),
                "paper_bottleneck_density": paper_hot.get("instant_density", 0.0),
                "our_bottleneck_node": our_hot.get("node"),
                "our_bottleneck_people": our_hot.get("instant_people", 0.0),
                "our_bottleneck_density": our_hot.get("instant_density", 0.0),
            })

            if verbose and event_type != "initial":
                print(
                    f"[T={int(time)}s] {src} | ACO={next_map['aco'] or 'None'} | "
                    f"Paper={next_map['paper'] or 'None'} | Our={next_map['our'] or 'None'}"
                )

            for key, _ in method_specs:
                prev_next[key][src] = next_map[key]

        for key, method in method_specs:
            advance_simulation_step(states[key], method, shortest_dists)

        def still_has_people(G):
            return any(
                G.nodes[n].get("people", 0) > 0.1 and G.nodes[n].get("type") != "exit"
                for n in G.nodes()
            )

        if not any(still_has_people(state) for state in states.values()):
            break

        time += DELTA_T

    route_log_df = pd.DataFrame(rows)
    route_log_df.to_csv(filename, index=False, encoding="utf-8-sig")
    return route_log_df, states, shortest_dists


def summarize_bottlenecks_from_events(route_df, method_prefix, filename):
    """把事件日志汇总成瓶颈统计，不再依赖单一时刻快照。"""
    if method_prefix in {"aco", "trad"}:
        node_col = "aco_bottleneck_node" if "aco_bottleneck_node" in route_df.columns else "trad_bottleneck_node"
        people_col = "aco_bottleneck_people" if "aco_bottleneck_people" in route_df.columns else "trad_bottleneck_people"
        density_col = "aco_bottleneck_density" if "aco_bottleneck_density" in route_df.columns else "trad_bottleneck_density"
        if "aco_vs_paper_diverged" in route_df.columns:
            event_mask = route_df["aco_vs_paper_diverged"] | route_df["aco_vs_our_diverged"]
        elif "trad_vs_paper_diverged" in route_df.columns:
            event_mask = route_df["trad_vs_paper_diverged"] | route_df["trad_vs_our_diverged"]
        else:
            event_mask = route_df["route_diverged"]
    elif method_prefix == "paper":
        node_col = "paper_bottleneck_node"
        people_col = "paper_bottleneck_people"
        density_col = "paper_bottleneck_density"
        if "aco_vs_paper_diverged" in route_df.columns:
            event_mask = route_df["aco_vs_paper_diverged"] | route_df["paper_vs_our_diverged"]
        else:
            event_mask = route_df["trad_vs_paper_diverged"] | route_df["paper_vs_our_diverged"]
    elif method_prefix == "our":
        node_col = "our_bottleneck_node"
        people_col = "our_bottleneck_people"
        density_col = "our_bottleneck_density"
        if "aco_vs_our_diverged" in route_df.columns:
            event_mask = route_df["aco_vs_our_diverged"] | route_df["paper_vs_our_diverged"]
        else:
            event_mask = route_df["trad_vs_our_diverged"] | route_df["paper_vs_our_diverged"]
    else:
        node_col = "guided_bottleneck_node"
        people_col = "guided_bottleneck_people"
        density_col = "guided_bottleneck_density"
        event_mask = route_df["route_diverged"]

    df = route_df[event_mask].copy()
    if df.empty:
        empty = pd.DataFrame(columns=["node", "hit_count", "avg_people", "avg_density", "first_time", "last_time"])
        empty.to_csv(filename, index=False, encoding="utf-8-sig")
        return empty

    summary = df.groupby(node_col).agg(
        hit_count=("source", "count"),
        avg_people=(people_col, "mean"),
        avg_density=(density_col, "mean"),
        first_time=("time", "min"),
        last_time=("time", "max")
    ).reset_index().rename(columns={node_col: "node"})

    summary = summary.sort_values(["hit_count", "avg_density"], ascending=False)
    summary.to_csv(filename, index=False, encoding="utf-8-sig")
    return summary


def summarize_route_changes_by_line(route_df, filename):
    """按线路汇总分叉与换路事件，避免图里只剩一条线。"""
    df = route_df[route_df["event_type"] != "initial"].copy()
    if df.empty:
        empty = pd.DataFrame(columns=["line", "event_count", "source_count", "first_time", "last_time"])
        empty.to_csv(filename, index=False, encoding="utf-8-sig")
        return empty

    if "aco_vs_paper_diverged" in df.columns:
        summary = df.groupby("line").agg(
            event_count=("source", "count"),
            source_count=("source", "nunique"),
            aco_change_count=("aco_curr_next", lambda s: int(df.loc[s.index, "event_type"].str.contains("aco_change").sum())),
            paper_change_count=("paper_curr_next", lambda s: int(df.loc[s.index, "event_type"].str.contains("paper_change").sum())),
            our_change_count=("our_curr_next", lambda s: int(df.loc[s.index, "event_type"].str.contains("our_change").sum())),
            aco_vs_paper_divergence=("aco_vs_paper_diverged", "sum"),
            aco_vs_our_divergence=("aco_vs_our_diverged", "sum"),
            paper_vs_our_divergence=("paper_vs_our_diverged", "sum"),
            first_time=("time", "min"),
            last_time=("time", "max")
        ).reset_index()
    elif "trad_vs_paper_diverged" in df.columns:
        summary = df.groupby("line").agg(
            event_count=("source", "count"),
            source_count=("source", "nunique"),
            trad_change_count=("traditional_curr_next", lambda s: int(df.loc[s.index, "event_type"].str.contains("trad_change").sum())),
            paper_change_count=("paper_curr_next", lambda s: int(df.loc[s.index, "event_type"].str.contains("paper_change").sum())),
            our_change_count=("our_curr_next", lambda s: int(df.loc[s.index, "event_type"].str.contains("our_change").sum())),
            trad_vs_paper_divergence=("trad_vs_paper_diverged", "sum"),
            trad_vs_our_divergence=("trad_vs_our_diverged", "sum"),
            paper_vs_our_divergence=("paper_vs_our_diverged", "sum"),
            first_time=("time", "min"),
            last_time=("time", "max")
        ).reset_index()
    else:
        summary = df.groupby("line").agg(
            event_count=("source", "count"),
            source_count=("source", "nunique"),
            first_time=("time", "min"),
            last_time=("time", "max")
        ).reset_index()

    summary = summary.sort_values(["event_count", "source_count"], ascending=False)
    summary.to_csv(filename, index=False, encoding="utf-8-sig")
    return summary


def plot_divergence_timeline(route_log_df, filename, bin_size=10):
    """按时间窗聚合分叉次数，不要每秒抖一次。"""
    if route_log_df.empty:
        return

    if "aco_vs_paper_diverged" in route_log_df.columns:
        df = route_log_df[route_log_df["event_type"] != "initial"].copy()
        if df.empty:
            return

        df["time_bin"] = (df["time"] // bin_size) * bin_size
        timeline = df.groupby("time_bin").agg(
            aco_vs_paper=("aco_vs_paper_diverged", "sum"),
            aco_vs_our=("aco_vs_our_diverged", "sum"),
            paper_vs_our=("paper_vs_our_diverged", "sum"),
        ).reset_index()

        plt.figure(figsize=(10, 5))
        plt.plot(timeline["time_bin"], timeline["aco_vs_paper"], "o-", linewidth=2, label="ACO vs ImprovedAStar")
        plt.plot(timeline["time_bin"], timeline["aco_vs_our"], "s-", linewidth=2, label="ACO vs OurSinglePath")
        plt.plot(timeline["time_bin"], timeline["paper_vs_our"], "^-", linewidth=2, label="ImprovedAStar vs OurSinglePath")
        plt.xlabel(f"时间窗 (s, {bin_size}s 聚合)")
        plt.ylabel("发生分叉的源点数")
        plt.title("三算法分叉时间线", fontweight="bold")
        plt.grid(True, linestyle=":", alpha=0.7)
        plt.legend()
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()
    elif "trad_vs_paper_diverged" in route_log_df.columns:
        df = route_log_df[route_log_df["event_type"] != "initial"].copy()
        if df.empty:
            return

        df["time_bin"] = (df["time"] // bin_size) * bin_size
        timeline = df.groupby("time_bin").agg(
            trad_vs_paper=("trad_vs_paper_diverged", "sum"),
            trad_vs_our=("trad_vs_our_diverged", "sum"),
            paper_vs_our=("paper_vs_our_diverged", "sum"),
        ).reset_index()

        plt.figure(figsize=(10, 5))
        plt.plot(timeline["time_bin"], timeline["trad_vs_paper"], "o-", linewidth=2, label="Traditional vs ImprovedAStar")
        plt.plot(timeline["time_bin"], timeline["trad_vs_our"], "s-", linewidth=2, label="Traditional vs OurSinglePath")
        plt.plot(timeline["time_bin"], timeline["paper_vs_our"], "^-", linewidth=2, label="ImprovedAStar vs OurSinglePath")
        plt.xlabel(f"时间窗 (s, {bin_size}s 聚合)")
        plt.ylabel("发生分叉的源点数")
        plt.title("三算法分叉时间线", fontweight="bold")
        plt.grid(True, linestyle=":", alpha=0.7)
        plt.legend()
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()
    else:
        df = route_log_df[route_log_df["route_diverged"] & (route_log_df["event_type"] != "initial")].copy()
        if df.empty:
            return

        df["time_bin"] = (df["time"] // bin_size) * bin_size
        timeline = df.groupby("time_bin").size().reset_index(name="divergence_count")

        plt.figure(figsize=(10, 5))
        plt.plot(timeline["time_bin"], timeline["divergence_count"], "b-o", linewidth=2)
        plt.xlabel(f"时间窗 (s, {bin_size}s 聚合)")
        plt.ylabel("发生分叉的源点数")
        plt.title("分叉时间线", fontweight="bold")
        plt.grid(True, linestyle=":", alpha=0.7)
        plt.savefig(filename, dpi=300, bbox_inches="tight")
        plt.close()



def plot_route_highlight(G_base, source, trad_path, imp_path, filename, total_people=None, obs_window=None):
    plt.figure(figsize=(16, 10))
    visible_nodes = [n for n, data in G_base.nodes(data=True) if not _is_hidden_visual_node(data)]
    H = G_base.subgraph(visible_nodes).copy()
    pos = nx.get_node_attributes(H, "pos")

    nx.draw_networkx_edges(H, pos, edge_color="#CFCFCF", width=1.0, alpha=0.35, arrows=True)
    nx.draw_networkx_nodes(H, pos, node_color="#E6E6E6", node_size=400, edgecolors="black", linewidths=0.6)

    if trad_path and len(trad_path) > 1:
        trad_edges = [(u, v) for u, v in zip(trad_path, trad_path[1:]) if u in H.nodes and v in H.nodes]
        nx.draw_networkx_edges(H, pos, edgelist=trad_edges, edge_color="red", width=3.0, style="dashed", arrows=True)

    if imp_path and len(imp_path) > 1:
        imp_edges = [(u, v) for u, v in zip(imp_path, imp_path[1:]) if u in H.nodes and v in H.nodes]
        nx.draw_networkx_edges(H, pos, edgelist=imp_edges, edge_color="blue", width=3.5, style="solid", arrows=True)

    labels = {}
    for n in H.nodes():
        if n == source or H.nodes[n].get("type") in {"exit", "gate"}:
            labels[n] = n.replace("Platform_", "").replace("Gate_", "").replace("Exit_", "")

    nx.draw_networkx_labels(H, pos, labels=labels, font_size=8, font_weight="bold")

    line_code = source.split("_")[1] if "_" in source else source
    title_bits = [f"路径对比 - {source}", f"线路 {line_code}"]
    if total_people is not None:
        title_bits.append(f"{total_people}人总规模")
    if obs_window is not None:
        title_bits.append(f"观测窗 0-{obs_window}s")

    plt.title(" | ".join(title_bits), fontsize=15, fontweight="bold")
    plt.legend(
        handles=[
            mpatches.Patch(color="red", label="Traditional: red dashed"),
            mpatches.Patch(color="blue", label="OurSinglePath: blue solid")
        ],
        loc="upper right"
    )
    plt.gca().set_aspect('equal', adjustable='datalim')
    plt.axis("off")
    plt.savefig(filename, dpi=300, bbox_inches="tight")
    plt.close()


def execute_moves(G, moves, evacuated_by_line=None, exit_usage_dict=None):
    """把本步流量放入在途队列，真正的到达在后续按 travel_time 处理。"""
    _schedule_moves_as_transit(G, moves)
    return 0.0


def generate_snapshots_for_method(G_base, pop_dict, method, time_points):
    G = G_base.copy()
    init_people(G, pop_dict, apply_noise=False)
    shortest_dists = dict(nx.all_pairs_dijkstra_path_length(G, weight="length"))

    time = 0
    max_time = max(time_points)
    snapshots = {}

    while time <= max_time:
        for tp in time_points:
            if abs(time - tp) < DELTA_T / 2:
                snapshots[tp] = {n: G.nodes[n].get("people", 0) for n in G.nodes()}

        advance_simulation_step(G, method, shortest_dists)
        time += DELTA_T

    return snapshots


def run_robustness_experiment(G_base, pop_per_line, method=OUR_SINGLE_PATH_METHOD, runs=10, seed=42):
    active_lines = get_real_active_lines(G_base)
    print(f"\n🔬 启动 {method} 算法鲁棒性测试 (全站总计:{pop_per_line * active_lines}人, 迭代:{runs}次)...")

    results_time, results_queue, results_exposure, results_speed = [], [], [], []

    for i in range(runs):
        rng = random.Random(None if seed is None else seed + i)
        G_noisy = copy.deepcopy(G_base)
        apply_capacity_noise(G_noisy, rng, 0.95, 1.05)

        metrics = run_simulation_for_metrics(
            G_noisy,
            pop_per_line,
            method=method,
            apply_noise=True,
            rng=rng,
        )


        results_time.append(metrics["time"])
        results_queue.append(metrics["queueing_time"])
        results_exposure.append(metrics["congestion_exposure_time"] / 1000)
        results_speed.append(metrics["avg_speed"])

    mean_t, std_t = statistics.mean(results_time), statistics.stdev(results_time) if runs > 1 else 0.0
    mean_q, std_q = statistics.mean(results_queue), statistics.stdev(results_queue) if runs > 1 else 0.0
    mean_e, std_e = statistics.mean(results_exposure), statistics.stdev(results_exposure) if runs > 1 else 0.0
    mean_s, std_s = statistics.mean(results_speed), statistics.stdev(results_speed) if runs > 1 else 0.0

    return mean_t, std_t, mean_q, std_q, mean_e, std_e, mean_s, std_s


# ==============================================================================
# 5. 绘图与主流程
# ==============================================================================
def plot_initial_topology(G):
    # 只调整视觉呈现，不修改任何节点坐标。
    fig, ax = plt.subplots(figsize=(30, 42))
    visible_nodes = [
        n for n, data in G.nodes(data=True)
        if not _is_hidden_visual_node(data)
    ]
    H = G.subgraph(visible_nodes).copy()
    pos = nx.get_node_attributes(H, 'pos')
    display_pos = {n: (float(p[0]), float(p[1])) for n, p in pos.items()}

    # 真实坐标下很多设施点间距极小，论文图会糊成一团。
    # 这里仅生成绘图用坐标副本，把近距离节点轻微错开；G.nodes[n]["pos"] 不会被修改。
    min_gap = 260.0
    anchor_strength = 0.08
    nodes_for_layout = list(display_pos.keys())
    original_pos = {n: display_pos[n] for n in nodes_for_layout}
    for _ in range(40):
        shifts = {n: [0.0, 0.0] for n in nodes_for_layout}
        for i, u in enumerate(nodes_for_layout):
            x1, y1 = display_pos[u]
            for v in nodes_for_layout[i + 1:]:
                x2, y2 = display_pos[v]
                dx, dy = x2 - x1, y2 - y1
                dist = math.hypot(dx, dy)
                if dist >= min_gap:
                    continue
                if dist < 1e-6:
                    dx = ((i % 7) - 3) or 1
                    dy = (((i // 7) % 7) - 3) or 1
                    dist = math.hypot(dx, dy)
                push = (min_gap - dist) * 0.5
                ux, uy = dx / dist, dy / dist
                shifts[u][0] -= ux * push
                shifts[u][1] -= uy * push
                shifts[v][0] += ux * push
                shifts[v][1] += uy * push

        for n in nodes_for_layout:
            x, y = display_pos[n]
            ox, oy = original_pos[n]
            display_pos[n] = (
                x + shifts[n][0] + anchor_strength * (ox - x),
                y + shifts[n][1] + anchor_strength * (oy - y),
            )

    color_map = []
    node_sizes = []
    for n in H.nodes():
        t = H.nodes[n].get('type', '')
        if 'platform' in t:
            color_map.append('#E53935')
            node_sizes.append(520)
        elif 'exit' in t:
            color_map.append('#34C759')
            node_sizes.append(430)
        elif 'gate' in t:
            color_map.append('#FFC107')
            node_sizes.append(250)
        elif 'stair' in t or 'escalator' in t:
            color_map.append('#1E88E5')
            node_sizes.append(220)
        elif 'virtual' in t:
            color_map.append('#8E63CE')
            node_sizes.append(210)
        else:
            color_map.append('#8E63CE')
            node_sizes.append(170)

    for n, (ox, oy) in original_pos.items():
        x, y = display_pos[n]
        if math.hypot(x - ox, y - oy) > 60:
            ax.plot([ox, x], [oy, y], color='#D0D0D0', linewidth=0.45, alpha=0.35, zorder=0)

    nx.draw_networkx_edges(
        H,
        display_pos,
        ax=ax,
        edge_color='#9A9A9A',
        arrows=True,
        width=0.7,
        arrowsize=5,
        alpha=0.18,
        connectionstyle='arc3,rad=0.08',
        min_source_margin=2,
        min_target_margin=2,
    )
    nx.draw_networkx_nodes(
        H,
        display_pos,
        ax=ax,
        node_color=color_map,
        node_size=node_sizes,
        edgecolors='black',
        linewidths=0.75,
        alpha=0.96,
    )

    labels = {
        n: n.split('_')[-1]
        for n in H.nodes()
        if H.nodes[n].get('type') in ['platform', 'exit']
    }
    nx.draw_networkx_labels(
        G,
        display_pos,
        labels=labels,
        ax=ax,
        font_size=7,
        font_weight='bold',
        bbox=dict(boxstyle='round,pad=0.10', facecolor='white', edgecolor='none', alpha=0.78),
    )

    legend_handles = [
        plt.Line2D([0], [0], marker='o', color='w', label='站台', markerfacecolor='#E53935', markeredgecolor='black', markersize=11),
        plt.Line2D([0], [0], marker='o', color='w', label='楼梯/扶梯', markerfacecolor='#1E88E5', markeredgecolor='black', markersize=9),
        plt.Line2D([0], [0], marker='o', color='w', label='闸机', markerfacecolor='#FFC107', markeredgecolor='black', markersize=9),
        plt.Line2D([0], [0], marker='o', color='w', label='通道/虚拟节点', markerfacecolor='#8E63CE', markeredgecolor='black', markersize=9),
        plt.Line2D([0], [0], marker='o', color='w', label='出口', markerfacecolor='#34C759', markeredgecolor='black', markersize=10),
    ]
    ax.legend(handles=legend_handles, loc='upper left', frameon=True, framealpha=0.9, fontsize=12)

    ax.set_title('龙阳路枢纽初始物理拓扑（视觉展开版，原始坐标未修改）', fontsize=24, fontweight='bold', pad=18)
    ax.set_aspect('equal', adjustable='datalim')
    ax.margins(x=0.08, y=0.08)
    ax.axis('off')

    fig.savefig("01_initial_topology.png", dpi=400, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def plot_comparative_snapshots(G_base, pop_dict, time_points=[20, 80, 150], methods=None):
    methods = methods or [
        ("ACO", ANT_COLONY_METHOD, "ACO (蚁群优化基线)"),
        ("ImprovedAStar", PAPER_SINGLE_PATH_METHOD, "ImprovedAStar (文献改进A*)"),
        ("OurSinglePath", OUR_SINGLE_PATH_METHOD, "OurSinglePath (动态单路径方法)"),
    ]
    print(f"\n🎬 正在生成多算法热力演化快照 (T={time_points}s)...")
    snapshots_by_label = {
        label: generate_snapshots_for_method(G_base, pop_dict, method, time_points)
        for label, method, _ in methods
    }

    visible_nodes = [n for n, data in G_base.nodes(data=True) if not _is_hidden_visual_node(data)]
    H = G_base.subgraph(visible_nodes).copy()
    pos = nx.get_node_attributes(H, 'pos')
    total_p = sum(sum(d.values()) for d in pop_dict.values())

    for tp in time_points:
        fig, axes = plt.subplots(1, len(methods), figsize=(16 * len(methods), 18))
        fig.suptitle(f'疏散时空拥挤演化对比 (T = {tp}s, 总规模: {total_p}人)', fontsize=30, fontweight='bold', y=0.98)
        axes = np.atleast_1d(axes).flatten()
        methods_data = [(title, snapshots_by_label[label][tp]) for label, _, title in methods]

        for idx, (title, node_people) in enumerate(methods_data):
            ax = axes[idx]
            ax.set_title(title, fontsize=24, pad=15)
            nx.draw_networkx_edges(H, pos, ax=ax, edge_color='#B0B0B0', width=1.5, alpha=0.4, arrowsize=8)

            node_colors, node_sizes, labels = [], [], {}
            for n in H.nodes():
                ppl = _visual_people_at_node(G_base, n, node_people)
                cap = max(H.nodes[n].get('capacity', 1.0), 0.001)
                node_colors.append(ppl / cap)

                # 🌟 优化热力图圆圈：基础变大，随人数增长更平滑
                base_size = 200 if H.nodes[n].get('type') == 'platform' else 80
                size = base_size + math.sqrt(ppl) * 20
                node_sizes.append(size)

                # 阈值调高一点，图面更清爽
                if ppl > 20:
                    labels[n] = f"{int(ppl)}"


            nodes = nx.draw_networkx_nodes(H, pos, ax=ax, node_color=node_colors, cmap=plt.cm.Reds, vmin=0,
                                           vmax=20, node_size=node_sizes, edgecolors='black', linewidths=0.5)
            nx.draw_networkx_labels(H, pos, labels=labels, ax=ax, font_size=9, font_weight='bold')
            ax.set_aspect('equal', adjustable='datalim')  # 🌟 同步保持真实坐标比例
            ax.axis('off')

        cbar = fig.colorbar(nodes, ax=axes.ravel().tolist(), shrink=0.5, aspect=30, pad=0.03)
        cbar.set_label('节点拥挤度系数 (人数 / 每秒通行容量)', fontsize=16)
        plt.savefig(f"04_system_snapshot_comparison_T{tp}s.png", dpi=300, bbox_inches='tight')
        plt.close()


def plot_charts(method_metrics, total_p):
    """【专业高颜值版】核心指标对比"""
    labels = [label for label, _ in method_metrics]
    metrics_map = dict(method_metrics)
    colors = ['#E63946', '#F4A261', '#457B9D', '#59A14F']

    fig, axes = plt.subplots(2, 2, figsize=(11, 9))
    fig.suptitle(f'枢纽疏散指标评估 (测试客流: {total_p}人)', fontsize=20, fontweight='bold', y=0.96)

    metrics_list = [
        ('time', '疏散完成时间 ', axes[0, 0], 1),
        ('queueing_time', '总滞留排队时间 ', axes[0, 1], 1),
        ('congestion_exposure_time', '中度拥挤暴露时间 (density > 3) ', axes[1, 0], 1000),
        ('avg_speed', '全局平均移动速度 ', axes[1, 1], 1)
    ]

    for key, title, ax, div in metrics_list:
        vals = [metrics_map[label][key] / div for label in labels]
        bars = ax.bar(labels, vals, color=colors[:len(labels)], width=0.55, edgecolor='black', linewidth=1.2)
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax.grid(axis='y', linestyle='--', alpha=0.6)
        ax.set_axisbelow(True)

        for bar in bars:
            yval = bar.get_height()
            label_text = f'{yval:.2f}' if div == 1000 or key == 'avg_speed' else f'{int(yval)}'
            ax.text(bar.get_x() + bar.get_width() / 2, yval + max(abs(yval) * 0.01, 0.5), label_text, ha='center', va='bottom',
                    fontsize=11, fontweight='bold')

    plt.savefig("02_System_Macro_Metrics_Comparison.png", dpi=300, bbox_inches="tight")
    plt.close()

    baseline = metrics_map["Traditional"]
    comparison_labels = [label for label in labels if label != "Traditional"]
    metric_keys = [
        ("time", "时间改善率"),
        ("queueing_time", "排队改善率"),
        ("congestion_exposure_time", "中度拥挤暴露改善率"),
    ]
    x = np.arange(len(metric_keys))
    width = min(0.8 / max(len(comparison_labels), 1), 0.28)

    plt.figure(figsize=(10, 6))
    for idx, label in enumerate(comparison_labels):
        vals = []
        for key, _ in metric_keys:
            base_val = baseline[key]
            cur_val = metrics_map[label][key]
            improve = ((base_val - cur_val) / base_val * 100) if base_val > 0 else 0.0
            vals.append(improve)
        offset = (idx - (len(comparison_labels) - 1) / 2.0) * width
        bars = plt.bar(x + offset, vals, width=width, color=colors[idx + 1], edgecolor='black', label=label)
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2, yval + 1, f"{yval:.1f}%", ha='center', fontweight='bold',
                     fontsize=10, color='black')
    plt.xticks(x, [title for _, title in metric_keys])
    plt.ylabel("改善提升幅度 (%)", fontsize=12)
    plt.title(f"相对 Traditional 的提升率 ({total_p}人)", fontweight="bold", fontsize=16)
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    plt.gca().set_axisbelow(True)
    plt.savefig("03_System_Improvement_Rates.png", dpi=300, bbox_inches="tight")
    plt.close()


def plot_line_specific_analysis(metrics_trad, metrics_imp, pop_dict):
    """【专业升级版】绘制各线路专属指标（疏散时间 + 中度拥挤暴露）"""
    lines = [l for l, d in pop_dict.items() if sum(d.values()) > 0]

    # 画 1行2列 的图，左边时间，右边拥挤暴露
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle('各线路疏散指标评估', fontsize=18, fontweight='bold', y=1.02)

    x = np.arange(len(lines))
    width = 0.35
    colors = ['#E63946', '#457B9D']

    # === 子图 1：各线路疏散完成时间 ===
    ax1 = axes[0]
    t_trad = [metrics_trad["clearance_times_by_line"].get(l) if metrics_trad["clearance_times_by_line"].get(
        l) is not None else metrics_trad["time"] for l in lines]
    t_imp = [
        metrics_imp["clearance_times_by_line"].get(l) if metrics_imp["clearance_times_by_line"].get(l) is not None else
        metrics_imp["time"] for l in lines]

    bars1_trad = ax1.bar(x - width / 2, t_trad, width, label='Traditional (传统)', color=colors[0], edgecolor='black',
                         linewidth=1)
    bars1_imp = ax1.bar(x + width / 2, t_imp, width, label='OurSinglePath', color=colors[1], edgecolor='black',
                        linewidth=1)

    ax1.set_xticks(x);
    ax1.set_xticklabels(lines, fontsize=12)
    ax1.set_ylabel('疏散完成时间 / Evacuation Time (s)', fontsize=12)
    ax1.set_title('各单线路疏散完成时间对比', fontweight='bold', fontsize=14)
    ax1.legend();
    ax1.grid(axis='y', linestyle='--', alpha=0.6);
    ax1.set_axisbelow(True)

    for bars in [bars1_trad, bars1_imp]:
        for bar in bars:
            yval = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, yval + 2, f'{int(yval)}', ha='center', va='bottom', fontsize=11,
                     fontweight='bold')

    # === 子图 2：各线路中度拥挤暴露时间 (density > 3) ===
    ax2 = axes[1]
    e_trad = [metrics_trad["congestion_exposure_by_line"].get(l, 0) / 1000.0 for l in lines]
    e_imp = [metrics_imp["congestion_exposure_by_line"].get(l, 0) / 1000.0 for l in lines]

    bars2_trad = ax2.bar(x - width / 2, e_trad, width, label='Traditional (传统)', color=colors[0], edgecolor='black',
                         linewidth=1)
    bars2_imp = ax2.bar(x + width / 2, e_imp, width, label='OurSinglePath', color=colors[1], edgecolor='black',
                        linewidth=1)

    ax2.set_xticks(x);
    ax2.set_xticklabels(lines, fontsize=12)
    ax2.set_ylabel('拥挤暴露时间 / Congestion Exposure (10$^3$ pax·s)', fontsize=12)
    ax2.set_title('各单线路中度拥挤暴露对比 (density > 3)', fontweight='bold', fontsize=14)
    ax2.legend();
    ax2.grid(axis='y', linestyle='--', alpha=0.6);
    ax2.set_axisbelow(True)

    for bars in [bars2_trad, bars2_imp]:
        for bar in bars:
            yval = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width() / 2, yval + (max(e_trad) * 0.02), f'{yval:.1f}', ha='center',
                     va='bottom', fontsize=11, fontweight='bold')

    plt.savefig("05_System_Line_Core_Metrics.png", dpi=300, bbox_inches='tight')
    plt.close()

    # ==== 保留：各线路逃生出口去向 (堆叠柱状图) ====
    exit_plot_methods = [("Traditional", metrics_trad), ("OurSinglePath", metrics_imp)]
    shared_active_exits = sorted({
        ext
        for _, met in exit_plot_methods
        for ext, lines_ppl in met["exit_usage_by_line"].items()
        if sum(lines_ppl.values()) > 1.0
    })
    shared_exit_ymax = 0.0
    for _, met in exit_plot_methods:
        exits_dict = met["exit_usage_by_line"]
        for ext in shared_active_exits:
            shared_exit_ymax = max(shared_exit_ymax, sum(exits_dict.get(ext, {}).get(line, 0.0) for line in lines))

    if shared_active_exits:
        shared_exit_ymax = max(shared_exit_ymax * 1.08, 1.0)

    for title, met in exit_plot_methods:
        exits_dict = met["exit_usage_by_line"]
        active_exits = shared_active_exits
        if not active_exits:
            continue

        fig, ax = plt.subplots(figsize=(14, 6))
        bottoms = np.zeros(len(active_exits))
        c_map = plt.cm.Set3(np.linspace(0, 1, len(lines)))
        x_positions = np.arange(len(active_exits))

        for i, line in enumerate(lines):
            counts = [exits_dict[ext].get(line, 0.0) for ext in active_exits]
            ax.bar(x_positions, counts, label=line, bottom=bottoms, color=c_map[i], edgecolor='black', linewidth=0.5)
            bottoms += counts

        ax.set_xticks(x_positions);
        ax.set_xticklabels([e.replace("Exit_", "") for e in active_exits], rotation=45, ha='right')
        ax.set_ylabel('逃生人数 (人)');
        ax.set_ylim(0, shared_exit_ymax)
        ax.set_title(f'人群逃生出口分布溯源 ({_method_display_name(title)})', fontweight='bold', fontsize=14)
        ax.legend(title="人群来源");
        ax.grid(axis='y', linestyle='--', alpha=0.5);
        ax.set_axisbelow(True)
        plt.savefig(f"06_Exit_Destinations_{_method_output_tag(title)}.png", dpi=300, bbox_inches='tight')
        plt.close()


def plot_charts_multi(G_base, method_metrics, total_p):
    labels = [label for label, _ in method_metrics]
    metrics_map = dict(method_metrics)
    colors = ['#E63946', '#F4A261', '#457B9D', '#59A14F']
    baseline_label = labels[0] if labels else "Baseline"
    key_nodes = _select_key_facility_nodes(G_base, method_metrics, top_k=8)
    key_node_rows = []
    for label, metrics in method_metrics:
        sim_time = max(float(metrics.get("time", 0.0)), DELTA_T)
        node_stats = metrics.get("node_stats", {})
        occupancy_vals = []
        for node in key_nodes:
            stat = node_stats.get(node, {})
            avg_occupancy = float(stat.get("density_seconds", 0.0)) / sim_time
            occupancy_vals.append(avg_occupancy)
            key_node_rows.append({
                "method": label,
                "node": node,
                "avg_occupancy": avg_occupancy,
                "peak_density": float(stat.get("peak_density", 0.0)),
                "queue_seconds": float(stat.get("queue_seconds", 0.0)),
            })
        metrics["key_node_avg_occupancy"] = sum(occupancy_vals) / len(occupancy_vals) if occupancy_vals else 0.0

    fig, axes = plt.subplots(2, 2, figsize=(11, 9))
    fig.suptitle(f'枢纽疏散安全性评估 (测试客流: {total_p}人)', fontsize=20, fontweight='bold', y=0.96)
    metrics_list = [
        ('queueing_time', '总滞留排队时间 (人·秒)', axes[0, 0], 1),
        ('severe_congestion_exposure_time', '重度拥挤暴露 (density > 5.0)', axes[0, 1], 1000),
        ('time', '疏散完成时间 (s)', axes[1, 0], 1),
        ('key_node_avg_occupancy', '关键节点平均占用率 (人/㎡)', axes[1, 1], 1)
    ]

    for key, title, ax, div in metrics_list:
        vals = [metrics_map[label][key] / div for label in labels]
        bars = ax.bar(labels, vals, color=colors[:len(labels)], width=0.55, edgecolor='black', linewidth=1.2)
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax.grid(axis='y', linestyle='--', alpha=0.6)
        ax.set_axisbelow(True)
        ymax = max(vals) if vals else 0.0
        if key == 'key_node_avg_occupancy':
            offset = max(ymax * 0.04, 0.015)
            ax.set_ylim(0, max(ymax * 1.18, ymax + 0.08, 0.1))
        elif div == 1000:
            offset = max(ymax * 0.03, 0.12)
            ax.set_ylim(0, max(ymax * 1.14, 1.0))
        else:
            offset = max(ymax * 0.015, 0.5)
            ax.set_ylim(0, max(ymax * 1.10, 1.0))
        for bar in bars:
            yval = bar.get_height()
            label_text = f'{yval:.2f}' if div == 1000 or key in {'avg_speed', 'key_node_avg_occupancy'} else f'{int(yval)}'
            ax.text(bar.get_x() + bar.get_width() / 2, yval + offset, label_text,
                    ha='center', va='bottom', fontsize=11, fontweight='bold')

    plt.savefig("02_System_Macro_Metrics_Comparison.png", dpi=300, bbox_inches="tight")
    plt.close()
    if key_node_rows:
        pd.DataFrame(key_node_rows).to_csv("02c_system_key_node_occupancy.csv", index=False, encoding="utf-8-sig")

    plt.figure(figsize=(8.5, 6))
    moderate_vals = [metrics_map[label]["moderate_congestion_exposure_time"] / 1000.0 for label in labels]
    bars = plt.bar(labels, moderate_vals, color=colors[:len(labels)], edgecolor='black', linewidth=1.2, width=0.55)
    ymax = max(moderate_vals) if moderate_vals else 0.0
    offset = max(ymax * 0.03, 0.12)
    plt.ylim(0, max(ymax * 1.14, 1.0))
    plt.ylabel("中度拥挤暴露时间 (10$^3$ 人·秒)", fontsize=12)
    plt.title("系统层中度拥挤暴露对比 (density > 3.0)", fontweight="bold", fontsize=16)
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    plt.gca().set_axisbelow(True)
    for bar in bars:
        yval = bar.get_height()
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            yval + offset,
            f"{yval:.2f}",
            ha='center',
            va='bottom',
            fontsize=11,
            fontweight='bold'
        )
    plt.savefig("02d_System_Moderate_Congestion_Comparison.png", dpi=300, bbox_inches="tight")
    plt.close()

    baseline = metrics_map[baseline_label]
    comparison_labels = [label for label in labels if label != baseline_label]
    metric_keys = [
        ("queueing_time", "排队改善率"),
        ("severe_congestion_exposure_time", "重度拥挤暴露改善率"),
        ("time", "时间改善率"),
    ]
    x = np.arange(len(metric_keys))
    width = min(0.8 / max(len(comparison_labels), 1), 0.28)

    plt.figure(figsize=(10, 6))
    for idx, label in enumerate(comparison_labels):
        vals = []
        for key, _ in metric_keys:
            base_val = baseline[key]
            cur_val = metrics_map[label][key]
            improve = ((base_val - cur_val) / base_val * 100) if base_val > 0 else 0.0
            vals.append(improve)
        offset = (idx - (len(comparison_labels) - 1) / 2.0) * width
        bars = plt.bar(x + offset, vals, width=width, color=colors[idx + 1], edgecolor='black', label=label)
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2, yval + 1, f"{yval:.1f}%", ha='center',
                     fontweight='bold', fontsize=10, color='black')
    plt.xticks(x, [title for _, title in metric_keys])
    plt.ylabel("改善提升幅度 (%)", fontsize=12)
    plt.title(f"相对 {baseline_label} 的安全性优先改善率 ({total_p}人)", fontweight="bold", fontsize=16)
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    plt.gca().set_axisbelow(True)
    plt.savefig("03_System_Improvement_Rates.png", dpi=300, bbox_inches="tight")
    plt.close()

    if all("wall_clock_runtime_s" in metrics_map[label] for label in labels):
        plt.figure(figsize=(8.5, 6))
        runtime_vals = [metrics_map[label]["wall_clock_runtime_s"] for label in labels]
        bars = plt.bar(labels, runtime_vals, color=colors[:len(labels)], edgecolor='black', linewidth=1.2, width=0.55)
        plt.ylabel("实际运行时间 (s)", fontsize=12)
        plt.title("系统层三算法实际运行时间对比", fontweight="bold", fontsize=16)
        plt.grid(axis='y', linestyle='--', alpha=0.6)
        plt.gca().set_axisbelow(True)
        for bar in bars:
            yval = bar.get_height()
            plt.text(
                bar.get_x() + bar.get_width() / 2,
                yval + max(yval * 0.02, 0.02),
                f"{yval:.2f}",
                ha='center',
                va='bottom',
                fontsize=11,
                fontweight='bold'
            )
        plt.savefig("02b_System_Runtime_Comparison.png", dpi=300, bbox_inches="tight")
        plt.close()


def plot_system_evacuation_curve(method_metrics, total_p, filename="01_system_evacuation_curve.png", csv_filename="01_system_evacuation_curve.csv"):
    colors = ['#E63946', '#F4A261', '#457B9D', '#59A14F']
    plt.figure(figsize=(10.5, 6.5))
    csv_rows = []

    for idx, (label, metrics) in enumerate(method_metrics):
        curve = metrics.get("evacuation_curve", {})
        times = curve.get("times", [])
        remaining = curve.get("remaining", [])
        if not times or not remaining:
            continue
        plt.plot(times, remaining, linewidth=2.8, color=colors[idx % len(colors)], label=label)
        for t, r in zip(times, remaining):
            csv_rows.append({
                "method": label,
                "time_s": float(t),
                "remaining_people": float(r),
            })

    plt.title(f"整体疏散完成曲线（站内剩余人数随时间变化，{total_p}人）", fontsize=18, fontweight='bold')
    plt.xlabel("时间 (s)", fontsize=13)
    plt.ylabel("站内剩余人数 (人)", fontsize=13)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.legend()
    plt.gca().set_axisbelow(True)
    plt.savefig(filename, dpi=300, bbox_inches="tight")
    plt.close()

    if csv_rows:
        pd.DataFrame(csv_rows).to_csv(csv_filename, index=False, encoding="utf-8-sig")


def plot_line_specific_analysis_multi(method_metrics, pop_dict):
    lines = [l for l, d in pop_dict.items() if sum(d.values()) > 0]
    labels = [label for label, _ in method_metrics]
    metrics_map = dict(method_metrics)
    colors = ['#E63946', '#F4A261', '#457B9D', '#59A14F']

    fig, axes = plt.subplots(1, 2, figsize=(17, 6))
    fig.suptitle('各线路疏散指标评估', fontsize=18, fontweight='bold', y=1.02)

    x = np.arange(len(lines))
    width = min(0.8 / max(len(labels), 1), 0.25)

    ax1 = axes[0]
    time_groups = []
    for idx, label in enumerate(labels):
        vals = [
            metrics_map[label]["clearance_times_by_line"].get(l)
            if metrics_map[label]["clearance_times_by_line"].get(l) is not None
            else metrics_map[label]["time"]
            for l in lines
        ]
        offset = (idx - (len(labels) - 1) / 2.0) * width
        bars = ax1.bar(x + offset, vals, width, label=label, color=colors[idx], edgecolor='black', linewidth=1)
        time_groups.append(bars)

    ax1.set_xticks(x)
    ax1.set_xticklabels(lines, fontsize=12)
    ax1.set_ylabel('疏散完成时间 / Evacuation Time (s)', fontsize=12)
    ax1.set_title('各单线路疏散完成时间对比', fontweight='bold', fontsize=14)
    ax1.legend()
    ax1.grid(axis='y', linestyle='--', alpha=0.6)
    ax1.set_axisbelow(True)
    for bars in time_groups:
        for bar in bars:
            yval = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width() / 2, yval + 2, f'{int(yval)}', ha='center', va='bottom', fontsize=10,
                     fontweight='bold')

    ax2 = axes[1]
    exposure_groups = []
    exposure_max = 0.0
    for idx, label in enumerate(labels):
        vals = [metrics_map[label]["congestion_exposure_by_line"].get(l, 0) / 1000.0 for l in lines]
        exposure_max = max(exposure_max, max(vals) if vals else 0.0)
        offset = (idx - (len(labels) - 1) / 2.0) * width
        bars = ax2.bar(x + offset, vals, width, label=label, color=colors[idx], edgecolor='black', linewidth=1)
        exposure_groups.append(bars)

    ax2.set_xticks(x)
    ax2.set_xticklabels(lines, fontsize=12)
    ax2.set_ylabel('中度拥挤暴露时间 / Congestion Exposure (10$^3$ pax·s)', fontsize=12)
    ax2.set_title('各单线路中度拥挤暴露对比 (density > 3)', fontweight='bold', fontsize=14)
    ax2.legend()
    ax2.grid(axis='y', linestyle='--', alpha=0.6)
    ax2.set_axisbelow(True)
    for bars in exposure_groups:
        for bar in bars:
            yval = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width() / 2, yval + max(exposure_max, 1.0) * 0.02, f'{yval:.1f}', ha='center',
                     va='bottom', fontsize=10, fontweight='bold')

    plt.savefig("05_System_Line_Core_Metrics.png", dpi=300, bbox_inches='tight')
    plt.close()

    shared_active_exits = sorted({
        ext
        for _, met in method_metrics
        for ext, lines_ppl in met["exit_usage_by_line"].items()
        if sum(lines_ppl.values()) > 1.0
    })
    shared_exit_ymax = 0.0
    for _, met in method_metrics:
        exits_dict = met["exit_usage_by_line"]
        for ext in shared_active_exits:
            shared_exit_ymax = max(shared_exit_ymax, sum(exits_dict.get(ext, {}).get(line, 0.0) for line in lines))

    if shared_active_exits:
        shared_exit_ymax = max(shared_exit_ymax * 1.08, 1.0)

    for title, met in method_metrics:
        exits_dict = met["exit_usage_by_line"]
        active_exits = shared_active_exits
        if not active_exits:
            continue

        fig, ax = plt.subplots(figsize=(14, 6))
        bottoms = np.zeros(len(active_exits))
        c_map = plt.cm.Set3(np.linspace(0, 1, len(lines)))
        x_positions = np.arange(len(active_exits))

        for i, line in enumerate(lines):
            counts = [exits_dict[ext].get(line, 0.0) for ext in active_exits]
            ax.bar(x_positions, counts, label=line, bottom=bottoms, color=c_map[i], edgecolor='black', linewidth=0.5)
            bottoms += counts

        ax.set_xticks(x_positions)
        ax.set_xticklabels([e.replace("Exit_", "") for e in active_exits], rotation=45, ha='right')
        ax.set_ylabel('逃生人数 (人)')
        ax.set_ylim(0, shared_exit_ymax)
        ax.set_title(f'人群逃生出口分布溯源 ({_method_display_name(title)})', fontweight='bold', fontsize=14)
        ax.legend(title="人群来源")
        ax.grid(axis='y', linestyle='--', alpha=0.5)
        ax.set_axisbelow(True)
        plt.savefig(f"06_Exit_Destinations_{_method_output_tag(title)}.png", dpi=300, bbox_inches='tight')
        plt.close()

def _infer_target_by_line_from_graph_state(G):
    totals = {line: 0.0 for line in ALL_LINE_IDS}
    for _, data in G.nodes(data=True):
        people_dict = data.get("people_dict", {})
        for line in ALL_LINE_IDS:
            totals[line] += float(people_dict.get(line, 0.0))
    return {line: total for line, total in totals.items() if total > 0.0}


def _run_simulation_for_metrics_core(G, method, target_by_line):
    time, evacuated_count = 0.0, 0.0
    total_flow_moves, sum_speed_weighted = 0.0, 0.0
    travel_person_seconds = 0.0
    shortest_dists = dict(nx.all_pairs_dijkstra_path_length(G, weight="length"))

    evacuated_by_line = {line: 0.0 for line in ALL_LINE_IDS}
    monitored_queue_nodes = [n for n in G.nodes() if _is_queue_node(G, n)]
    monitored_edges = [
        _edge_key(u, v)
        for u, v, data in G.edges(data=True)
        if _is_monitored_edge(data)
    ]

    monitor_node = "Gate_L2_N_West" if "Gate_L2_N_West" in G.nodes else next(
        (n for n in G.nodes if "gate" in n.lower()), None
    )

    metrics = {
        "time": 0,
        "queueing_time": 0.0,
        "congestion_exposure_time": 0.0,
        "moderate_congestion_exposure_time": 0.0,
        "severe_congestion_exposure_time": 0.0,
        "avg_speed": 0.0,
        "avg_travel_time": 0.0,
        "peak_density": 0.0,
        "clearance_times_by_line": {line: None for line, pop in target_by_line.items() if pop > 0},
        "queueing_time_by_line": {line: 0.0 for line in ALL_LINE_IDS},
        "congestion_exposure_by_line": {line: 0.0 for line in ALL_LINE_IDS},
        "moderate_congestion_exposure_by_line": {line: 0.0 for line in ALL_LINE_IDS},
        "severe_congestion_exposure_by_line": {line: 0.0 for line in ALL_LINE_IDS},
        "exit_usage_by_line": {
            ext: {line: 0.0 for line in ALL_LINE_IDS}
            for ext in NODES_DATA.get("ALL_EXITS", {}).keys()
        },
        "exit_usage_by_source_group": {
            ext: {}
            for ext in NODES_DATA.get("ALL_EXITS", {}).keys()
        },
        "exit_usage": {ext: 0 for ext in NODES_DATA.get("ALL_EXITS", {}).keys()},
        "time_series_queue": {monitor_node: []} if monitor_node else {},
        "evacuation_curve": {"times": [], "remaining": [], "evacuated": []},
        "node_stats": {
            n: {
                "peak_people": 0.0,
                "peak_density": 0.0,
                "density_seconds": 0.0,
                "queue_seconds": 0.0,
                "congestion_seconds": 0.0
            }
            for n in G.nodes()
        },
        "time_series_by_line": {
            line: {"times": [], "speeds": [], "queues": []}
            for line in ALL_LINE_IDS
        },
        "node_series": {
            n: {"times": [], "queue": [], "travel_time": []}
            for n in monitored_queue_nodes
        },
        "edge_series": {
            edge_key: {"times": [], "passengers": [], "speed": []}
            for edge_key in monitored_edges
        },
        "edge_stats": {
            edge_key: {"flow_total": 0.0, "peak_passengers": 0.0, "peak_speed": 0.0}
            for edge_key in monitored_edges
        }
    }

    while time < 6000:
        current_time, _ = _ensure_transit_state(G)
        time = current_time

        arrived_this_step = _process_transit_arrivals(
            G,
            current_time,
            evacuated_by_line=evacuated_by_line,
            exit_usage_dict=metrics["exit_usage_by_line"],
            exit_usage_by_source_group=metrics["exit_usage_by_source_group"],
        )
        evacuated_count += arrived_this_step
        total_evacuated = sum(float(val) for val in evacuated_by_line.values())
        total_remaining = max(sum(float(target) for target in target_by_line.values() if target > 0) - total_evacuated, 0.0)
        metrics["evacuation_curve"]["times"].append(current_time)
        metrics["evacuation_curve"]["remaining"].append(total_remaining)
        metrics["evacuation_curve"]["evacuated"].append(total_evacuated)

        all_lines_cleared = True
        for line_id, target in target_by_line.items():
            if target > 0:
                # 1. 独立发奖牌：只要这条线跑完了，立刻记录当前时间，不管别人跑没跑完
                if metrics["clearance_times_by_line"].get(line_id) is None:
                    if evacuated_by_line[line_id] >= target * 0.99:
                        metrics["clearance_times_by_line"][line_id] = current_time

                # 2. 独立查缺勤：只要还有任何一条线没跑完，总清空标志就为 False
                if evacuated_by_line[line_id] < target * 0.99:
                    all_lines_cleared = False

        # 注意：这里千万不要放在 for 循环里面！
        # 等 for 循环把所有线路都老老实实检查完之后，再判断要不要结束整个大仿真
        if all_lines_cleared:
            break

        active_nodes = [
            n for n in G.nodes()
            if G.nodes[n].get("people", 0) > 0.1 and G.nodes[n].get("type") != "exit"
        ]

        current_moderate_congestion = 0.0
        current_severe_congestion = 0.0
        current_queues_by_line = {line: 0.0 for line in ALL_LINE_IDS}
        current_moving_ppl_by_line = {line: 0.0 for line in ALL_LINE_IDS}
        current_speed_sum_by_line = {line: 0.0 for line in ALL_LINE_IDS}
        current_queue_by_node = {n: G.nodes[n].get("people", 0.0) for n in monitored_queue_nodes}

        # 先统计这一时刻节点状态
        for n in active_nodes:
            ppl = G.nodes[n]["people"]
            node_type = G.nodes[n].get("type", "")
            density = ppl / max(G.nodes[n].get("area", 1.0), 0.001)

            metrics["node_stats"][n]["peak_people"] = max(metrics["node_stats"][n]["peak_people"], ppl)
            metrics["node_stats"][n]["peak_density"] = max(metrics["node_stats"][n]["peak_density"], density)
            metrics["node_stats"][n]["density_seconds"] += density * DELTA_T
            metrics["peak_density"] = max(metrics["peak_density"], density)

            if _is_queue_node(G, n):
                metrics["queueing_time"] += ppl * DELTA_T
                metrics["node_stats"][n]["queue_seconds"] += ppl * DELTA_T

                for line_id, count in G.nodes[n].get("people_dict", {}).items():
                    if count <= 0:
                        continue
                    metrics["queueing_time_by_line"][line_id] += count * DELTA_T
                    current_queues_by_line[line_id] += count


            if density > MODERATE_CONGESTION_DENSITY_THRESHOLD:
                current_moderate_congestion += ppl * DELTA_T
                metrics["node_stats"][n]["congestion_seconds"] += ppl * DELTA_T
                for line_id, count in G.nodes[n].get("people_dict", {}).items():
                    metrics["congestion_exposure_by_line"][line_id] += count * DELTA_T
                    metrics["moderate_congestion_exposure_by_line"][line_id] += count * DELTA_T

            if density > SEVERE_CONGESTION_DENSITY_THRESHOLD:
                current_severe_congestion += ppl * DELTA_T
                for line_id, count in G.nodes[n].get("people_dict", {}).items():
                    metrics["severe_congestion_exposure_by_line"][line_id] += count * DELTA_T

        # 关键改动：这里不再只走单一 next node，而是允许并行分流
        moves = get_step_moves(G, method, shortest_dists)

        metrics["congestion_exposure_time"] += current_moderate_congestion
        metrics["moderate_congestion_exposure_time"] += current_moderate_congestion
        metrics["severe_congestion_exposure_time"] += current_severe_congestion
        if monitor_node and monitor_node in G.nodes:
            metrics["time_series_queue"][monitor_node].append(G.nodes[monitor_node].get("people", 0))

        scheduled_moves = _schedule_moves_as_transit(G, moves)
        for item in scheduled_moves:
            amount = float(item["amount"])
            tt = max(float(item["travel_time"]), 0.001)
            u_node, v_node = item["u"], item["v"]
            length = max(float(G[u_node][v_node].get("length", 0.0)), 0.0)
            actual_spd = length / tt if length > 0 else spr.PAPER_FREE_SPEED

            total_flow_moves += amount
            sum_speed_weighted += amount * actual_spd

            for line_id, line_flow in item.get("line_shares", {}).items():
                if line_flow <= 0:
                    continue
                current_moving_ppl_by_line[line_id] += line_flow
                current_speed_sum_by_line[line_id] += line_flow * actual_spd

            edge_key = _edge_key(u_node, v_node)
            if edge_key in metrics["edge_stats"]:
                metrics["edge_stats"][edge_key]["flow_total"] += amount
                metrics["edge_stats"][edge_key]["peak_passengers"] = max(
                    metrics["edge_stats"][edge_key]["peak_passengers"], amount
                )
                metrics["edge_stats"][edge_key]["peak_speed"] = max(
                    metrics["edge_stats"][edge_key]["peak_speed"], actual_spd
                )

        travel_person_seconds += sum(item["amount"] * item["travel_time"] for item in scheduled_moves)
        G.graph["_sim_time"] = current_time + DELTA_T

        node_travel_sum = {n: 0.0 for n in monitored_queue_nodes}
        node_travel_flow = {n: 0.0 for n in monitored_queue_nodes}
        for item in scheduled_moves:
            u = item["u"]
            if u not in node_travel_sum:
                continue
            node_travel_sum[u] += item["amount"] * item["travel_time"]
            node_travel_flow[u] += item["amount"]

        # 记录每条线的瞬时折线数据
        for line_id, target in target_by_line.items():
            if target > 0:
                metrics["time_series_by_line"][line_id]["times"].append(time)
                metrics["time_series_by_line"][line_id]["queues"].append(current_queues_by_line[line_id])
                if current_moving_ppl_by_line[line_id] > 0:
                    metrics["time_series_by_line"][line_id]["speeds"].append(
                        current_speed_sum_by_line[line_id] / current_moving_ppl_by_line[line_id]
                    )
                else:
                    metrics["time_series_by_line"][line_id]["speeds"].append(0.0)

        for n in monitored_queue_nodes:
            metrics["node_series"][n]["times"].append(current_time)
            metrics["node_series"][n]["queue"].append(current_queue_by_node.get(n, 0.0))
            if node_travel_flow[n] > 0:
                metrics["node_series"][n]["travel_time"].append(node_travel_sum[n] / node_travel_flow[n])
            else:
                metrics["node_series"][n]["travel_time"].append(np.nan)

        edge_snapshot = _capture_edge_snapshot(G, current_time, monitored_edges)
        for edge_key, series in metrics["edge_series"].items():
            series["times"].append(current_time)
            series["passengers"].append(edge_snapshot[edge_key]["passengers"] if edge_key in edge_snapshot else 0.0)
            if edge_snapshot[edge_key]["passengers"] > 0:
                series["speed"].append(edge_snapshot[edge_key]["speed_sum"] / edge_snapshot[edge_key]["passengers"])
            else:
                series["speed"].append(np.nan)

        time = current_time + DELTA_T

    metrics["time"] = time
    metrics["avg_speed"] = sum_speed_weighted / total_flow_moves if total_flow_moves > 0 else 0.0
    total_target = sum(float(target) for target in target_by_line.values() if target > 0)
    metrics["avg_travel_time"] = travel_person_seconds / total_target if total_target > 0 else 0.0
    metrics["exit_usage"] = {
        exit_name: sum(float(flow) for flow in line_map.values())
        for exit_name, line_map in metrics["exit_usage_by_line"].items()
    }
    return metrics


def run_simulation_for_metrics(G_base, pop_dict, method=OUR_SINGLE_PATH_METHOD, apply_noise=False, rng=None):
    G = copy.deepcopy(G_base)
    init_people(G, pop_dict, apply_noise, rng)
    source_group_totals = _source_group_totals_from_graph(G)
    if apply_noise:
        noise_rng = rng if rng is not None else random.Random()
        apply_capacity_noise(G, noise_rng, 0.95, 1.05)
    target_by_line = {
        line: sum(d.values())
        for line, d in pop_dict.items()
        if sum(d.values()) > 0
    }
    metrics = _run_simulation_for_metrics_core(G, method, target_by_line)
    metrics["source_group_totals"] = source_group_totals
    return metrics


def run_simulation_for_metrics_timed(G_base, pop_dict, method=OUR_SINGLE_PATH_METHOD, apply_noise=False, rng=None):
    start_ts = time.perf_counter()
    metrics = run_simulation_for_metrics(G_base, pop_dict, method=method, apply_noise=apply_noise, rng=rng)
    metrics["wall_clock_runtime_s"] = time.perf_counter() - start_ts
    return metrics


def build_exit_source_group_rows(metrics, method_label=None):
    source_group_totals = metrics.get("source_group_totals", {})
    exit_usage_by_source_group = metrics.get("exit_usage_by_source_group", {})
    rows = []

    for source_group_id, configured_people in source_group_totals.items():
        line_id, source_type, source_zone = _parse_source_group_id(source_group_id)
        evacuated_people = sum(
            float(group_map.get(source_group_id, 0.0))
            for group_map in exit_usage_by_source_group.values()
        )
        denom = evacuated_people if evacuated_people > 0 else float(configured_people)

        for exit_name, group_map in exit_usage_by_source_group.items():
            people = float(group_map.get(source_group_id, 0.0))
            if people <= 0:
                continue
            rows.append({
                "method_label": method_label or "",
                "source_group": source_group_id,
                "line": line_id,
                "source_type": source_type,
                "source_zone": source_zone,
                "configured_people": float(configured_people),
                "evacuated_people": float(evacuated_people),
                "exit_name": exit_name,
                "people": people,
                "share_within_group": people / max(denom, 1.0),
            })

    order = {"platform_waiting": 0, "hall_people": 1, "transfer_people": 2, "train_1": 3, "train_2": 4}
    rows.sort(
        key=lambda row: (
            row["method_label"],
            row["line"],
            order.get(row["source_type"], 99),
            row.get("source_zone", ""),
            row["exit_name"],
        )
    )
    return rows


def run_simulation_for_existing_state(G_state, method=OUR_SINGLE_PATH_METHOD, target_by_line=None):
    G = copy.deepcopy(G_state)
    targets = target_by_line if target_by_line is not None else _infer_target_by_line_from_graph_state(G)
    return _run_simulation_for_metrics_core(G, method, targets)


def _build_fixed_next_by_node(G, path=None, method=ANT_COLONY_METHOD):
    fixed_next = {}

    if isinstance(path, dict):
        for fixed_path in path.values():
            if not fixed_path:
                continue
            for u, v in zip(fixed_path, fixed_path[1:]):
                if G.has_edge(u, v):
                    fixed_next[u] = v
    elif path:
        for u, v in zip(path, path[1:]):
            if G.has_edge(u, v):
                fixed_next[u] = v

    shortest_dists = dict(nx.all_pairs_dijkstra_path_length(G, weight="length"))
    active_sources = [
        n for n in G.nodes()
        if G.nodes[n].get("type") != "exit" and float(G.nodes[n].get("people", 0.0)) > 0.1
    ]
    for source in active_sources:
        if source in fixed_next:
            continue
        source_path = get_best_path_to_exit(G, source, method, shortest_dists)
        if not source_path:
            continue
        for u, v in zip(source_path, source_path[1:]):
            if G.has_edge(u, v):
                fixed_next[u] = v
    return fixed_next


def _recover_fixed_path(G, source, max_steps=None):
    fixed_next = G.graph.get("_fixed_next_by_node") or {}
    if source not in fixed_next:
        return None
    max_steps = max_steps or max(len(G.nodes), 1)
    path = [source]
    visited = {source}
    current = source
    for _ in range(max_steps):
        nxt = fixed_next.get(current)
        if not nxt or not G.has_edge(current, nxt):
            break
        path.append(nxt)
        if G.nodes[nxt].get("type") == "exit":
            return path
        if nxt in visited:
            break
        visited.add(nxt)
        current = nxt
    return path if len(path) > 1 else None


def run_simulation_for_fixed_path_state(G_state, path, method=ANT_COLONY_METHOD, target_by_line=None):
    """按一条预先规划好的固定路径推进，用于传统 ACO 这类静态路径基准。"""
    G = copy.deepcopy(G_state)
    targets = target_by_line if target_by_line is not None else _infer_target_by_line_from_graph_state(G)
    G.graph["_fixed_next_by_node"] = _build_fixed_next_by_node(G, path=path, method=method)
    return _run_simulation_for_metrics_core(G, method, targets)


def _reset_graph_people_state(G):
    for node in G.nodes():
        G.nodes[node]["people"] = 0
        current_dict = G.nodes[node].get("people_dict", {})
        G.nodes[node]["people_dict"] = {line: 0 for line in ALL_LINE_IDS}
        for line in current_dict:
            if line not in G.nodes[node]["people_dict"]:
                G.nodes[node]["people_dict"][line] = 0
    G.graph["_sim_time"] = 0.0
    G.graph["_transit_queue"] = []
    G.graph["_edge_flow_credit"] = {}
    G.graph.pop("_arrival_queue", None)
    G.graph.pop("_paper_blocked_signature", None)
    G.graph.pop("_paper_path_by_node", None)
    G.graph.pop("_paper_fixed_next_by_node", None)
    G.graph.pop("_our_guidance_state", None)


def build_single_path_case_state(
    G_base,
    case_spec,
    evacuees=SINGLE_PATH_CASE_POPULATION,
    use_waiting_zones=None,
):
    G = copy.deepcopy(G_base)
    _reset_graph_people_state(G)

    origin = case_spec["origin"]
    line_id = case_spec["line"]
    G.graph["_single_path_case_line"] = line_id
    if origin not in G.nodes:
        raise ValueError(f"Single-path case origin {origin} not found in graph.")

    should_use_waiting_zones = use_waiting_zones
    if should_use_waiting_zones is None:
        should_use_waiting_zones = (
            origin == f"Platform_{line_id}"
            and bool(_platform_waiting_zone_defs(line_id))
            and bool(_platform_waiting_zone_nodes(G, line_id))
        )

    if should_use_waiting_zones:
        _add_people_to_nodes_by_weights(
            G,
            _platform_waiting_zone_nodes(G, line_id),
            line_id,
            int(round(float(evacuees))),
            _platform_waiting_zone_area_weights(_platform_waiting_zone_defs(line_id)),
        )
    else:
        assigned = int(round(float(evacuees)))
        G.nodes[origin]["people"] = assigned
        G.nodes[origin]["people_dict"][line_id] = assigned
    _apply_obstacle_areas(G)
    return G


def build_distributed_platform_case_state(G_base, line_id, evacuees, area_weights=None):
    G = copy.deepcopy(G_base)
    _reset_graph_people_state(G)
    G.graph["_single_path_case_line"] = line_id

    waiting_zone_defs = _platform_waiting_zone_defs(line_id)
    waiting_zone_nodes = _platform_waiting_zone_nodes(G, line_id)
    if not waiting_zone_defs or not waiting_zone_nodes:
        raise ValueError(f"Line {line_id} has no configured platform waiting zones.")

    if area_weights is None:
        area_weights = _platform_waiting_zone_area_weights(waiting_zone_defs)
    elif len(area_weights) != len(waiting_zone_nodes):
        raise ValueError(
            f"Expected {len(waiting_zone_nodes)} area weights for line {line_id}, got {len(area_weights)}."
        )

    _add_people_to_nodes_by_weights(
        G,
        waiting_zone_nodes,
        line_id,
        int(round(float(evacuees))),
        area_weights,
    )
    _apply_obstacle_areas(G)
    return G


def _apply_obstacle_areas(G):
    """把配置文件里的障碍物面积写入图属性。"""
    nodes_cfg = OBSTACLE_AREAS.get("nodes", {})
    for line_id, node_map in nodes_cfg.items():
        if not isinstance(node_map, dict):
            continue
        for node_name, obstacle_area in node_map.items():
            if node_name in G.nodes:
                G.nodes[node_name]["obstacle_area"] = float(obstacle_area)
                G.nodes[node_name]["obstacle_line"] = line_id

    edges_cfg = OBSTACLE_AREAS.get("edges", {})
    for line_id, edge_map in edges_cfg.items():
        if not isinstance(edge_map, dict):
            continue
        for edge_name, obstacle_area in edge_map.items():
            if "->" not in edge_name:
                continue
            u, v = [part.strip() for part in edge_name.split("->", 1)]
            if G.has_edge(u, v):
                G[u][v]["obstacle_area"] = float(obstacle_area)
                G[u][v]["obstacle_line"] = line_id


def _path_total_length(G, path):
    if not path or len(path) <= 1:
        return 0.0
    return sum(float(G[path[i]][path[i + 1]].get("length", 0.0)) for i in range(len(path) - 1))


def run_single_path_case_suite(
    G_base,
    case_specs=None,
    evacuees=SINGLE_PATH_CASE_POPULATION,
    methods=(PAPER_SINGLE_PATH_METHOD, ANT_COLONY_METHOD, OUR_SINGLE_PATH_METHOD),
    long_csv="15_single_path_case_results.csv",
    wide_csv="16_single_path_case_comparison.csv",
    summary_csv="17_single_path_case_summary.csv",
    plot_file="18_single_path_case_metrics.png",
):
    case_specs = case_specs or SINGLE_PATH_CASE_SPECS
    long_rows = []

    for case_spec in case_specs:
        case_state = build_single_path_case_state(G_base, case_spec, evacuees=evacuees)
        shortest_dists = dict(nx.all_pairs_dijkstra_path_length(case_state, weight="length"))

        for method in methods:
            metrics = run_simulation_for_existing_state(
                case_state,
                method=method,
                target_by_line={case_spec["line"]: float(evacuees)},
            )
            if method == ANT_COLONY_METHOD:
                path = standard_aco_pathfinder(case_state, case_spec["origin"], shortest_dists, fruin_speed)
            else:
                path = get_best_path_to_exit(case_state, case_spec["origin"], method, shortest_dists)
            target_exit = path[-1] if path else None
            long_rows.append(
                {
                    "case_id": case_spec["case_id"],
                    "line": case_spec["line"],
                    "origin": case_spec["origin"],
                    "start_role": case_spec["start_role"],
                    "evacuees": float(evacuees),
                    "method": _normalize_method(method),
                    "method_label": _method_display_name(method),
                    "target_exit": target_exit,
                    "path": format_path(path),
                    "path_length": _path_total_length(case_state, path),
                    "evacuation_time": metrics["time"],
                    "queueing_time": metrics["queueing_time"],
                    "congestion_exposure_time": metrics["congestion_exposure_time"],
                    "avg_speed": metrics["avg_speed"],
                }
            )

    long_df = pd.DataFrame(long_rows)
    long_df.to_csv(long_csv, index=False, encoding="utf-8-sig")

    wide_df = (
        long_df.pivot_table(
            index=["case_id", "line", "origin", "start_role", "evacuees"],
            columns="method",
            values=[
                "target_exit",
                "path",
                "path_length",
                "evacuation_time",
                "queueing_time",
                "congestion_exposure_time",
                "avg_speed",
            ],
            aggfunc="first",
        )
        .sort_index()
    )
    wide_df.columns = [f"{metric}_{method}" for metric, method in wide_df.columns]
    wide_df = wide_df.reset_index()
    wide_df.to_csv(wide_csv, index=False, encoding="utf-8-sig")

    summary_df = (
        long_df.groupby(["line", "method", "method_label"])
        .agg(
            case_count=("case_id", "count"),
            mean_path_length=("path_length", "mean"),
            mean_evacuation_time=("evacuation_time", "mean"),
            mean_queueing_time=("queueing_time", "mean"),
            mean_congestion_exposure=("congestion_exposure_time", "mean"),
            mean_avg_speed=("avg_speed", "mean"),
        )
        .reset_index()
    )
    summary_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")

    method_order = [_normalize_method(m) for m in methods]
    case_order = [spec["case_id"] for spec in case_specs]
    pivot_time = long_df.pivot(index="case_id", columns="method", values="evacuation_time").reindex(case_order)
    pivot_queue = long_df.pivot(index="case_id", columns="method", values="queueing_time").reindex(case_order)
    pivot_exposure = long_df.pivot(index="case_id", columns="method", values="congestion_exposure_time").reindex(case_order)

    fig, axes = plt.subplots(3, 1, figsize=(14, 13), sharex=True)
    x = np.arange(len(case_order))
    width = min(0.25, 0.8 / max(len(method_order), 1))
    colors = ["#4E79A7", "#59A14F", "#F28E2B", "#B07AA1"]
    metrics_plot = [
        (pivot_time, "Evacuation time (s)", axes[0]),
        (pivot_queue, "Queueing time (person*s)", axes[1]),
        (pivot_exposure, "Congestion exposure (person*s)", axes[2]),
    ]

    for plot_idx, (pivot_df, ylabel, ax) in enumerate(metrics_plot):
        for method_idx, method in enumerate(method_order):
            vals = pivot_df[method].to_numpy(dtype=float)
            offset = (method_idx - (len(method_order) - 1) / 2.0) * width
            ax.bar(
                x + offset,
                vals,
                width=width,
                color=colors[method_idx % len(colors)],
                edgecolor="black",
                label=_method_display_name(method),
            )
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", linestyle="--", alpha=0.5)
        if plot_idx == 0:
            ax.legend()

    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(case_order, rotation=25, ha="right")
    fig.suptitle(
        f"Literature-Style Single-Path Benchmark ({int(evacuees)} evacuees per case, 12 cases)",
        fontsize=16,
        fontweight="bold",
    )
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(plot_file, dpi=300, bbox_inches="tight")
    plt.close()

    return long_df, wide_df, summary_df



def plot_detailed_dynamics_by_line(G_base, metrics_trad, metrics_imp, pop_dict):
    """方案A：按文献口径画等待区队列与关键设施旅行时间。"""
    lines = [l for l, d in pop_dict.items() if sum(d.values()) > 0]
    if not lines: return

    # ==== 1. 各线路等待区队列长度 + 占用率 ====
    fig, axes = plt.subplots(math.ceil(len(lines) / 2), 2, figsize=(16, 5 * math.ceil(len(lines) / 2)))
    fig.suptitle('各线路等待区队列长度与占用率动态演化对比', fontsize=20, fontweight='bold', y=0.95)
    axes = np.atleast_1d(axes).flatten()

    for idx, line in enumerate(lines):
        ax = axes[idx]
        times_trad, q_trad, nodes_trad = _aggregate_line_node_series(G_base, metrics_trad, line, "queue", normalize_by_area=False)
        times_imp, q_imp, nodes_imp = _aggregate_line_node_series(G_base, metrics_imp, line, "queue", normalize_by_area=False)
        _, occ_trad, _ = _aggregate_line_node_series(G_base, metrics_trad, line, "queue", normalize_by_area=True)
        _, occ_imp, _ = _aggregate_line_node_series(G_base, metrics_imp, line, "queue", normalize_by_area=True)

        q_trad = _smooth_display_series(q_trad, window=5)
        q_imp = _smooth_display_series(q_imp, window=5)
        occ_trad = _smooth_display_series(occ_trad, window=5)
        occ_imp = _smooth_display_series(occ_imp, window=5)

        ax2 = ax.twinx()
        ax.plot(times_trad, q_trad, 'r-', linewidth=2.2, label="Traditional 队列长度", alpha=0.85)
        ax.plot(times_imp, q_imp, 'g-', linewidth=2.2, label="OurSinglePath 队列长度")
        ax2.plot(times_trad, occ_trad, 'r--', linewidth=1.8, label="Traditional 占用率", alpha=0.65)
        ax2.plot(times_imp, occ_imp, 'g--', linewidth=1.8, label="OurSinglePath 占用率")

        node_hint = ", ".join(nodes_trad[:3]) if nodes_trad else "no-queue-node"
        ax.set_title(f'{line} 等待区排队\n[{node_hint}]', fontsize=13, fontweight='bold')
        ax.set_xlabel('时间 (s)')
        ax.set_ylabel('队列长度 (人)')
        ax2.set_ylabel('等待区占用率 (人/㎡)')
        ax.grid(True, linestyle=":", alpha=0.7)

        handles1, labels1 = ax.get_legend_handles_labels()
        handles2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(handles1 + handles2, labels1 + labels2, loc="upper right", fontsize=9)

    # 隐藏多余的子图
    for idx in range(len(lines), len(axes)): fig.delaxes(axes[idx])
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    plt.savefig("03_System_Line_Queue_Dynamics.png", dpi=300, bbox_inches='tight')
    plt.close()

    # ==== 2. 各线路关键设施实际旅行时间 ====
    fig, axes = plt.subplots(math.ceil(len(lines) / 2), 2, figsize=(16, 5 * math.ceil(len(lines) / 2)))
    fig.suptitle('各线路关键设施实际旅行时间动态演化对比', fontsize=20, fontweight='bold', y=0.95)
    axes = np.atleast_1d(axes).flatten()

    for idx, line in enumerate(lines):
        ax = axes[idx]
        times_trad, travel_trad, nodes_trad = _aggregate_line_node_series(G_base, metrics_trad, line, "travel_time", normalize_by_area=False)
        times_imp, travel_imp, nodes_imp = _aggregate_line_node_series(G_base, metrics_imp, line, "travel_time", normalize_by_area=False)
        travel_trad = _smooth_display_series(travel_trad, window=5)
        travel_imp = _smooth_display_series(travel_imp, window=5)

        node_hint = ", ".join(nodes_trad[:3]) if nodes_trad else "no-queue-node"

        ax.plot(times_trad, travel_trad, 'r-', linewidth=2.5, label="Traditional (传统)", alpha=0.85)
        ax.plot(times_imp, travel_imp, 'b-', linewidth=2.8, label="OurSinglePath")

        ax.set_title(f'{line} 关键设施旅行时间\n[{node_hint}]', fontsize=13, fontweight='bold')
        ax.set_xlabel('时间 (s)')
        ax.set_ylabel('实际旅行时间 (s)')
        ax.grid(True, linestyle=":", alpha=0.7)
        ax.legend()

    for idx in range(len(lines), len(axes)): fig.delaxes(axes[idx])
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    plt.savefig("04_System_Line_Speed_Dynamics.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_article_style_dynamics_multi(G_base, method_metrics, pop_dict):
    """【三算法同台竞技版】输出关键节点排队与链路速度的 3 线对比折线图 (X轴为秒)"""
    lines = [l for l, d in pop_dict.items() if sum(d.values()) > 0]
    if not lines:
        return

    # 使用传统算法(基准)来定位全站最严重的 16 个瓶颈节点和链路
    ref_metrics = method_metrics[0][1]
    article_edges = _select_article_links(ref_metrics, top_k=16)
    article_nodes = _select_article_nodes(ref_metrics, top_k=16)

    # 定义三算法颜色: 传统(红), 文献(橙), 本文(蓝)
    color_map = ['#E63946', '#F4A261', '#457B9D']

    # ==== Fig.13: 关键链路有效速度 3线对比 ====
    fig, axes = plt.subplots(4, 4, figsize=(18, 16))
    fig.suptitle("关键链路有效速度动态演化 (三算法对比)", fontsize=20, fontweight="bold", y=0.95)
    axes = np.atleast_1d(axes).flatten()

    for idx in range(16):
        ax = axes[idx]
        if idx >= len(article_edges):
            ax.axis("off")
            continue
        edge_key = article_edges[idx]

        # 在同一个子图里画 3 条线
        for m_idx, (label, metrics) in enumerate(method_metrics):
            series = metrics.get("edge_series", {}).get(edge_key, {})
            times = np.array(series.get("times", []), dtype=float)  # 保留为秒
            speeds = np.array(series.get("speed", []), dtype=float)
            speeds = _smooth_display_series(speeds, window=5)
            if times.size > 0:
                ax.plot(times, speeds, color=color_map[m_idx], linewidth=1.8, label=label)

        ax.set_title(edge_key.replace(" -> ", "\n"), fontsize=9, fontweight="bold")
        ax.set_xlabel("Time (s)")  # 已改为秒
        ax.set_ylabel("Speed (m/s)")
        ax.grid(True, linestyle=":", alpha=0.6)
        if idx == 0:  # 只在第一个图显示图例避免遮挡
            ax.legend(fontsize=8, loc="upper right")

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    plt.savefig("07_System_Link_Speed_3Way_Dynamics.png", dpi=300, bbox_inches="tight")
    plt.close()

    # ==== Fig.14: 关键节点排队长度 3线对比 ====
    fig, axes = plt.subplots(4, 4, figsize=(18, 16))
    fig.suptitle("关键节点排队长度动态演化 (三算法对比)", fontsize=20, fontweight="bold", y=0.95)
    axes = np.atleast_1d(axes).flatten()

    for idx in range(16):
        ax = axes[idx]
        if idx >= len(article_nodes):
            ax.axis("off")
            continue
        node = article_nodes[idx]

        # 在同一个子图里画 3 条线
        max_q = 0
        for m_idx, (label, metrics) in enumerate(method_metrics):
            times, queues = _get_node_series(metrics, node, "queue")
            queues = _smooth_display_series(queues, window=5)
            if times.size > 0:
                ax.plot(times, queues, color=color_map[m_idx], linewidth=2.0, label=label)
                if len(queues) > 0 and not np.isnan(queues).all():
                    max_q = max(max_q, np.nanmax(queues))

        ax.set_title(node, fontsize=9, fontweight="bold")
        ax.set_xlabel("Time (s)")  # 已改为秒
        ax.set_ylabel("Queue length (person)")
        ax.set_ylim(bottom=-2, top=max(max_q * 1.1, 10))  # 动态调整Y轴高度
        ax.grid(True, linestyle=":", alpha=0.6)
        if idx == 0:
            ax.legend(fontsize=8, loc="upper right")

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    plt.savefig("08_System_Node_Queue_3Way_Dynamics.png", dpi=300, bbox_inches="tight")
    plt.close()

def get_evacuation_mode():
    print("\n" + "=" * 60)
    print("🚇 欢迎使用龙阳路站高精度客流仿真控制台")
    print("=" * 60)
    print("请选择客流加载模式：\n")
    print("  [1] 常规突发 (仅原有人员：站台 + 站厅 + 换乘)")
    print("  [2] 单向迫停 - 上行 (仅上行 Train 1 满载开门 + 原有人员)")
    print("  [3] 单向迫停 - 下行 (仅下行 Train 2 满载开门 + 原有人员)")
    print("  [4] 极限地狱 - 双向满载 (上下行列车同时开门 + 原有人员)")
    print("-" * 60)
    while True:
        choice = input("👉 请输入序号 [1 / 2 / 3 / 4] 并按回车: ").strip()
        if choice in ['1', '2', '3', '4']:
            return int(choice)
        print("❌ 输入无效，请重新输入！")


def get_experiment_mode():
    print("\n" + "=" * 60)
    print("🧪 请选择实验类型：\n")
    print("  [1] 系统层四场景仿真 (四条线路联动)")
    print("  [2] 单路径 100 人基准实验")
    print("-" * 60)
    while True:
        choice = input("👉 请输入序号 [1 / 2] 并按回车: ").strip()
        if choice in ['1', '2']:
            return int(choice)
        print("❌ 输入无效，请重新输入！")


def run_single_path_benchmark_workflow(G):
    print("\n📘 正在运行文献式单路径基准实验 (12组案例, 每组100人, 单源-多出口)...")
    single_long_df, single_wide_df, single_summary_df = run_single_path_case_suite(G)
    print(f"   已生成: 15_single_path_case_results.csv ({len(single_long_df)} rows)")
    print(f"   已生成: 16_single_path_case_comparison.csv ({len(single_wide_df)} cases)")
    print(f"   已生成: 17_single_path_case_summary.csv")
    print(f"   已生成: 18_single_path_case_metrics.png")


def run_system_mode_workflow(G):
    mode = get_evacuation_mode()
    STATION_BASE_LOADS = {
        "L2": {"platform_waiting": 236, "hall_people": 350, "transfer_people": 526},
        "L7": {"platform_waiting": 219, "hall_people": 112, "transfer_people": 169},
        "L16": {"platform_waiting": 42, "hall_people": 15, "transfer_people": 27},
        "L18": {"platform_waiting": 178, "hall_people": 125, "transfer_people": 188},
        "Maglev": {"platform_waiting": 0, "hall_people": 0, "transfer_people": 0},
    }

    current_pop_dict, total_p = {}, 0
    for line, physics in TRAIN_PHYSICS.items():
        base = STATION_BASE_LOADS[line]
        train_total = int(round(_train_total_people(physics)))

        if mode == 1:
            t1, t2 = 0, 0
        elif mode == 2:
            t1, t2 = train_total, 0
        elif mode == 3:
            t1, t2 = 0, train_total
        else:
            t1, t2 = train_total, train_total

        pw = int(base["platform_waiting"])
        hp = int(base["hall_people"])
        tp = int(base["transfer_people"])

        current_pop_dict[line] = {
            "train_1": t1,
            "train_2": t2,
            "platform_waiting": pw,
            "hall_people": hp,
            "transfer_people": tp
        }
        total_p += (t1 + t2 + pw + hp + tp)

    print(f"\n==== 目标客流: {total_p} 人 ====")

    aco_state = copy.deepcopy(G)
    init_people(aco_state, current_pop_dict, apply_noise=False)
    aco_targets = {
        line: sum(d.values())
        for line, d in current_pop_dict.items()
        if sum(d.values()) > 0
    }
    aco_start_ts = time.perf_counter()
    # 核心修改：使用普通的 run_simulation_for_metrics_timed，和你的 A* 待遇一样
    metrics_aco = run_simulation_for_metrics_timed(aco_state, current_pop_dict, method=ANT_COLONY_METHOD)
    # 墙上时间已在 timed 里记录，无需重复相减，直接保持原样覆盖即可
    metrics_paper = run_simulation_for_metrics_timed(G, current_pop_dict, method=PAPER_SINGLE_PATH_METHOD)
    metrics_guided = run_simulation_for_metrics_timed(G, current_pop_dict, method=OUR_SINGLE_PATH_METHOD)

    critical_facility = "Escalator_L2_up1"
    G_disrupted = copy.deepcopy(G)
    if critical_facility in G_disrupted.nodes:
        _apply_node_disruption(G_disrupted, critical_facility, factor=0.0)
        print(f"\n🔧 扰动设施已固定为: {critical_facility} (节点及其相连通路中断)")
    else:
        raise ValueError(f"扰动设施 {critical_facility} 不存在，请检查网络拓扑。")
    metrics_guided_disrupted = run_simulation_for_metrics_timed(G_disrupted, current_pop_dict, method=OUR_SINGLE_PATH_METHOD)

    print(
        f"[ACO] 总排队 {metrics_aco['queueing_time']:.1f} 人·秒 | "
        f"中度拥挤暴露 {metrics_aco['congestion_exposure_time']:.1f} 人·秒 | "
        f"重度拥挤暴露 {metrics_aco.get('severe_congestion_exposure_time', 0.0):.1f} 人·秒 | "
        f"全站时间 {metrics_aco['time']:.1f}s | 实际运行 {metrics_aco['wall_clock_runtime_s']:.2f}s"
    )
    print(
        f"[ImprovedAStar] 总排队 {metrics_paper['queueing_time']:.1f} 人·秒 | "
        f"中度拥挤暴露 {metrics_paper['congestion_exposure_time']:.1f} 人·秒 | "
        f"重度拥挤暴露 {metrics_paper.get('severe_congestion_exposure_time', 0.0):.1f} 人·秒 | "
        f"全站时间 {metrics_paper['time']:.1f}s | 实际运行 {metrics_paper['wall_clock_runtime_s']:.2f}s"
    )
    print(
        f"[OurSinglePath] 总排队 {metrics_guided['queueing_time']:.1f} 人·秒 | "
        f"中度拥挤暴露 {metrics_guided['congestion_exposure_time']:.1f} 人·秒 | "
        f"重度拥挤暴露 {metrics_guided.get('severe_congestion_exposure_time', 0.0):.1f} 人·秒 | "
        f"全站时间 {metrics_guided['time']:.1f}s | 实际运行 {metrics_guided['wall_clock_runtime_s']:.2f}s"
    )
    method_metrics = [
        ("ACO", metrics_aco),
        ("ImprovedAStar", metrics_paper),
        ("OurSinglePath", metrics_guided),
    ]
    summary_rows = []
    active_lines = [line for line, vals in current_pop_dict.items() if sum(vals.values()) > 0]
    for label, met in method_metrics:
        summary_rows.append({
            "method": label,
            "queueing_time": met["queueing_time"],
            "congestion_exposure_time": met["congestion_exposure_time"],
            "moderate_congestion_exposure_time": met["congestion_exposure_time"],
            "severe_congestion_exposure_time": met.get("severe_congestion_exposure_time", 0.0),
            "time": met["time"],
            "avg_speed": met["avg_speed"],
            "wall_clock_runtime_s": met.get("wall_clock_runtime_s"),
    })
    pd.DataFrame(summary_rows).to_csv("02_system_method_summary.csv", index=False, encoding="utf-8-sig")
    line_rows = []
    for label, met in method_metrics:
        for line in active_lines:
            line_rows.append({
                "method": label,
                "line": line,
                "clearance_time": met["clearance_times_by_line"].get(line) if met["clearance_times_by_line"].get(line) is not None else met["time"],
                "congestion_exposure_time": met["congestion_exposure_by_line"].get(line, 0.0),
                "moderate_congestion_exposure_time": met["congestion_exposure_by_line"].get(line, 0.0),
            })
    pd.DataFrame(line_rows).to_csv("03_system_line_summary.csv", index=False, encoding="utf-8-sig")
    print("\n📊 正在生成论文式关键链路/关键节点图 (三算法速度、队列对比)...")
    plot_article_style_dynamics_multi(G, method_metrics, current_pop_dict)
    print("\n📈 正在生成整体疏散完成曲线图...")
    plot_system_evacuation_curve(method_metrics, total_p)
    print("\n📊 正在生成宏观指标深度对比图 (Bar柱状图与消散折线图)...")
    plot_charts_multi(G, method_metrics, total_p)

    print("\n📊 正在生成各线路专属清空分析图表...")
    plot_line_specific_analysis_multi(method_metrics, current_pop_dict)

    print("\n🔍 正在生成抗拥挤的高清热力快照 (请稍候)...")
    plot_comparative_snapshots(
        G,
        pop_dict=current_pop_dict,
        time_points=[30, 90, 200],
        methods=[
            ("ACO", ANT_COLONY_METHOD, "ACO (蚁群优化基线)"),
            ("ImprovedAStar", PAPER_SINGLE_PATH_METHOD, "ImprovedAStar (文献改进A*)"),
            ("OurSinglePath", OUR_SINGLE_PATH_METHOD, "OurSinglePath (动态单路径方法)"),
        ],
    )

    print("\n📝 正在生成三算法事件日志与瓶颈追踪CSV...")
    source_nodes = [n for n, d in G.nodes(data=True) if d.get("type") in {"stair", "escalator"}]
    route_df, _, _ = collect_route_event_log_three_methods(
        G_base=G,
        pop_dict=current_pop_dict,
        source_nodes=source_nodes,
        target_time=2000,
        filename="10_route_event_log_three_methods.csv",
        verbose=False,
    )
    summarize_route_changes_by_line(route_df, "11_route_change_summary_by_line.csv")
    summarize_bottlenecks_from_events(route_df, "aco", "12_bottlenecks_aco.csv")
    summarize_bottlenecks_from_events(route_df, "paper", "13_bottlenecks_improved_astar.csv")
    summarize_bottlenecks_from_events(route_df, "our", "14_bottlenecks_our_single_path.csv")
    plot_divergence_timeline(route_df, "15_divergence_timeline_three_methods.png", bin_size=10)
    print("\n📝 正在提取各线路(Profile)去往各出口的精细匹配数据...")
    exit_dest_rows = []
    for label, met in method_metrics:
        for ext, lines_ppl in met["exit_usage_by_line"].items():
            for line_id, count in lines_ppl.items():
                if count > 0:
                    exit_dest_rows.append({
                        "Method": label,
                        "Exit_Name": ext.replace("Exit_", ""),
                        "Profile_Line": line_id,
                        "Evacuated_People": round(count, 1),
                    })
    pd.DataFrame(exit_dest_rows).to_csv("16_Profile_to_Exit_Distribution.csv", index=False, encoding="utf-8-sig")
    print("\n✅ 所有的深度分析图表和日志已完美生成！")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    G = build_graph()
    experiment_mode = get_experiment_mode()
    if experiment_mode == 1:
        plot_initial_topology(G)
        run_system_mode_workflow(G)
    else:
        run_single_path_benchmark_workflow(G)
