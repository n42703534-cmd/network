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
# 3. 动态建图与智能放人引擎
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
    # 🌟 新增：动态构建“列车车厢节点”与“车门瓶颈连线”
    # =================================================================
    TRAIN_PHYSICS = {
        "L2": {"cars": 8, "doors_per_car": 5, "door_w": 1.4, "area_per_car": 70.62},
        "L7": {"cars": 6, "doors_per_car": 5, "door_w": 1.4, "area_per_car": 70.62},
        "L16": {"cars": 6, "doors_per_car": 3, "door_w": 1.4, "area_per_car": 70.62},
        "L18": {"cars": 6, "doors_per_car": 5, "door_w": 1.4, "area_per_car": 66},
        "Maglev": {"cars": 5, "doors_per_car": 4, "door_w": 1.4, "area_per_car": 89}
    }

    for line_id, physics in TRAIN_PHYSICS.items():
        p_node = f"Platform_{line_id}"
        if p_node not in G.nodes:
            continue

        total_door_width = physics["cars"] * physics["doors_per_car"] * physics["door_w"]
        door_capacity = calculate_gb_capacity_per_second("passageway", total_door_width)
        train_area = physics["cars"] * physics["area_per_car"]

        t1_node = f"Train_{line_id}_1"
        G.add_node(t1_node, type="train", capacity=9999, area=train_area, people=0, pos=G.nodes[p_node].get("pos", (0, 0)))
        G.add_edge(t1_node, p_node, length=1.0, capacity=door_capacity, edge_type="train_door")

        t2_node = f"Train_{line_id}_2"
        G.add_node(t2_node, type="train", capacity=9999, area=train_area, people=0, pos=G.nodes[p_node].get("pos", (0, 0)))
        G.add_edge(t2_node, p_node, length=1.0, capacity=door_capacity, edge_type="train_door")
    for n in G.nodes():
        G.nodes[n]["people_dict"] = {l: 0.0 for l in ALL_LINE_IDS}
    return G


def init_people(G, pop_dict, apply_noise=False, rng=None):
    # 重置清空
    for n in G.nodes():
        G.nodes[n]["people"] = 0.0
        G.nodes[n]["people_dict"] = {l: 0.0 for l in ALL_LINE_IDS}

    for line_id, spec in PLATFORM_VERTICAL_SPECS.items():
        p_node = spec["platform_node"]
        if p_node in G.nodes and line_id in pop_dict:
            line_data = pop_dict[line_id]

            # 列车放入 (同时打上该线路的基因标签)
            if f"Train_{line_id}_1" in G.nodes:
                G.nodes[f"Train_{line_id}_1"]["people"] = line_data.get("train_1", 0)
                G.nodes[f"Train_{line_id}_1"]["people_dict"][line_id] = line_data.get("train_1", 0)
            if f"Train_{line_id}_2" in G.nodes:
                G.nodes[f"Train_{line_id}_2"]["people"] = line_data.get("train_2", 0)
                G.nodes[f"Train_{line_id}_2"]["people_dict"][line_id] = line_data.get("train_2", 0)

            # 站台放入
            G.nodes[p_node]["people"] = line_data.get("platform_waiting", 0)
            G.nodes[p_node]["people_dict"][line_id] = line_data.get("platform_waiting", 0)

            # 站厅及换乘散布
            hall_people = line_data.get("hall_transfer", 0)
            gate_group_name = spec.get("gate_group", f"{line_id}_GATES")
            valid_targets = [n for n in NODES_DATA.get(gate_group_name, {}) if n in G.nodes]

            if "TRANSFERS" in NODES_DATA:
                for t_node in NODES_DATA["TRANSFERS"].keys():
                    if line_id in t_node and t_node in G.nodes:
                        valid_targets.append(t_node)

            if valid_targets and hall_people > 0:
                base_weights = [G.nodes[n].get("capacity", 1.0) for n in valid_targets]
                if apply_noise and rng is not None: base_weights = [w * rng.uniform(0.9, 1.1) for w in base_weights]
                total_w = sum(base_weights)
                if total_w > 0:
                    for n, w in zip(valid_targets, base_weights):
                        assigned_ppl = hall_people * (w / total_w)
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
        moves = []
        active_nodes = [n for n in G.nodes() if G.nodes[n].get("people", 0) > 0.1 and G.nodes[n].get("type") != "exit"]

        for u in active_nodes:
            v = get_best_next_node(G, u, method, shortest_dists)
            if v:
                flow = min(G.nodes[u]["people"], G[u][v]["capacity"] * DELTA_T)
                if flow > 0:
                    moves.append((u, v, flow))

        for u, v, amount in moves:
            G.nodes[u]["people"] -= amount
            G.nodes[v]["people"] += amount

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
    rows.sort(key=lambda x: x["instant_people"], reverse=True)
    return rows[:top_k]

def advance_simulation_step(G, method, shortest_dists):
    """推进单个仿真步，供事件日志复用。"""
    moves = []
    active_nodes = [
        n for n in G.nodes()
        if G.nodes[n].get("people", 0) > 0.1 and G.nodes[n].get("type") != "exit"
    ]

    for u in active_nodes:
        v = get_best_next_node(G, u, method, shortest_dists)
        if v:
            flow = min(G.nodes[u]["people"], G[u][v]["capacity"] * DELTA_T)
            if flow > 0:
                moves.append((u, v, flow))

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
    plt.title("智能换路分叉时间线", fontweight="bold")
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
        if sum_u <= 0: continue

        # 按照起点节点的“线路成分比例”把流动的人切片
        for line_id, ppl in G.nodes[u].get("people_dict", {}).items():
            if ppl <= 0: continue
            flow = amount * (ppl / sum_u)

            # 扣除起点，增加终点
            G.nodes[u]["people_dict"][line_id] -= flow
            G.nodes[v]["people_dict"][line_id] += flow

            if G.nodes[v].get("type") == "exit":
                if evacuated_by_line is not None: evacuated_by_line[line_id] += flow
                if exit_usage_dict is not None and v in exit_usage_dict: exit_usage_dict[v][line_id] += flow

        G.nodes[u]["people"] -= amount
        G.nodes[v]["people"] += amount
        if G.nodes[v].get("type") == "exit": evac_total += amount
    return evac_total


def run_simulation_for_metrics(G_base, pop_dict, method="Improved", apply_noise=False, rng=None):
    G = copy.deepcopy(G_base)
    init_people(G, pop_dict, apply_noise, rng)

    time, evacuated_count = 0, 0
    total_flow_moves, sum_speed_weighted = 0.0, 0.0
    shortest_dists = dict(nx.all_pairs_dijkstra_path_length(G, weight='length'))

    # 🌟 各线路独立跟踪核心参数
    target_by_line = {line: sum(d.values()) for line, d in pop_dict.items()}
    evacuated_by_line = {line: 0.0 for line in ALL_LINE_IDS}
    total_pop = sum(target_by_line.values())
    target_evacuated_total = total_pop * 0.99

    metrics = {
        "time": 0, "queueing_time": 0.0,
        "clearance_times_by_line": {line: None for line, pop in target_by_line.items() if pop > 0},
        "queueing_time_by_line": {line: 0.0 for line in ALL_LINE_IDS},
        "exit_usage_by_line": {ext: {line: 0.0 for line in ALL_LINE_IDS} for ext in
                               NODES_DATA.get("ALL_EXITS", {}).keys()}
    }

    while time < 6000:
        # 🌟 真正的刹车逻辑：检查是不是【每一条有人的线路】都已经自己跑完了 99%？
        all_lines_cleared = True
        for l, target in target_by_line.items():
            if target > 0 and evacuated_by_line[l] < target * 0.99:
                all_lines_cleared = False
                break

        # 只有当所有线路都跑完了，才允许停止仿真！
        if all_lines_cleared:
            break
        moves = []
        active_nodes = [n for n in G.nodes() if G.nodes[n].get("people", 0) > 0.1 and G.nodes[n].get("type") != "exit"]

        for n in active_nodes:
            ppl = G.nodes[n]["people"]
            node_type = G.nodes[n].get("type", "")
            if "gate" in node_type or "virtual" in node_type:
                metrics["queueing_time"] += ppl * DELTA_T
                for line_id, count in G.nodes[n].get("people_dict", {}).items():
                    metrics["queueing_time_by_line"][line_id] += count * DELTA_T

            v = get_best_next_node(G, n, method, shortest_dists)
            if v:
                flow = min(ppl, G[n][v]["capacity"] * DELTA_T)
                if flow > 0: moves.append((n, v, flow))

        amount_evacuated_this_step = execute_moves(G, moves, evacuated_by_line, metrics["exit_usage_by_line"])
        evacuated_count += amount_evacuated_this_step

        for u, v, amount in moves:
            path_density = G.nodes[v]["people"] / G.nodes[v].get("area", 1.0)
            total_flow_moves += amount
            sum_speed_weighted += amount * fruin_speed(path_density)
        time += DELTA_T

        for line_id, target in target_by_line.items():
            if target > 0 and metrics["clearance_times_by_line"].get(line_id) is None:
                if evacuated_by_line[line_id] >= target * 0.99:
                    metrics["clearance_times_by_line"][line_id] = time

    metrics["time"] = time
    return metrics


def generate_snapshots_for_method(G_base, pop_dict, method, time_points):
    G = G_base.copy()
    init_people(G, pop_dict, apply_noise=False)
    shortest_dists = dict(nx.all_pairs_dijkstra_path_length(G, weight='length'))

    time = 0
    max_time = max(time_points)
    snapshots = {}

    while time <= max_time:
        for tp in time_points:
            if abs(time - tp) < DELTA_T / 2:
                snapshots[tp] = {n: G.nodes[n].get('people', 0) for n in G.nodes()}

        moves = []
        active_nodes = [n for n in G.nodes() if G.nodes[n].get('people', 0) > 0.1 and G.nodes[n].get('type') != 'exit']
        for u in active_nodes:
            v = get_best_next_node(G, u, method, shortest_dists)
            if v:
                flow = min(G.nodes[u]['people'], G[u][v]['capacity'] * DELTA_T)
                if flow > 0: moves.append((u, v, flow))

        execute_moves(G, moves)
        time += DELTA_T
    return snapshots

def run_robustness_experiment(G_base, pop_per_line, method="Improved", runs=10, seed=42):
    active_lines = get_real_active_lines(G_base)
    print(f"\n🔬 启动 {method} 算法鲁棒性测试 (全站总计:{pop_per_line * active_lines}人, 迭代:{runs}次)...")

    results_time, results_queue, results_exposure, results_speed = [], [], [], []

    for i in range(runs):
        rng = random.Random(None if seed is None else seed + i)
        G_noisy = copy.deepcopy(G_base)

        apply_capacity_noise(G_noisy, rng, 0.95, 1.05)
        platform_ratio = rng.uniform(0.55, 0.65)

        metrics = run_simulation_for_metrics(G_noisy, pop_per_line, method=method, apply_noise=True, rng=rng,
                                             platform_ratio=platform_ratio)

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
                        ("Improved (智能分流算法)", snap_imp[tp])]

        for idx, (title, node_people) in enumerate(methods_data):
            ax = axes[idx]
            ax.set_title(title, fontsize=24, pad=15)
            nx.draw_networkx_edges(G_base, pos, ax=ax, edge_color='#B0B0B0', width=1.5, alpha=0.4, arrowsize=8)

            node_colors, node_sizes, labels = [], [], {}
            for n in G_base.nodes():
                ppl = node_people[n]
                cap = max(G_base.nodes[n].get('capacity', 1.0), 0.001)
                node_colors.append(ppl / cap)

                # 🌟 优化热力图圆圈：基础变大，随人数增长更平滑
                base_size = 200 if G_base.nodes[n].get('type') == 'platform' else 80
                size = base_size + math.sqrt(ppl) * 20
                node_sizes.append(size)

                # 阈值调高一点，图面更清爽
                if ppl > 20: labels[n] = f"{int(ppl)}"

            nodes = nx.draw_networkx_nodes(G_base, pos, ax=ax, node_color=node_colors, cmap=plt.cm.Reds, vmin=0,
                                           vmax=20, node_size=node_sizes, edgecolors='black', linewidths=0.5)
            nx.draw_networkx_labels(G_base, pos, labels=labels, ax=ax, font_size=9, font_weight='bold')
            ax.set_aspect('equal', adjustable='datalim')  # 🌟 同步保持真实坐标比例
            ax.axis('off')

        cbar = fig.colorbar(nodes, ax=axes.ravel().tolist(), shrink=0.5, aspect=30, pad=0.03)
        cbar.set_label('节点拥挤度系数 (人数 / 每秒通行容量)', fontsize=16)
        plt.savefig(f"04_snapshot_comparison_T{tp}s.png", dpi=300, bbox_inches='tight')
        plt.close()

def plot_charts(scenario_names, results):
    """【全数归还】你辛苦调好的排队、暴露、速度、改善率折线图！"""
    def s(method_key, metric_key): return [results[p][method_key][metric_key] for p in scenario_names]

    trad_time, imp_time = s("trad", "time"), s("imp", "time")
    trad_queue, imp_queue = s("trad", "queueing_time"), s("imp", "queueing_time")
    trad_exp, imp_exp = s("trad", "congestion_exposure_time"), s("imp", "congestion_exposure_time")
    trad_speed, imp_speed = s("trad", "avg_speed"), s("imp", "avg_speed")

    pd.DataFrame({
        "scenario": scenario_names, "trad_time": trad_time, "imp_time": imp_time,
        "trad_queue": trad_queue, "imp_queue": imp_queue,
        "trad_exposure_k": [x / 1000 for x in trad_exp], "imp_exposure_k": [x / 1000 for x in imp_exp],
        "trad_avg_speed": trad_speed, "imp_avg_speed": imp_speed,
        "time_reduction_pct": [((t - i) / t * 100) if t > 0 else 0.0 for t, i in zip(trad_time, imp_time)],
        "queue_reduction_pct": [((t - i) / t * 100) if t > 0 else 0.0 for t, i in zip(trad_queue, imp_queue)],
        "exposure_reduction_pct": [((t - i) / t * 100) if t > 0 else 0.0 for t, i in zip(trad_exp, imp_exp)],
    }).to_csv("00_summary_table.csv", index=False, encoding="utf-8-sig")

    plt.figure(figsize=(10, 6)); plt.plot(scenario_names, trad_time, "r--^", linewidth=2, label="Traditional"); plt.plot(scenario_names, imp_time, "g-o", linewidth=2, label="Improved"); plt.ylabel("总疏散时间 (s)"); plt.title("不同时段总疏散时间对比", fontweight="bold"); plt.grid(True, linestyle=":", alpha=0.7); plt.legend(); plt.savefig("02_Evacuation_Time_Comparison.png", dpi=300, bbox_inches="tight"); plt.close()
    plt.figure(figsize=(10, 6)); plt.plot(scenario_names, trad_queue, "r--^", linewidth=2, label="Traditional"); plt.plot(scenario_names, imp_queue, "g-o", linewidth=2, label="Improved"); plt.ylabel("总排队时间 (人·秒)"); plt.title("排队时间对比", fontweight="bold"); plt.grid(True, linestyle=":", alpha=0.7); plt.legend(); plt.savefig("03_Queueing_Time_Comparison.png", dpi=300, bbox_inches="tight"); plt.close()
    plt.figure(figsize=(10, 6)); plt.plot(scenario_names, [x / 1000 for x in trad_exp], "r--^", linewidth=2, label="Traditional"); plt.plot(scenario_names, [x / 1000 for x in imp_exp], "g-o", linewidth=2, label="Improved"); plt.fill_between(scenario_names, [x / 1000 for x in trad_exp], [x / 1000 for x in imp_exp], color="green", alpha=0.12); plt.ylabel("重度拥挤暴露 (千人·秒)"); plt.title("重度拥挤暴露对比", fontweight="bold"); plt.grid(True, linestyle=":", alpha=0.7); plt.legend(); plt.savefig("04_Congestion_Exposure_Comparison.png", dpi=300, bbox_inches="tight"); plt.close()
    plt.figure(figsize=(10, 6)); plt.plot(scenario_names, trad_speed, "r--^", linewidth=2, label="Traditional"); plt.plot(scenario_names, imp_speed, "g-o", linewidth=2, label="Improved"); plt.ylabel("平均速度 (m/s)"); plt.title("平均速度对比", fontweight="bold"); plt.grid(True, linestyle=":", alpha=0.7); plt.legend(); plt.savefig("05_Avg_Speed_Comparison.png", dpi=300, bbox_inches="tight"); plt.close()

    plt.figure(figsize=(10, 6))
    plt.plot(scenario_names, [((t - i) / t * 100) if t > 0 else 0.0 for t, i in zip(trad_time, imp_time)], "b-o", linewidth=2, label="时间改善率")
    plt.plot(scenario_names, [((t - i) / t * 100) if t > 0 else 0.0 for t, i in zip(trad_queue, imp_queue)], "m-s", linewidth=2, label="排队改善率")
    plt.plot(scenario_names, [((t - i) / t * 100) if t > 0 else 0.0 for t, i in zip(trad_exp, imp_exp)], "k-^", linewidth=2, label="暴露改善率")
    plt.ylabel("改善率 (%)"); plt.title("改进算法相对传统算法的改善率", fontweight="bold"); plt.grid(True, linestyle=":", alpha=0.7); plt.legend(); plt.savefig("06_Improvement_Rates.png", dpi=300, bbox_inches="tight"); plt.close()

def plot_line_specific_analysis(metrics_trad, metrics_imp, pop_dict):
    """新增模块：绘制各线路专属指标图表"""
    lines = [l for l, d in pop_dict.items() if sum(d.values()) > 0]

    # 1. 各线路清空时间对比
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(lines))
    t_trad = [metrics_trad["clearance_times_by_line"].get(l, 0) for l in lines]
    t_imp = [metrics_imp["clearance_times_by_line"].get(l, 0) for l in lines]

    ax.bar(x - 0.2, t_trad, 0.4, label='Traditional', color='#EF9A9A')
    ax.bar(x + 0.2, t_imp, 0.4, label='Improved', color='#80CBC4')
    ax.set_xticks(x)
    ax.set_xticklabels(lines)
    ax.set_ylabel('完全清空时间 (s)')
    ax.set_title('各线路独立清空时间对比', fontweight='bold', fontsize=14)
    ax.legend()
    plt.grid(axis='y', linestyle=':', alpha=0.7)
    plt.savefig("05_Line_Clearance_Time.png", dpi=300, bbox_inches='tight')
    plt.close()

    # 2. 各线路人群逃生出口去向 (堆叠柱状图证明智能绕路)
    # 2. 各线路人群逃生出口去向 (堆叠柱状图)
    for title, met in [("Traditional", metrics_trad), ("Improved", metrics_imp)]:
        exits_dict = met["exit_usage_by_line"]
        active_exits = sorted([e for e, lines_ppl in exits_dict.items() if sum(lines_ppl.values()) > 1.0])
        if not active_exits: continue

        fig, ax = plt.subplots(figsize=(14, 7))
        bottoms = np.zeros(len(active_exits))
        colors = plt.cm.Set3(np.linspace(0, 1, len(lines)))

        # 🌟 修复警告：明确生成 X 轴的物理位置坐标
        x_positions = np.arange(len(active_exits))

        for i, line in enumerate(lines):
            counts = [exits_dict[ext].get(line, 0.0) for ext in active_exits]
            # 🌟 修复警告：把柱子画在明确的物理坐标上
            ax.bar(x_positions, counts, label=line, bottom=bottoms, color=colors[i])
            bottoms += counts

        # 🌟 修复警告：先设置刻度位置，再填入文字标签，Matplotlib 就彻底闭嘴了！
        ax.set_xticks(x_positions)
        ax.set_xticklabels([e.replace("Exit_", "") for e in active_exits], rotation=45, ha='right')

        ax.set_ylabel('逃生人数')
        ax.set_title(f'人群逃生出口去向分布 ({title} 算法)', fontweight='bold', fontsize=14)
        ax.legend(title="人群来源")
        plt.grid(axis='y', linestyle=':', alpha=0.5)
        plt.savefig(f"06_Exit_Destinations_{title}.png", dpi=300, bbox_inches='tight')
        plt.close()


def get_evacuation_mode():
    print("\n" + "=" * 60)
    print("🚇 欢迎使用龙阳路站高精度客流仿真控制台")
    print("=" * 60)
    print("请选择客流加载模式：\n")
    print("  [1] 常规突发 (仅站台候车 + 站厅换乘人员)")
    print("  [2] 极限地狱 (满载列车迫停开门 + 站台/站厅原有人员)")
    print("-" * 60)
    while True:
        choice = input("👉 请输入序号 [1 / 2] 并按回车: ").strip()
        if choice in ['1', '2']: return int(choice)
        print("❌ 输入无效，请重新输入！")


if __name__ == "__main__":
    G = build_graph()
    plot_initial_topology(G)

    # 🌟 修复后的终极客流数据 (严格贴合你提供的表1-2最大瞬时客流)
    REAL_POPULATIONS = {
        "L2": {"train_1": 2400, "train_2": 2400, "platform_waiting": 236, "hall_transfer": 876},
        "L7": {"train_1": 1620, "train_2": 1620, "platform_waiting": 219, "hall_transfer": 281},
        "L16": {"train_1": 959, "train_2": 959, "platform_waiting": 42, "hall_transfer": 45},
        "L18": {"train_1": 1665, "train_2": 1665, "platform_waiting": 178, "hall_transfer": 313},
        "Maglev": {"train_1": 1980, "train_2": 1980, "platform_waiting": 0, "hall_transfer": 0}
    }

    mode = get_evacuation_mode()
    print(f"\n🚀 启动实验：【{'常规突发(无列车)' if mode == 1 else '极限地狱(含列车)'}】")

    current_pop_dict, total_p = {}, 0
    for line, data in REAL_POPULATIONS.items():
        t1 = 0 if mode == 1 else int(data["train_1"])
        t2 = 0 if mode == 1 else int(data["train_2"])
        pw = int(data["platform_waiting"])
        ht = int(data["hall_transfer"])
        current_pop_dict[line] = {"train_1": t1, "train_2": t2, "platform_waiting": pw, "hall_transfer": ht}
        total_p += (t1 + t2 + pw + ht)

    print(f"\n==== 总疏散人数: {total_p} 人 ====")

    metrics_trad = run_simulation_for_metrics(G, current_pop_dict, method="Traditional")
    metrics_imp = run_simulation_for_metrics(G, current_pop_dict, method="Improved")

    print(f"[Traditional] 全站时间 {metrics_trad['time']:.1f}s | 总排队 {metrics_trad['queueing_time']:.1f} 人·秒")
    print(f"[Improved]    全站时间 {metrics_imp['time']:.1f}s | 总排队 {metrics_imp['queueing_time']:.1f} 人·秒")

    print("\n📊 正在生成各线路独立维度的分析图表 (新增功能)...")
    plot_line_specific_analysis(metrics_trad, metrics_imp, current_pop_dict)

    print("\n🔍 正在生成抗拥挤的高清热力快照 (请稍候)...")
    # 截取第 30s, 90s, 200s 的疏散瞬间
    plot_comparative_snapshots(G, pop_dict=current_pop_dict, time_points=[30, 90, 200])

    print("\n✅ 所有高阶仿真和精美绘图任务已执行完毕！")