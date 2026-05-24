import copy
from collections import defaultdict

import networkx as nx
import pandas as pd

import network


LINE_ID = "L7"
ORIGIN = "Platform_L7"
EVACUEES = 1000.0
CASE_SPEC = {
    "case_id": "L7_PLATFORM_1000_SHARED_WAITING",
    "line": LINE_ID,
    "origin": ORIGIN,
    "start_role": "platform",
}
METHODS = [
    network.PAPER_SINGLE_PATH_METHOD,
    network.ANT_COLONY_METHOD,
    network.OUR_SINGLE_PATH_METHOD,
]


def path_str(path):
    if not path:
        return "N/A"
    return " -> ".join(path)


def line_exit_total(G):
    total = 0.0
    for node, data in G.nodes(data=True):
        if data.get("type") == "exit":
            total += float(data.get("people_dict", {}).get(LINE_ID, 0.0))
    return total


def line_non_exit_total(G):
    total = 0.0
    for node, data in G.nodes(data=True):
        if data.get("type") != "exit":
            total += float(data.get("people_dict", {}).get(LINE_ID, 0.0))
    return total


def line_in_transit_total(G):
    total = 0.0
    for item in G.graph.get("_transit_queue", []):
        total += float(item.get("line_shares", {}).get(LINE_ID, 0.0))
    return total


def active_line_nodes(G):
    nodes = []
    for node, data in G.nodes(data=True):
        if data.get("type") == "exit":
            continue
        if float(data.get("people_dict", {}).get(LINE_ID, 0.0)) > 0.1:
            nodes.append(node)
    return nodes


def get_path_for_node(G, node, method, shortest_dists, suffix_map):
    if method == network.ANT_COLONY_METHOD:
        return suffix_map.get(node)
    return network.get_best_path_to_exit(G, node, method, shortest_dists)


def line_waiting_zones(G):
    return network._platform_waiting_zone_nodes(G, LINE_ID)


def initial_path_map(G, method, shortest_dists, waiting_zones):
    path_map = {}
    for zone in waiting_zones:
        path_map[zone] = network.get_best_path_to_exit(G, zone, method, shortest_dists)
    return path_map


def run_metrics(case_state, method, per_zone_paths):
    target = {LINE_ID: EVACUEES}
    if method == network.ANT_COLONY_METHOD:
        return network.run_simulation_for_fixed_path_state(
            case_state,
            per_zone_paths,
            method=method,
            target_by_line=target,
        )
    return network.run_simulation_for_existing_state(
        case_state,
        method=method,
        target_by_line=target,
    )


def simulate_trace(case_state, method, per_zone_paths, waiting_zones):
    G = copy.deepcopy(case_state)
    shortest_dists = dict(nx.all_pairs_dijkstra_path_length(G, weight="length"))
    suffix_map = {}
    for zone, path in per_zone_paths.items():
        if not path:
            continue
        suffix_map[zone] = path
        for idx, node in enumerate(path):
            suffix_map.setdefault(node, path[idx:])

    if method == network.ANT_COLONY_METHOD:
        fixed_next = {}
        for path in per_zone_paths.values():
            if not path:
                continue
            for u, v in zip(path, path[1:]):
                if G.has_edge(u, v):
                    fixed_next[u] = v
        G.graph["_fixed_next_by_node"] = fixed_next

    prev_paths = {}
    route_change_rows = []
    zone_outflow_rows = []
    edge_flow = defaultdict(float)

    max_steps = 5000
    for _ in range(max_steps):
        current_time, _ = network._ensure_transit_state(G)
        network._process_transit_arrivals(G, current_time)

        for node in active_line_nodes(G):
            path = get_path_for_node(G, node, method, shortest_dists, suffix_map)
            path_key = tuple(path) if path else tuple()
            if prev_paths.get(node) != path_key:
                route_change_rows.append(
                    {
                        "method": method,
                        "time_s": current_time,
                        "node": node,
                        "people_at_node": float(G.nodes[node].get("people_dict", {}).get(LINE_ID, 0.0)),
                        "path": path_str(path),
                        "next_hop": path[1] if path and len(path) > 1 else None,
                    }
                )
                prev_paths[node] = path_key

        moves = network.get_step_moves(G, method, shortest_dists)

        for u, v, amount in moves:
            edge_flow[(u, v)] += float(amount)
            if u in waiting_zones and amount > 0:
                source_path = get_path_for_node(G, u, method, shortest_dists, suffix_map)
                zone_outflow_rows.append(
                    {
                        "method": method,
                        "time_s": current_time,
                        "from_zone": u,
                        "to_node": v,
                        "flow": float(amount),
                        "zone_people_before": float(G.nodes[u].get("people_dict", {}).get(LINE_ID, 0.0)),
                        "zone_path": path_str(source_path),
                    }
                )

        network._schedule_moves_as_transit(G, moves)
        G.graph["_sim_time"] = current_time + network.DELTA_T

        if (
            line_exit_total(G) >= EVACUEES - 1e-6
            and line_non_exit_total(G) <= 1e-6
            and line_in_transit_total(G) <= 1e-6
        ):
            break

    edge_rows = []
    for (u, v), flow in edge_flow.items():
        edge_rows.append(
            {
                "method": method,
                "from_node": u,
                "to_node": v,
                "flow_total": flow,
            }
        )
    edge_df = pd.DataFrame(edge_rows)
    if not edge_df.empty:
        edge_df = edge_df.sort_values(["method", "flow_total"], ascending=[True, False])

    node_rows = []
    inbound = defaultdict(float)
    for (u, v), flow in edge_flow.items():
        inbound[v] += flow
    for zone in waiting_zones:
        inbound[zone] += float(case_state.nodes[zone].get("people_dict", {}).get(LINE_ID, 0.0))
    for node, flow in inbound.items():
        node_rows.append(
            {
                "method": method,
                "node": node,
                "throughput": flow,
            }
        )
    node_df = pd.DataFrame(node_rows)
    if not node_df.empty:
        node_df = node_df.sort_values(["method", "throughput"], ascending=[True, False])

    return (
        pd.DataFrame(route_change_rows),
        pd.DataFrame(zone_outflow_rows),
        edge_df,
        node_df,
    )


def main():
    G_base = network.build_graph()
    case_state = network.build_single_path_case_state(G_base, CASE_SPEC, evacuees=EVACUEES)
    shortest_dists = dict(nx.all_pairs_dijkstra_path_length(case_state, weight="length"))
    waiting_zones = line_waiting_zones(case_state)

    summary_rows = []
    initial_rows = []
    route_change_frames = []
    zone_outflow_frames = []
    edge_flow_frames = []
    node_flow_frames = []

    for method in METHODS:
        per_zone_paths = initial_path_map(case_state, method, shortest_dists, waiting_zones)
        metrics = run_metrics(case_state, method, per_zone_paths)
        route_df, zone_df, edge_df, node_df = simulate_trace(case_state, method, per_zone_paths, waiting_zones)

        exit_usage = []
        for exit_node, line_map in metrics.get("exit_usage_by_line", {}).items():
            count = float(line_map.get(LINE_ID, 0.0))
            if count > 0.01:
                exit_usage.append((exit_node, count))
        exit_usage.sort(key=lambda item: item[1], reverse=True)

        first_hop_usage = (
            zone_df.groupby("to_node", as_index=False)["flow"]
            .sum()
            .sort_values("flow", ascending=False)
            if not zone_df.empty
            else pd.DataFrame(columns=["to_node", "flow"])
        )

        summary_rows.append(
            {
                "method": method,
                "evacuation_time_s": metrics["time"],
                "queueing_time_person_s": metrics["queueing_time"],
                "congestion_exposure_person_s": metrics["congestion_exposure_time"],
                "avg_speed_mps": metrics["avg_speed"],
                "exit_usage": "; ".join(f"{exit_node}:{count:.1f}" for exit_node, count in exit_usage),
                "waiting_zone_first_hop_usage": "; ".join(
                    f"{row.to_node}:{row.flow:.1f}" for row in first_hop_usage.itertuples(index=False)
                ),
            }
        )

        for zone in waiting_zones:
            zone_path = per_zone_paths.get(zone)
            initial_rows.append(
                {
                    "method": method,
                    "origin_zone": zone,
                    "initial_people": float(case_state.nodes[zone].get("people_dict", {}).get(LINE_ID, 0.0)),
                    "initial_path": path_str(zone_path),
                    "initial_next_hop": zone_path[1] if zone_path and len(zone_path) > 1 else None,
                    "initial_exit": zone_path[-1] if zone_path else None,
                    "initial_path_length_m": network._path_total_length(case_state, zone_path) if zone_path else None,
                }
            )

        route_change_frames.append(route_df)
        zone_outflow_frames.append(zone_df)
        edge_flow_frames.append(edge_df)
        node_flow_frames.append(node_df)

    summary_df = pd.DataFrame(summary_rows)
    initial_df = pd.DataFrame(initial_rows)
    route_change_df = pd.concat(route_change_frames, ignore_index=True)
    zone_outflow_df = pd.concat(zone_outflow_frames, ignore_index=True)
    edge_flow_df = pd.concat(edge_flow_frames, ignore_index=True)
    node_flow_df = pd.concat(node_flow_frames, ignore_index=True)

    summary_path = "128_L7_platform1000_shared_waiting_method_summary.csv"
    initial_path_csv = "129_L7_platform1000_shared_waiting_initial_paths.csv"
    route_change_path = "130_L7_platform1000_shared_waiting_route_change_log.csv"
    zone_outflow_path = "131_L7_platform1000_shared_waiting_zone_outflow_timeseries.csv"
    edge_flow_path = "132_L7_platform1000_shared_waiting_edge_flow_totals.csv"
    node_flow_path = "133_L7_platform1000_shared_waiting_node_throughput.csv"
    report_path = "134_L7_platform1000_shared_waiting_report.md"

    summary_df.to_csv(summary_path, index=False, encoding="utf-8-sig")
    initial_df.to_csv(initial_path_csv, index=False, encoding="utf-8-sig")
    route_change_df.to_csv(route_change_path, index=False, encoding="utf-8-sig")
    zone_outflow_df.to_csv(zone_outflow_path, index=False, encoding="utf-8-sig")
    edge_flow_df.to_csv(edge_flow_path, index=False, encoding="utf-8-sig")
    node_flow_df.to_csv(node_flow_path, index=False, encoding="utf-8-sig")

    lines = ["# L7 Platform 1000 Trace (Shared Waiting Zones)", ""]
    for row in summary_df.itertuples(index=False):
        lines.append(f"## {row.method}")
        lines.append(f"- Evacuation time: {row.evacuation_time_s:.1f}s")
        lines.append(f"- Queueing time: {row.queueing_time_person_s:.2f} person*s")
        lines.append(f"- Congestion exposure: {row.congestion_exposure_person_s:.2f} person*s")
        lines.append(f"- Avg speed: {row.avg_speed_mps:.4f} m/s")
        lines.append(f"- Exit usage: {row.exit_usage}")
        lines.append(f"- Waiting-zone first-hop usage: {row.waiting_zone_first_hop_usage}")
        zone_rows = initial_df[initial_df["method"] == row.method]
        lines.append("- Initial path by waiting zone:")
        for zone_row in zone_rows.itertuples(index=False):
            lines.append(
                f"  - {zone_row.origin_zone} ({zone_row.initial_people:.1f} people): "
                f"{zone_row.initial_path}"
            )
        top_edges = edge_flow_df[edge_flow_df["method"] == row.method].head(10)
        lines.append("- Top edges by cumulative flow:")
        for edge_row in top_edges.itertuples(index=False):
            lines.append(f"  - {edge_row.from_node} -> {edge_row.to_node}: {edge_row.flow_total:.1f}")
        lines.append("")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(summary_df.to_string(index=False))
    print(f"\nSaved: {summary_path}, {initial_path_csv}, {route_change_path}, {zone_outflow_path}, {edge_flow_path}, {node_flow_path}, {report_path}")


if __name__ == "__main__":
    main()
