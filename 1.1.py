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

from calc_platform_dists import PATHFINDER_CONFIG


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
def _edge_dynamic_cost(G, u, v, method):
    data = G[u][v]
    L = data["length"]
    walk_time_base = L / 1.427

    if method == "Improved":
        node_type = G.nodes[v].get("type", "")
        people_at_v = G.nodes[v].get("people", 0)

        if "gate" in node_type or "exit" in node_type or "virtual" in node_type:
            mu = G.nodes[v].get("capacity", 1.0)
            return walk_time_base + 1.5 * (people_at_v / max(mu, 0.001))

        density = people_at_v / max(G.nodes[v].get("area", 1.0), 0.001)
        safe_speed = max(fruin_speed(density), 0.1)
        return (L / safe_speed) * 3.0 if density > 3.0 else (L / safe_speed)

    return L


def update_dynamic_weights(G, method):
    weight_key = "sim_weight"
    for u, v, data in G.edges(data=True):
        data[weight_key] = _edge_dynamic_cost(G, u, v, method)


def get_split_next_moves(G, current_node, method, shortest_dists, max_branches=3, score_band=1.25):
    """
    返回当前节点本步应该走向多个后继节点的流量分配结果。
    这里不是只挑一个 next node，而是按“接近最优”的多个后继分流。
    """
    exits = [n for n, d in G.nodes(data=True) if d.get("type") == "exit"]
    if not exits:
        return []

    successors = list(G.successors(current_node))
    if not successors:
        return []

    scored = []
    for v in successors:
        edge_cost = G[current_node][v].get("sim_weight", G[current_node][v]["length"])
        downstream = min(
            (shortest_dists.get(v, {}).get(ext, float("inf")) for ext in exits),
            default=float("inf")
        )

        if math.isinf(edge_cost) and math.isinf(downstream):
            continue

        total_cost = edge_cost + 0.10 * downstream
        scored.append((v, total_cost))

    if not scored:
        return []

    scored.sort(key=lambda x: x[1])
    best_cost = scored[0][1]

    picked = [
        item for item in scored
        if item[1] <= best_cost * score_band or item[1] <= best_cost + 5.0
    ][:max_branches]

    if not picked:
        picked = scored[:1]

    remaining = float(G.nodes[current_node].get("people", 0))
    if remaining <= 0:
        return []

    capacity_left = {
        v: G[current_node][v]["capacity"] * DELTA_T
        for v, _ in picked
    }
    score_map = {v: max(cost, 1e-6) for v, cost in picked}

    moves = []
    active = [v for v, _ in picked]

    while remaining > 1e-9 and active:
        inv = {v: 1.0 / score_map[v] for v in active}
        total_inv = sum(inv.values())
        if total_inv <= 0:
            break

        proposed = {v: remaining * inv[v] / total_inv for v in active}

        allocated = 0.0
        saturated = []

        for v in active:
            flow = min(proposed[v], capacity_left[v])
            if flow > 0:
                moves.append((current_node, v, flow))
                allocated += flow
                capacity_left[v] -= flow

            if capacity_left[v] <= 1e-9:
                saturated.append(v)

        if allocated <= 1e-9:
            break

        remaining -= allocated
        active = [v for v in active if capacity_left[v] > 1e-9]

    return moves


def get_step_moves(G, method, shortest_dists):
    """
    传统算法：保持单路径最短路，不做多路分流。
    改进算法：允许按多个接近最优的后继并行分流。
    """
    active_nodes = [
        n for n in G.nodes()
        if G.nodes[n].get("people", 0) > 0.1 and G.nodes[n].get("type") != "exit"
    ]

    moves = []

    if method == "Traditional":
        # 保持你原来的传统逻辑：每个节点每秒只选一个下一跳
        for u in active_nodes:
            v = get_best_next_node(G, u, method, shortest_dists)
            if v:
                flow = min(G.nodes[u]["people"], G[u][v]["capacity"] * DELTA_T)
                if flow > 0:
                    moves.append((u, v, flow))
        return moves

    # 改进算法才做多路并行分流
    update_dynamic_weights(G, method)
    for u in active_nodes:
        moves.extend(get_split_next_moves(G, u, method, shortest_dists))

    return moves


# 🌟 从配置文件导入纯数据
from lines_config import NODES_DATA, EDGES_DATA, STATION_LEVELS, PLATFORM_VERTICAL_SPECS, PRECALCULATED_PLATFORM_DISTS
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
DELTA_T = 1.0
ALL_LINE_IDS = ["L2", "L7", "L16", "L18", "Maglev"]
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
    if density <= 0.2:
        return 1.427
    elif density <= 3.0:
        return 1.427 - 0.3549 * density
    else:
        return 0.01


# ==============================================================================
# 3. 动态建图与改进放人引擎
# ==============================================================================
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
                cap_out = calculate_gb_capacity_per_second("passageway", w_down)
                G.add_node(name, pos=pos, type=ftype, width=w_down, capacity=cap_out, area=measured_area, people=0)

     # 3. 动态构建 站台->垂直设施 的边
    for line_id, spec in PLATFORM_VERTICAL_SPECS.items():
        platform_node = spec["platform_node"]
        vertical_group = spec["vertical_group"]

        if vertical_group not in NODES_DATA:
            raise ValueError(f"\n[配置致命错误] 线路 '{line_id}' 引用了不存在的垂直设施组 '{vertical_group}'！")

        delta_h = get_delta_h(line_id)

        for v_name in NODES_DATA[vertical_group].keys():
            if v_name not in PRECALCULATED_PLATFORM_DISTS:
                raise ValueError(f"\n[数据缺失]：字典中未找到 '{v_name}' 的距离，请检查 calc_platform_dists.py！")

            horizontal_dist = PRECALCULATED_PLATFORM_DISTS[v_name]
            total_edge_length = horizontal_dist + 2.0 * delta_h
            G.add_edge(platform_node, v_name, length=total_edge_length, capacity=G.nodes[v_name]["capacity"], edge_type="platform_to_vertical")

    # 4. 读取其余静态边
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

                for door_idx in range(1, door_count + 1):
                    door_node = f"{car_node}_Door{door_idx}"
                    door_pos = _layout_point_from_span(train_span, car_idx, door_idx, car_count, door_count, platform_pos)

                    G.add_node(
                        door_node,
                        type="train",
                        capacity=999999,
                        area=max(car_area / door_count, 1.0),
                        people=0,
                        pos=door_pos,
                        line_id=line_id,
                        train_index=train_idx,
                        car_index=car_idx,
                        door_index=door_idx,
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
                        p_node,
                        length=1.0,
                        capacity=door_capacity,
                        edge_type="train_door",
                    )

    return G



def init_people(G, pop_dict, apply_noise=False, rng=None):
    # 重置清空
    for n in G.nodes():
        G.nodes[n]["people"] = 0.0
        G.nodes[n]["people_dict"] = {l: 0.0 for l in ALL_LINE_IDS}

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
                    car_nodes = _sorted_train_car_nodes(G, line_id, train_idx)
                    total_people = float(line_data.get(key, 0))

                    if not car_nodes or total_people <= 0:
                        continue

                    base_share = total_people / len(car_nodes)
                    allocated = 0.0

                    for i, car_node in enumerate(car_nodes):
                        if i < len(car_nodes) - 1:
                            assigned = base_share
                            allocated += assigned
                        else:
                            assigned = total_people - allocated

                        G.nodes[car_node]["people"] = assigned
                        G.nodes[car_node]["people_dict"][line_id] = assigned
            else:
                if f"Train_{line_id}_1" in G.nodes:
                    G.nodes[f"Train_{line_id}_1"]["people"] = line_data.get("train_1", 0)
                    G.nodes[f"Train_{line_id}_1"]["people_dict"][line_id] = line_data.get("train_1", 0)
                if f"Train_{line_id}_2" in G.nodes:
                    G.nodes[f"Train_{line_id}_2"]["people"] = line_data.get("train_2", 0)
                    G.nodes[f"Train_{line_id}_2"]["people_dict"][line_id] = line_data.get("train_2", 0)

            # 2. 放入【站台】
            G.nodes[p_node]["people"] = line_data.get("platform_waiting", 0)
            G.nodes[p_node]["people_dict"][line_id] = line_data.get("platform_waiting", 0)

            # 3. 放入【站厅闸机区】
            hall_people = line_data.get("hall_people", 0)
            gate_group_name = spec.get("gate_group", f"{line_id}_GATES")
            valid_gates = [n for n in NODES_DATA.get(gate_group_name, {}) if n in G.nodes]

            if valid_gates and hall_people > 0:
                base_weights = [G.nodes[n].get("capacity", 1.0) for n in valid_gates]
                total_w = sum(base_weights)
                if total_w > 0:
                    for n, w in zip(valid_gates, base_weights):
                        assigned_ppl = hall_people * (w / total_w)
                        G.nodes[n]["people"] += assigned_ppl
                        G.nodes[n]["people_dict"][line_id] += assigned_ppl

            # 4. 放入【换乘通道区】
            transfer_people = line_data.get("transfer_people", 0)
            valid_transfers = []
            if "TRANSFERS" in NODES_DATA:
                for t_node in NODES_DATA["TRANSFERS"].keys():
                    if line_id in t_node and t_node in G.nodes:
                        valid_transfers.append(t_node)

            if valid_transfers and transfer_people > 0:
                base_weights = [G.nodes[n].get("capacity", 1.0) for n in valid_transfers]
                total_w = sum(base_weights)
                if total_w > 0:
                    for n, w in zip(valid_transfers, base_weights):
                        assigned_ppl = transfer_people * (w / total_w)
                        G.nodes[n]["people"] += assigned_ppl
                        G.nodes[n]["people_dict"][line_id] += assigned_ppl



def apply_capacity_noise(G, rng, low=0.95, high=1.05):
    for u, v, edge_data in G.edges(data=True):
        if "capacity" in edge_data and edge_data["capacity"] != float("inf"):
            edge_data["capacity"] *= rng.uniform(low, high)


# ==============================================================================
# 4. 动态仿真与路径算法
# ==============================================================================
def heuristic_hn(u, v, d_dict): return 0.10 * d_dict.get(u, {}).get(v, 0)


def get_best_next_node(G, current_node, method, shortest_dists):
    exits = [n for n, d in G.nodes(data=True) if d.get('type') == 'exit']
    if not exits: return None

    weight_key = 'sim_weight'
    for u, v, data in G.edges(data=True):
        L = data['length']
        walk_time_base = L / 1.427

        if method == "Improved":
            node_type = G.nodes[v].get('type', '')
            people_at_v = G.nodes[v].get('people', 0)
            if "gate" in node_type or "exit" in node_type or "virtual" in node_type:
                mu = G.nodes[v].get('capacity', 1.0)
                data[weight_key] = 1.0 * walk_time_base + 1.5 * (people_at_v / max(mu, 0.001))
            else:
                density = people_at_v / G.nodes[v].get('area', 1.0)
                safe_speed = max(fruin_speed(density), 0.1)
                data[weight_key] = (L / safe_speed) * 3.0 if density > 3.0 else (L / safe_speed)
        else:
            data[weight_key] = L

    best_next, min_cost = None, float('inf')

    for target in exits:
        try:
            path = nx.astar_path(G, current_node, target, heuristic=lambda u, v: heuristic_hn(u, v, shortest_dists),
                                 weight=weight_key) if method == "Improved" else nx.shortest_path(G, current_node,
                                                                                                  target,
                                                                                                  weight=weight_key)
            if len(path) > 1:
                cost = sum(G[path[i]][path[i + 1]][weight_key] for i in range(len(path) - 1))
                if cost < min_cost: min_cost, best_next = cost, path[1]
        except nx.NetworkXNoPath:
            continue
    return best_next

def update_dynamic_weights(G, method):
    weight_key = "sim_weight"
    for u, v, data in G.edges(data=True):
        L = data["length"]
        walk_time_base = L / 1.427

        if method == "Improved":
            node_type = G.nodes[v].get("type", "")
            people_at_v = G.nodes[v].get("people", 0)

            if "gate" in node_type or "exit" in node_type or "virtual" in node_type:
                mu = G.nodes[v].get("capacity", 1.0)
                data[weight_key] = walk_time_base + 1.5 * (people_at_v / max(mu, 0.001))
            else:
                density = people_at_v / G.nodes[v].get("area", 1.0)
                safe_speed = max(fruin_speed(density), 0.1)
                data[weight_key] = (L / safe_speed) * 3.0 if density > 3.0 else (L / safe_speed)
        else:
            data[weight_key] = L


def get_best_path_to_exit(G, current_node, method, shortest_dists):
    exits = [n for n, d in G.nodes(data=True) if d.get("type") == "exit"]
    if not exits:
        return None

    update_dynamic_weights(G, method)
    weight_key = "sim_weight"

    best_path = None
    min_cost = float("inf")

    for target in exits:
        try:
            if method == "Improved":
                path = nx.astar_path(
                    G,
                    current_node,
                    target,
                    heuristic=lambda u, v: heuristic_hn(u, v, shortest_dists),
                    weight=weight_key
                )
            else:
                path = nx.shortest_path(G, current_node, target, weight=weight_key)

            if len(path) > 1:
                cost = sum(G[path[i]][path[i + 1]][weight_key] for i in range(len(path) - 1))
                if cost < min_cost:
                    min_cost = cost
                    best_path = path
        except nx.NetworkXNoPath:
            continue

    return best_path

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


def save_route_comparison_table(G_trad, G_imp, shortest_dists, source_nodes, filename):
    rows = []
    for src in source_nodes:
        trad_path = get_best_path_to_exit(G_trad, src, "Traditional", shortest_dists)
        imp_path = get_best_path_to_exit(G_imp, src, "Improved", shortest_dists)

        trad_len = sum(G_trad[trad_path[i]][trad_path[i + 1]]["length"] for i in range(len(trad_path) - 1)) if trad_path else None
        imp_len = sum(G_imp[imp_path[i]][imp_path[i + 1]]["length"] for i in range(len(imp_path) - 1)) if imp_path else None

        rows.append({
            "source": src,
            "traditional_path": format_path(trad_path),
            "improved_path": format_path(imp_path),
            "first_divergence": first_divergence(trad_path, imp_path),
            "trad_length": trad_len,
            "imp_length": imp_len,
            "length_reduction_pct": ((trad_len - imp_len) / trad_len * 100) if trad_len and imp_len and trad_len > 0 else 0.0
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
    """推进单个仿真步。支持一个节点同时向多个后继分流。"""
    moves = get_step_moves(G, method, shortest_dists)

    for u, v, amount in moves:
        G.nodes[u]["people"] -= amount
        G.nodes[v]["people"] += amount

    return moves



def collect_route_event_log(G_base, pop_dict, source_nodes, target_time, filename, verbose=False):
    """只记录“路由发生变化”的事件，不记录每一秒。"""
    G_trad = copy.deepcopy(G_base)
    G_imp = copy.deepcopy(G_base)

    init_people(G_trad, pop_dict, apply_noise=False)
    init_people(G_imp, pop_dict, apply_noise=False)

    shortest_dists = dict(nx.all_pairs_dijkstra_path_length(G_base, weight="length"))
    prev_trad = {src: None for src in source_nodes}
    prev_imp = {src: None for src in source_nodes}
    rows = []

    time = 0
    while time <= target_time:
        trad_hot = rank_instantaneous_bottlenecks(G_trad, top_k=1)
        imp_hot = rank_instantaneous_bottlenecks(G_imp, top_k=1)

        trad_hot_node = trad_hot[0]["node"] if trad_hot else None
        trad_hot_people = trad_hot[0]["instant_people"] if trad_hot else 0.0
        trad_hot_density = trad_hot[0]["instant_density"] if trad_hot else 0.0

        imp_hot_node = imp_hot[0]["node"] if imp_hot else None
        imp_hot_people = imp_hot[0]["instant_people"] if imp_hot else 0.0
        imp_hot_density = imp_hot[0]["instant_density"] if imp_hot else 0.0

        for src in source_nodes:
            line = src.split("_")[1] if "_" in src else src

            trad_path = get_best_path_to_exit(G_trad, src, "Traditional", shortest_dists)
            imp_path = get_best_path_to_exit(G_imp, src, "Improved", shortest_dists)

            trad_next = trad_path[1] if trad_path and len(trad_path) > 1 else None
            imp_next = imp_path[1] if imp_path and len(imp_path) > 1 else None

            trad_changed = trad_next != prev_trad[src]
            imp_changed = imp_next != prev_imp[src]
            route_diverged = trad_next != imp_next

            if time == 0:
                event_type = "initial"
            else:
                flags = []
                if trad_changed:
                    flags.append("trad_change")
                if imp_changed:
                    flags.append("imp_change")
                if route_diverged:
                    flags.append("diverged")
                if not flags:
                    prev_trad[src] = trad_next
                    prev_imp[src] = imp_next
                    continue
                event_type = "+".join(flags)

            trad_next_people = G_trad.nodes[trad_next].get("people", 0.0) if trad_next in G_trad.nodes else 0.0
            imp_next_people = G_imp.nodes[imp_next].get("people", 0.0) if imp_next in G_imp.nodes else 0.0

            trad_next_density = trad_next_people / max(G_trad.nodes[trad_next].get("area", 1.0), 0.001) if trad_next in G_trad.nodes else 0.0
            imp_next_density = imp_next_people / max(G_imp.nodes[imp_next].get("area", 1.0), 0.001) if imp_next in G_imp.nodes else 0.0

            trad_len = sum(G_trad[trad_path[i]][trad_path[i + 1]]["length"] for i in range(len(trad_path) - 1)) if trad_path else None
            imp_len = sum(G_imp[imp_path[i]][imp_path[i + 1]]["length"] for i in range(len(imp_path) - 1)) if imp_path else None

            reason = "same-route"
            if route_diverged and trad_next and imp_next:
                if imp_next_density < trad_next_density:
                    reason = "improved_detour_lower_density"
                elif imp_next_density < trad_hot_density:
                    reason = "improved_avoids_traditional_bottleneck"
                else:
                    reason = "improved_reroute"
            elif trad_changed and not imp_changed:
                reason = "traditional_changed_only"
            elif imp_changed and not trad_changed:
                reason = "improved_changed_only"

            rows.append({
                "time": time,
                "line": line,
                "source": src,
                "event_type": event_type,
                "traditional_prev_next": prev_trad[src],
                "traditional_curr_next": trad_next,
                "improved_prev_next": prev_imp[src],
                "improved_curr_next": imp_next,
                "route_diverged": route_diverged,
                "traditional_path": format_path(trad_path),
                "improved_path": format_path(imp_path),
                "first_divergence": first_divergence(trad_path, imp_path),
                "trad_path_length": trad_len,
                "imp_path_length": imp_len,
                "trad_next_people": trad_next_people,
                "imp_next_people": imp_next_people,
                "trad_next_density": trad_next_density,
                "imp_next_density": imp_next_density,
                "trad_bottleneck_node": trad_hot_node,
                "trad_bottleneck_people": trad_hot_people,
                "trad_bottleneck_density": trad_hot_density,
                "imp_bottleneck_node": imp_hot_node,
                "imp_bottleneck_people": imp_hot_people,
                "imp_bottleneck_density": imp_hot_density,
                "reason": reason
            })

            if verbose and event_type != "initial":
                print(
                    f"[T={int(time)}s] {src} | Trad={trad_next or 'None'} | Imp={imp_next or 'None'} | "
                    f"分叉={route_diverged} | 原传统瓶颈={trad_hot_node or 'None'} | 原改进瓶颈={imp_hot_node or 'None'}"
                )

            prev_trad[src] = trad_next
            prev_imp[src] = imp_next

        advance_simulation_step(G_trad, "Traditional", shortest_dists)
        advance_simulation_step(G_imp, "Improved", shortest_dists)
        def still_has_people(G):
            return any(
                G.nodes[n].get("people", 0) > 0.1 and G.nodes[n].get("type") != "exit"
                for n in G.nodes()
            )

        if not still_has_people(G_trad) and not still_has_people(G_imp):
            break

        time += DELTA_T

    route_log_df = pd.DataFrame(rows)
    route_log_df.to_csv(filename, index=False, encoding="utf-8-sig")
    return route_log_df, G_trad, G_imp, shortest_dists


def summarize_bottlenecks_from_events(route_df, method_prefix, filename):
    """把事件日志汇总成瓶颈统计，不再依赖单一时刻快照。"""
    if method_prefix == "trad":
        node_col = "trad_bottleneck_node"
        people_col = "trad_bottleneck_people"
        density_col = "trad_bottleneck_density"
    else:
        node_col = "imp_bottleneck_node"
        people_col = "imp_bottleneck_people"
        density_col = "imp_bottleneck_density"

    df = route_df[route_df["route_diverged"]].copy()
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

    df = route_log_df[route_log_df["route_diverged"] & (route_log_df["event_type"] != "initial")].copy()
    if df.empty:
        return

    df["time_bin"] = (df["time"] // bin_size) * bin_size
    timeline = df.groupby("time_bin").size().reset_index(name="divergence_count")

    plt.figure(figsize=(10, 5))
    plt.plot(timeline["time_bin"], timeline["divergence_count"], "b-o", linewidth=2)
    plt.xlabel(f"时间窗 (s, {bin_size}s 聚合)")
    plt.ylabel("发生分叉的源点数")
    plt.title("改进换路分叉时间线", fontweight="bold")
    plt.grid(True, linestyle=":", alpha=0.7)
    plt.savefig(filename, dpi=300, bbox_inches="tight")
    plt.close()



def plot_route_highlight(G_base, source, trad_path, imp_path, filename, total_people=None, obs_window=None):
    plt.figure(figsize=(16, 10))
    pos = nx.get_node_attributes(G_base, "pos")

    nx.draw_networkx_edges(G_base, pos, edge_color="#CFCFCF", width=1.0, alpha=0.35, arrows=True)
    nx.draw_networkx_nodes(G_base, pos, node_color="#E6E6E6", node_size=400, edgecolors="black", linewidths=0.6)

    if trad_path and len(trad_path) > 1:
        trad_edges = list(zip(trad_path, trad_path[1:]))
        nx.draw_networkx_edges(G_base, pos, edgelist=trad_edges, edge_color="red", width=3.0, style="dashed", arrows=True)

    if imp_path and len(imp_path) > 1:
        imp_edges = list(zip(imp_path, imp_path[1:]))
        nx.draw_networkx_edges(G_base, pos, edgelist=imp_edges, edge_color="blue", width=3.5, style="solid", arrows=True)

    labels = {}
    for n in G_base.nodes():
        if n == source or G_base.nodes[n].get("type") in {"exit", "gate"}:
            labels[n] = n.replace("Platform_", "").replace("Gate_", "").replace("Exit_", "")

    nx.draw_networkx_labels(G_base, pos, labels=labels, font_size=8, font_weight="bold")

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
            mpatches.Patch(color="blue", label="Improved: blue solid")
        ],
        loc="upper right"
    )
    plt.gca().set_aspect('equal', adjustable='datalim')
    plt.axis("off")
    plt.savefig(filename, dpi=300, bbox_inches="tight")
    plt.close()


def execute_moves(G, moves, evacuated_by_line=None, exit_usage_dict=None):
    """带基因的多色流体转移引擎 (新增)"""
    evac_total = 0.0
    for u, v, amount in moves:
        sum_u = G.nodes[u].get("people", 0)
        if sum_u <= 0:
            continue

        # 按照起点节点的“线路成分比例”把流动的人切片
        for line_id, ppl in G.nodes[u].get("people_dict", {}).items():
            if ppl <= 0:
                continue
            flow = amount * (ppl / sum_u)

            # 扣除起点，增加终点
            G.nodes[u]["people_dict"][line_id] = max(G.nodes[u]["people_dict"][line_id] - flow, 0.0)
            G.nodes[v]["people_dict"][line_id] += flow

            if G.nodes[v].get("type") == "exit":
                if evacuated_by_line is not None:
                    evacuated_by_line[line_id] += flow
                if exit_usage_dict is not None and v in exit_usage_dict:
                    exit_usage_dict[v][line_id] += flow

        G.nodes[u]["people"] = max(G.nodes[u]["people"] - amount, 0.0)
        G.nodes[v]["people"] += amount

        if G.nodes[v].get("type") == "exit":
            evac_total += amount

    return evac_total


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


def run_robustness_experiment(G_base, pop_per_line, method="Improved", runs=10, seed=42):
    active_lines = get_real_active_lines(G_base)
    print(f"\n🔬 启动 {method} 算法鲁棒性测试 (全站总计:{pop_per_line * active_lines}人, 迭代:{runs}次)...")

    results_time, results_queue, results_exposure, results_speed = [], [], [], []

    for i in range(runs):
        rng = random.Random(None if seed is None else seed + i)
        G_noisy = copy.deepcopy(G_base)

        (G_noisy, rng, 0.95, 1.05)

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
    # 🌟 恢复大画幅正方形，让系统按物理坐标自动拉伸，拒绝“面条图”！
    plt.figure(figsize=(22, 22))
    pos = nx.get_node_attributes(G, 'pos')

    color_map = []
    node_sizes = []
    for n in G.nodes():
        t = G.nodes[n].get('type', '')
        if 'platform' in t:
            color_map.append('#9370DB');
            node_sizes.append(800)  # 恢复大气尺寸
        elif 'exit' in t:
            color_map.append('#32CD32');
            node_sizes.append(600)
        elif 'gate' in t:
            color_map.append('#FFA500');
            node_sizes.append(350)
        elif 'stair' in t or 'escalator' in t:
            color_map.append('#1E90FF');
            node_sizes.append(250)
        elif 'virtual' in t:
            color_map.append('#FF0000');
            node_sizes.append(150)
        else:
            color_map.append('lightgray');
            node_sizes.append(100)

    # 边加粗，看得更清楚
    nx.draw_networkx_edges(G, pos, edge_color='#A9A9A9', arrows=True, width=1.5, arrowsize=10, alpha=0.6)
    nx.draw_networkx_nodes(G, pos, node_color=color_map, node_size=node_sizes, edgecolors='black', linewidths=0.8)

    # 恢复清晰的字体大小
    labels = {n: n.split('_')[-1] for n in G.nodes() if G.nodes[n].get('type') in ['platform', 'exit', 'gate']}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=10, font_weight='bold')

    plt.title('龙阳路枢纽初始物理拓扑 (高精还原比例)', fontsize=26, fontweight='bold', pad=20)
    plt.gca().set_aspect('equal', adjustable='datalim')  # 🌟 这句是灵魂：保证坐标绝不变形
    plt.axis('off')

    plt.savefig("01_initial_topology.png", dpi=300, bbox_inches='tight')
    plt.close()


def plot_comparative_snapshots(G_base, pop_dict, time_points=[20, 80, 150]):
    print(f"\n🎬 正在生成双算法热力演化快照 (T={time_points}s)...")
    snap_trad = generate_snapshots_for_method(G_base, pop_dict, "Traditional", time_points)
    snap_imp = generate_snapshots_for_method(G_base, pop_dict, "Improved", time_points)

    pos = nx.get_node_attributes(G_base, 'pos')
    total_p = sum(sum(d.values()) for d in pop_dict.values())

    for tp in time_points:
        # 🌟 改为超大宽屏，容纳左右两张对比图，拒绝挤压
        fig, axes = plt.subplots(1, 2, figsize=(32, 18))
        fig.suptitle(f'疏散时空拥挤演化对比 (T = {tp}s, 总规模: {total_p}人)', fontsize=30, fontweight='bold', y=0.98)

        methods_data = [("Traditional (传统算法 - 易局部死锁)", snap_trad[tp]),
                        ("Improved (改进算法)", snap_imp[tp])]

        for idx, (title, node_people) in enumerate(methods_data):
            ax = axes[idx]
            ax.set_title(title, fontsize=24, pad=15)
            nx.draw_networkx_edges(G_base, pos, ax=ax, edge_color='#B0B0B0', width=1.5, alpha=0.4, arrowsize=8)

            node_colors, node_sizes, labels = [], [], {}
            for n in G_base.nodes():
                ppl = max(node_people[n], 0.0)
                cap = max(G_base.nodes[n].get('capacity', 1.0), 0.001)
                node_colors.append(ppl / cap)

                # 🌟 优化热力图圆圈：基础变大，随人数增长更平滑
                base_size = 200 if G_base.nodes[n].get('type') == 'platform' else 80
                size = base_size + math.sqrt(ppl) * 20
                node_sizes.append(size)

                # 阈值调高一点，图面更清爽
                if ppl > 20:
                    labels[n] = f"{int(ppl)}"


            nodes = nx.draw_networkx_nodes(G_base, pos, ax=ax, node_color=node_colors, cmap=plt.cm.Reds, vmin=0,
                                           vmax=20, node_size=node_sizes, edgecolors='black', linewidths=0.5)
            nx.draw_networkx_labels(G_base, pos, labels=labels, ax=ax, font_size=9, font_weight='bold')
            ax.set_aspect('equal', adjustable='datalim')  # 🌟 同步保持真实坐标比例
            ax.axis('off')

        cbar = fig.colorbar(nodes, ax=axes.ravel().tolist(), shrink=0.5, aspect=30, pad=0.03)
        cbar.set_label('节点拥挤度系数 (人数 / 每秒通行容量)', fontsize=16)
        plt.savefig(f"04_snapshot_comparison_T{tp}s.png", dpi=300, bbox_inches='tight')
        plt.close()


def plot_charts(metrics_trad, metrics_imp, total_p):
    """【专业高颜值版】核心指标对比"""
    labels = ['传统算法 (Traditional)', '改进算法 (Improved)']
    colors = ['#E63946', '#457B9D']  # 经典的学术红蓝配色

    fig, axes = plt.subplots(2, 2, figsize=(10, 9))
    fig.suptitle(f'枢纽疏散指标评估 (测试客流: {total_p}人)', fontsize=20, fontweight='bold', y=0.96)

    # 定义我们要画的4个图的数据和专业标题
    metrics_list = [
        ('time', '疏散完成时间 ', axes[0, 0], 1),
        ('queueing_time', '总滞留排队时间 ', axes[0, 1], 1),
        ('congestion_exposure_time', '重度拥挤暴露时间 ', axes[1, 0], 1000),
        ('avg_speed', '全局平均移动速度 ', axes[1, 1], 1)
    ]

    for key, title, ax, div in metrics_list:
        vals = [metrics_trad[key] / div, metrics_imp[key] / div]
        # 添加黑色描边，让柱体更立体
        bars = ax.bar(labels, vals, color=colors, width=0.4, edgecolor='black', linewidth=1.2)
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax.grid(axis='y', linestyle='--', alpha=0.6)
        ax.set_axisbelow(True)  # 让网格线在柱子后面

        # 🌟 灵魂注入：直接在柱子上打上精准数值标签！
        for bar in bars:
            yval = bar.get_height()
            label_text = f'{yval:.2f}' if div == 1000 or key == 'avg_speed' else f'{int(yval)}'
            ax.text(bar.get_x() + bar.get_width() / 2, yval + (yval * 0.01), label_text, ha='center', va='bottom',
                    fontsize=12, fontweight='bold')

    plt.savefig("02_Macro_Metrics_Comparison.png", dpi=300, bbox_inches="tight")
    plt.close()

    # 2. 改善率汇总 (柱状图)
    t_imp = ((metrics_trad['time'] - metrics_imp['time']) / metrics_trad['time'] * 100) if metrics_trad[
                                                                                               'time'] > 0 else 0
    q_imp = ((metrics_trad['queueing_time'] - metrics_imp['queueing_time']) / metrics_trad['queueing_time'] * 100) if \
    metrics_trad['queueing_time'] > 0 else 0
    e_imp = ((metrics_trad['congestion_exposure_time'] - metrics_imp['congestion_exposure_time']) / metrics_trad[
        'congestion_exposure_time'] * 100) if metrics_trad['congestion_exposure_time'] > 0 else 0

    plt.figure(figsize=(9, 6))
    bars = plt.bar(['时间改善率', '排队改善率', '拥挤暴露改善率'], [t_imp, q_imp, e_imp], color='#4A90E2',
                   edgecolor='black', width=0.4)
    plt.ylabel("改善提升幅度 (%)", fontsize=12)
    plt.title(f"改进算法性能提升率评估 ({total_p}人)", fontweight="bold", fontsize=16)
    plt.grid(axis='y', linestyle='--', alpha=0.6);
    plt.gca().set_axisbelow(True)
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, yval + 1, f"{yval:.1f}%", ha='center', fontweight='bold',
                 fontsize=12, color='black')
    plt.savefig("03_Improvement_Rates.png", dpi=300, bbox_inches="tight")
    plt.close()


def plot_line_specific_analysis(metrics_trad, metrics_imp, pop_dict):
    """【专业升级版】绘制各线路专属指标（疏散时间 + 重度拥挤暴露）"""
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
    bars1_imp = ax1.bar(x + width / 2, t_imp, width, label='Improved (改进)', color=colors[1], edgecolor='black',
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

    # === 子图 2：各线路重度拥挤暴露时间 (你要的新图！) ===
    ax2 = axes[1]
    e_trad = [metrics_trad["congestion_exposure_by_line"].get(l, 0) / 1000.0 for l in lines]
    e_imp = [metrics_imp["congestion_exposure_by_line"].get(l, 0) / 1000.0 for l in lines]

    bars2_trad = ax2.bar(x - width / 2, e_trad, width, label='Traditional (传统)', color=colors[0], edgecolor='black',
                         linewidth=1)
    bars2_imp = ax2.bar(x + width / 2, e_imp, width, label='Improved (改进)', color=colors[1], edgecolor='black',
                        linewidth=1)

    ax2.set_xticks(x);
    ax2.set_xticklabels(lines, fontsize=12)
    ax2.set_ylabel('拥挤暴露时间 / Congestion Exposure (10$^3$ pax·s)', fontsize=12)
    ax2.set_title('各单线路重度拥挤暴露对比', fontweight='bold', fontsize=14)
    ax2.legend();
    ax2.grid(axis='y', linestyle='--', alpha=0.6);
    ax2.set_axisbelow(True)

    for bars in [bars2_trad, bars2_imp]:
        for bar in bars:
            yval = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width() / 2, yval + (max(e_trad) * 0.02), f'{yval:.1f}', ha='center',
                     va='bottom', fontsize=11, fontweight='bold')

    plt.savefig("05_Line_Core_Metrics.png", dpi=300, bbox_inches='tight')
    plt.close()

    # ==== 保留：各线路逃生出口去向 (堆叠柱状图) ====
    for title, met in [("Traditional", metrics_trad), ("Improved", metrics_imp)]:
        exits_dict = met["exit_usage_by_line"]
        active_exits = sorted([e for e, lines_ppl in exits_dict.items() if sum(lines_ppl.values()) > 1.0])
        if not active_exits: continue

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
        ax.set_title(f'人群逃生出口分布溯源 ({title} 算法)', fontweight='bold', fontsize=14)
        ax.legend(title="人群来源");
        ax.grid(axis='y', linestyle='--', alpha=0.5);
        ax.set_axisbelow(True)
        plt.savefig(f"06_Exit_Destinations_{title}.png", dpi=300, bbox_inches='tight')
        plt.close()


def run_simulation_for_metrics(G_base, pop_dict, method="Improved", apply_noise=False, rng=None):
    G = copy.deepcopy(G_base)
    init_people(G, pop_dict, apply_noise, rng)

    time, evacuated_count = 0, 0
    total_flow_moves, sum_speed_weighted = 0.0, 0.0
    shortest_dists = dict(nx.all_pairs_dijkstra_path_length(G, weight="length"))

    target_by_line = {line: sum(d.values()) for line, d in pop_dict.items()}
    evacuated_by_line = {line: 0.0 for line in ALL_LINE_IDS}

    monitor_node = "Gate_L2_N_West" if "Gate_L2_N_West" in G.nodes else next(
        (n for n in G.nodes if "gate" in n.lower()), None
    )

    metrics = {
        "time": 0,
        "queueing_time": 0.0,
        "congestion_exposure_time": 0.0,
        "avg_speed": 0.0,
        "clearance_times_by_line": {line: None for line, pop in target_by_line.items() if pop > 0},
        "queueing_time_by_line": {line: 0.0 for line in ALL_LINE_IDS},
        "congestion_exposure_by_line": {line: 0.0 for line in ALL_LINE_IDS},
        "exit_usage_by_line": {
            ext: {line: 0.0 for line in ALL_LINE_IDS}
            for ext in NODES_DATA.get("ALL_EXITS", {}).keys()
        },
        "exit_usage": {ext: 0 for ext in NODES_DATA.get("ALL_EXITS", {}).keys()},
        "time_series_queue": {monitor_node: []} if monitor_node else {},
        "node_stats": {
            n: {
                "peak_people": 0.0,
                "peak_density": 0.0,
                "queue_seconds": 0.0,
                "congestion_seconds": 0.0
            }
            for n in G.nodes()
        },
        "time_series_by_line": {
            line: {"times": [], "speeds": [], "queues": []}
            for line in ALL_LINE_IDS
        }
    }

    while time < 6000:
        all_lines_cleared = True
        for line_id, target in target_by_line.items():
            if target > 0 and evacuated_by_line[line_id] < target * 0.99:
                all_lines_cleared = False
                break
        if all_lines_cleared:
            break

        active_nodes = [
            n for n in G.nodes()
            if G.nodes[n].get("people", 0) > 0.1 and G.nodes[n].get("type") != "exit"
        ]

        current_heavy_congestion = 0.0
        current_queues_by_line = {line: 0.0 for line in ALL_LINE_IDS}
        current_moving_ppl_by_line = {line: 0.0 for line in ALL_LINE_IDS}
        current_speed_sum_by_line = {line: 0.0 for line in ALL_LINE_IDS}

        # 先统计这一时刻节点状态
        for n in active_nodes:
            ppl = G.nodes[n]["people"]
            node_type = G.nodes[n].get("type", "")
            density = ppl / max(G.nodes[n].get("area", 1.0), 0.001)

            metrics["node_stats"][n]["peak_people"] = max(metrics["node_stats"][n]["peak_people"], ppl)
            metrics["node_stats"][n]["peak_density"] = max(metrics["node_stats"][n]["peak_density"], density)

            if "gate" in node_type or "virtual" in node_type:
                metrics["queueing_time"] += ppl * DELTA_T
                metrics["node_stats"][n]["queue_seconds"] += ppl * DELTA_T
                for line_id, count in G.nodes[n].get("people_dict", {}).items():
                    metrics["queueing_time_by_line"][line_id] += count * DELTA_T
                    current_queues_by_line[line_id] += count

            if density > 3.0:
                current_heavy_congestion += ppl * DELTA_T
                metrics["node_stats"][n]["congestion_seconds"] += ppl * DELTA_T
                for line_id, count in G.nodes[n].get("people_dict", {}).items():
                    metrics["congestion_exposure_by_line"][line_id] += count * DELTA_T

        # 关键改动：这里不再只走单一 next node，而是允许并行分流
        moves = get_step_moves(G, method, shortest_dists)

        metrics["congestion_exposure_time"] += current_heavy_congestion
        if monitor_node and monitor_node in G.nodes:
            metrics["time_series_queue"][monitor_node].append(G.nodes[monitor_node].get("people", 0))

        for u, v, amount in moves:
            path_density = G.nodes[v]["people"] / max(G.nodes[v].get("area", 1.0), 0.001)
            spd = fruin_speed(path_density)
            total_flow_moves += amount
            sum_speed_weighted += amount * spd

            sum_u = G.nodes[u].get("people", 0)
            if sum_u > 0:
                for line_id, ppl_in_node in G.nodes[u].get("people_dict", {}).items():
                    if ppl_in_node > 0:
                        line_flow = amount * (ppl_in_node / sum_u)
                        current_moving_ppl_by_line[line_id] += line_flow
                        current_speed_sum_by_line[line_id] += line_flow * spd

            if G.nodes[v].get("type") == "exit":
                metrics["exit_usage"][v] += amount

        amount_evacuated_this_step = execute_moves(G, moves, evacuated_by_line, metrics["exit_usage_by_line"])
        evacuated_count += amount_evacuated_this_step

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

        time += DELTA_T

        for line_id, target in target_by_line.items():
            if target > 0 and metrics["clearance_times_by_line"].get(line_id) is None:
                if evacuated_by_line[line_id] >= target * 0.99:
                    metrics["clearance_times_by_line"][line_id] = time

    metrics["time"] = time
    metrics["avg_speed"] = sum_speed_weighted / total_flow_moves if total_flow_moves > 0 else 0.0
    return metrics



def plot_detailed_dynamics_by_line(metrics_trad, metrics_imp, pop_dict):
    """【硬核细节分析】绘制各条线路的瞬时排队折线图、瞬时速度折线图"""
    lines = [l for l, d in pop_dict.items() if sum(d.values()) > 0]
    if not lines: return

    # ==== 1. 各线路瞬时排队人数折线图 (看哪里堵得久) ====
    fig, axes = plt.subplots(math.ceil(len(lines) / 2), 2, figsize=(16, 5 * math.ceil(len(lines) / 2)))
    fig.suptitle('各线路瞬时排队/滞留人数动态演化对比', fontsize=20, fontweight='bold', y=0.95)
    axes = axes.flatten() if len(lines) > 1 else [axes]

    for idx, line in enumerate(lines):
        ax = axes[idx]
        times_trad = metrics_trad["time_series_by_line"][line]["times"]
        queues_trad = metrics_trad["time_series_by_line"][line]["queues"]
        times_imp = metrics_imp["time_series_by_line"][line]["times"]
        queues_imp = metrics_imp["time_series_by_line"][line]["queues"]

        ax.plot(times_trad, queues_trad, 'r-', linewidth=2, label="Traditional (传统)", alpha=0.8)
        ax.plot(times_imp, queues_imp, 'g-', linewidth=2.5, label="Improved (改进)")

        ax.set_title(f'{line} 线路排队演化', fontsize=14, fontweight='bold')
        ax.set_xlabel('时间 (s)');
        ax.set_ylabel('正在排队滞留人数 (人)')
        ax.grid(True, linestyle=":", alpha=0.7);
        ax.legend()

    # 隐藏多余的子图
    for idx in range(len(lines), len(axes)): fig.delaxes(axes[idx])
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    plt.savefig("03_Line_Queue_Dynamics.png", dpi=300, bbox_inches='tight')
    plt.close()

    # ==== 2. 各线路瞬时平均速度折线图 (看哪里走不动) ====
    fig, axes = plt.subplots(math.ceil(len(lines) / 2), 2, figsize=(16, 5 * math.ceil(len(lines) / 2)))
    fig.suptitle('各线路人群平均移动速度动态演化对比', fontsize=20, fontweight='bold', y=0.95)
    axes = axes.flatten() if len(lines) > 1 else [axes]

    for idx, line in enumerate(lines):
        ax = axes[idx]

        times_trad = np.array(metrics_trad["time_series_by_line"][line]["times"])
        speeds_trad = np.array(metrics_trad["time_series_by_line"][line]["speeds"])
        times_imp = np.array(metrics_imp["time_series_by_line"][line]["times"])
        speeds_imp = np.array(metrics_imp["time_series_by_line"][line]["speeds"])

        # 获取该线路真实的清空时间，疏散完之后的时间点标记为 NaN (不画线，避免跌到0)
        clear_time_trad = metrics_trad["clearance_times_by_line"].get(line) or float('inf')
        clear_time_imp = metrics_imp["clearance_times_by_line"].get(line) or float('inf')

        speeds_trad[times_trad > clear_time_trad] = np.nan
        speeds_imp[times_imp > clear_time_imp] = np.nan

        # 忽略微小的0值断层，并把平滑窗口扩大到 20 秒，彻底消除锯齿！
        s_trad_smooth = pd.Series(speeds_trad).replace(0.0, np.nan).interpolate().rolling(window=20,
                                                                                          min_periods=1).mean()
        s_imp_smooth = pd.Series(speeds_imp).replace(0.0, np.nan).interpolate().rolling(window=20, min_periods=1).mean()

        ax.plot(times_trad, s_trad_smooth, 'r-', linewidth=2.5, label="Traditional (传统)", alpha=0.8)
        ax.plot(times_imp, s_imp_smooth, 'b-', linewidth=3.0, label="Improved (改进分流)")

        ax.set_title(f'{line} 线路平均速度演化', fontsize=14, fontweight='bold')
        ax.set_xlabel('时间 (s)');
        ax.set_ylabel('移动速度 (m/s)')
        ax.set_ylim(0, 1.5)  # 正常人步速上限
        ax.grid(True, linestyle=":", alpha=0.7);
        ax.legend()

    for idx in range(len(lines), len(axes)): fig.delaxes(axes[idx])
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    plt.savefig("04_Line_Speed_Dynamics.png", dpi=300, bbox_inches='tight')
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


if __name__ == "__main__":
    G = build_graph()
    plot_initial_topology(G)
    mode = get_evacuation_mode()
    # 🌟 按照你的原话：站厅、站台、换乘人数完全独立配置！车厢不变！
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
        elif mode == 4:
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

    # 只跑这一遍，拿最精准的数据！
    metrics_trad = run_simulation_for_metrics(G, current_pop_dict, method="Traditional")
    metrics_imp = run_simulation_for_metrics(G, current_pop_dict, method="Improved")

    print(f"[Traditional] 全站时间 {metrics_trad['time']:.1f}s | 总排队 {metrics_trad['queueing_time']:.1f} 人·秒")
    print(f"[Improved]    全站时间 {metrics_imp['time']:.1f}s | 总排队 {metrics_imp['queueing_time']:.1f} 人·秒")
    print("\n📊 正在生成各线路硬核微观细节对比图 (速度起伏、排队动态)...")
    plot_detailed_dynamics_by_line(metrics_trad, metrics_imp, current_pop_dict)
    print("\n📊 正在生成宏观指标深度对比图 (Bar柱状图与消散折线图)...")
    plot_charts(metrics_trad, metrics_imp, total_p)

    print("\n📊 正在生成各线路专属清空分析图表...")
    plot_line_specific_analysis(metrics_trad, metrics_imp, current_pop_dict)

    print("\n🔍 正在生成抗拥挤的高清热力快照 (请稍候)...")
    plot_comparative_snapshots(G, pop_dict=current_pop_dict, time_points=[30, 90, 200])

    print("\n📝 正在生成事件日志与瓶颈追踪CSV...")
    source_nodes = [n for n, d in G.nodes(data=True) if d.get("type") in {"stair", "escalator"}]
    route_df, _, _, _ = collect_route_event_log(
        G_base=G, pop_dict=current_pop_dict, source_nodes=source_nodes, target_time=2000,
        filename="10_route_event_log.csv", verbose=False
    )
    summarize_route_changes_by_line(route_df, "11_route_change_summary.csv")
    summarize_bottlenecks_from_events(route_df, "trad", "12_bottlenecks_traditional.csv")
    summarize_bottlenecks_from_events(route_df, "imp", "13_bottlenecks_improved.csv")
    plot_divergence_timeline(route_df, "14_divergence_timeline.png", bin_size=10)

    print("\n✅ 所有的深度分析图表和日志已完美生成！")
