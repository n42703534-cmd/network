import math
import random

import networkx as nx


PAPER_SINGLE_PATH_METHOD = "PaperImprovedAStar"
OUR_SINGLE_PATH_METHOD = "AdaptiveSingleNextHop"
OUR_SPLIT_GUIDANCE_METHOD = "OurSplitGuidance"
OUR_NO_SOURCE_RELEASE_METHOD = "NoUpstreamLoadPenalty"
OUR_NO_DOWNSTREAM_RELEASE_METHOD = "NoDownstreamLoadPenalty"
OUR_NO_EXIT_PRESSURE_METHOD = "NoExitPressurePenalty"
OUR_NO_PREDICTIVE_PENALTIES_METHOD = "NoPredictivePenalties"
ANT_COLONY_METHOD = "AntColony"

METHOD_ALIASES = {
    "ClassicImproved": PAPER_SINGLE_PATH_METHOD,
    "Improved": OUR_SPLIT_GUIDANCE_METHOD,
    "ACO": ANT_COLONY_METHOD,
    "AntColonyOptimization": ANT_COLONY_METHOD,
    "OurSinglePath": OUR_SINGLE_PATH_METHOD,
    "OurNoSourceRelease": OUR_NO_SOURCE_RELEASE_METHOD,
    "OurNoDownstreamRelease": OUR_NO_DOWNSTREAM_RELEASE_METHOD,
    "OurNoExitPressure": OUR_NO_EXIT_PRESSURE_METHOD,
    "OurNoPredictivePenalties": OUR_NO_PREDICTIVE_PENALTIES_METHOD,
}

PAPER_FREE_SPEED = 1.427
PAPER_DENSITY_FREE = 0.2
PAPER_DENSITY_JAM = 4.0
PAPER_DENSITY_SLOPE = 0.3549
PAPER_LENGTH_ALPHA = 0.15
PAPER_SPEED_BETA = 0.85
PAPER_HEURISTIC_GAMMA = 0.10
PAPER_DENSITY_CUTOFF = 3.0
PAPER_FACILITY_SPEED_LIMITS = {
    "flat": PAPER_FREE_SPEED,
    # Station adaptation of Meng et al.'s improved A*: their cruise-ship case
    # assumes stair cost equals flat passage cost; metro evacuation needs
    # facility-specific walking-speed caps for stairs and escalators.
    "stair": 0.75,
    "escalator": 0.50,
}
OUR_GATE_QUEUE_WEIGHT = 3.5
OUR_GATE_SOURCE_RELEASE_WEIGHT = 0.18
OUR_GATE_SERVICE_RATE_WEIGHT = 3.0
ACO_ANT_COUNT = 20
ACO_ITERATIONS = 40
ACO_ALPHA = 1.0
ACO_BETA = 2.0
ACO_EVAPORATION = 0.35
ACO_DEPOSIT_Q = 100.0
OUR_PATH_DOWNSTREAM_RELEASE_WEIGHT = 0.45
OUR_PATH_EXIT_PRESSURE_WEIGHT = 0.55
OUR_DENSITY_MODERATE_THRESHOLD = 2.5
OUR_DENSITY_SEVERE_THRESHOLD = 4.0
OUR_DENSITY_MODERATE_FACTOR = 0.65
OUR_DENSITY_SEVERE_SURCHARGE = 2.5
OUR_GATE_OVERLOAD_FACTOR = 0.6
OUR_SERVICE_WAIT_TIME_WEIGHT = 1.1
SERVICE_QUEUE_HORIZON_SECONDS = 30.0
SERVICE_MODERATE_LOAD_RATIO = 1.0
SERVICE_SEVERE_LOAD_RATIO = 2.0

OUR_PREDICTIVE_VARIANTS = {
    OUR_SINGLE_PATH_METHOD,
    OUR_SPLIT_GUIDANCE_METHOD,
    OUR_NO_SOURCE_RELEASE_METHOD,
    OUR_NO_DOWNSTREAM_RELEASE_METHOD,
    OUR_NO_EXIT_PRESSURE_METHOD,
    OUR_NO_PREDICTIVE_PENALTIES_METHOD,
}


def normalize_method(method):
    return METHOD_ALIASES.get(method, method)


def routing_base_method(method):
    method = normalize_method(method)
    if method in OUR_PREDICTIVE_VARIANTS:
        return OUR_SINGLE_PATH_METHOD
    return method


def uses_dynamic_a_star(method):
    return routing_base_method(method) in {PAPER_SINGLE_PATH_METHOD, OUR_SINGLE_PATH_METHOD}


def uses_predictive_single_path(method):
    return routing_base_method(method) == OUR_SINGLE_PATH_METHOD


def uses_ant_colony(method):
    return routing_base_method(method) == ANT_COLONY_METHOD


def uses_predictive_guidance_family(method):
    return normalize_method(method) in OUR_PREDICTIVE_VARIANTS


def our_penalty_weights(method):
    method = normalize_method(method)
    weights = {
        "source_release": OUR_GATE_SOURCE_RELEASE_WEIGHT,
        "downstream_release": OUR_PATH_DOWNSTREAM_RELEASE_WEIGHT,
        "exit_pressure": OUR_PATH_EXIT_PRESSURE_WEIGHT,
    }
    if method == OUR_NO_SOURCE_RELEASE_METHOD:
        weights["source_release"] = 0.0
    elif method == OUR_NO_DOWNSTREAM_RELEASE_METHOD:
        weights["downstream_release"] = 0.0
    elif method == OUR_NO_EXIT_PRESSURE_METHOD:
        weights["exit_pressure"] = 0.0
    elif method == OUR_NO_PREDICTIVE_PENALTIES_METHOD:
        weights = {key: 0.0 for key in weights}
    return weights


def heuristic_cost(u, v, d_dict, method):
    method = routing_base_method(method)
    dist = float(d_dict.get(u, {}).get(v, 0.0))
    if method == PAPER_SINGLE_PATH_METHOD:
        return PAPER_HEURISTIC_GAMMA * dist
    if method == OUR_SINGLE_PATH_METHOD:
        return dist / 1.427
    return 0.0


def allowed_exit_nodes(G):
    case_line = G.graph.get("_single_path_case_line")
    exits = [n for n, data in G.nodes(data=True) if data.get("type") == "exit"]
    if not case_line:
        return exits

    line_tag = f"_{case_line}_"
    filtered = [n for n in exits if line_tag in n]
    return filtered or exits


def node_out_capacity(G, node):
    total = 0.0
    for succ in G.successors(node):
        total += float(G[node][succ].get("capacity", 0.0))
    return max(total, 0.001)


def node_reserved_inflow(G, node):
    if node not in G.nodes:
        return 0.0
    return max(float(G.nodes[node].get("_guidance_reserved_inflow", 0.0)), 0.0)


def is_capacity_service_node(G, node):
    if node not in G.nodes:
        return False
    node_type = str(G.nodes[node].get("type", "")).lower()
    return node_type in {"stair", "escalator"} or node_type.startswith("gate") or "gate" in node_type


def node_service_capacity(G, node):
    if node not in G.nodes:
        return 0.001
    capacity = float(G.nodes[node].get("capacity", 0.0) or 0.0)
    if not math.isfinite(capacity) or capacity <= 0:
        capacity = node_out_capacity(G, node)
    return max(capacity, 0.001)


def spatial_effective_density(G, node, obstacle_area=0.0):
    if node not in G.nodes:
        return 0.0
    area = max(float(G.nodes[node].get("area", 1.0)), 0.1)
    obstacle_area = min(max(float(obstacle_area), 0.0), max(area - 0.1, 0.0))
    effective_area = max(area - obstacle_area, 0.1)
    people_at_node = float(G.nodes[node].get("people", 0.0)) + node_reserved_inflow(G, node)
    return people_at_node / effective_area


def node_congestion_index(G, node, obstacle_area=0.0):
    if is_capacity_service_node(G, node):
        people_at_node = float(G.nodes[node].get("people", 0.0)) + node_reserved_inflow(G, node)
        service_capacity = node_service_capacity(G, node)
        service_window = service_capacity * SERVICE_QUEUE_HORIZON_SECONDS
        return people_at_node / max(service_window, 0.001), "capacity_ratio"
    return spatial_effective_density(G, node, obstacle_area), "density"


def edge_runtime_density(G, u, v):
    if not G.has_edge(u, v):
        return 0.0
    density = float(G[u][v].get("runtime_density", 0.0) or 0.0)
    if not math.isfinite(density):
        return 0.0
    return max(density, 0.0)


def exit_approach_pressure(G, exit_node):
    if exit_node not in G.nodes:
        return 0.0

    preds = list(G.predecessors(exit_node))
    if not preds:
        return 0.0

    approach_people = 0.0
    inbound_capacity = 0.0
    for pred in preds:
        approach_people += float(G.nodes[pred].get("people", 0.0)) + node_reserved_inflow(G, pred)
        inbound_capacity += float(G[pred][exit_node].get("capacity", 0.0))
    return approach_people / max(inbound_capacity, 0.001)


def approach_pressure(G, pred, exit_node):
    """Per-predecessor local approach pressure for a single (pred, exit) pair.

    P(pred, exit) = people(pred) / capacity(pred -> exit)

    This is the pre-computed form used by update_dynamic_weights to attach
    exit-area congestion to edges entering *pred*, so that A* naturally
    avoids approaches to already-crowded exits.
    """
    if pred not in G.nodes or exit_node not in G.nodes:
        return 0.0
    if not G.has_edge(pred, exit_node):
        return 0.0
    people_at_pred = float(G.nodes[pred].get("people", 0.0)) + node_reserved_inflow(G, pred)
    edge_capacity = max(float(G[pred][exit_node].get("capacity", 0.0)), 0.001)
    return people_at_pred / edge_capacity


def smoothed_approach_pressure(G, pred, exit_node):
    """EMA-smoothed per-predecessor approach pressure."""
    store = G.graph.get("_approach_pressure_smoothed")
    if store is None:
        return approach_pressure(G, pred, exit_node)
    return float(store.get((pred, exit_node), 0.0))


def edge_width_proxy(G, u, v):
    data = G[u][v]
    width_limit = data.get("width_limit")
    if width_limit is not None and float(width_limit) > 0:
        return float(width_limit)

    capacity = float(data.get("capacity", 0.0))
    if capacity > 0:
        return max(capacity / (5000.0 / 3600.0), 0.6)

    return 1.0


def paper_edge_area(G, u, v):
    data = G[u][v]
    length = max(float(data.get("length", 0.0)), 0.0)
    width = max(edge_width_proxy(G, u, v), 0.1)
    return max(length * width, 0.1)


def paper_obstacle_area(G, u, v):
    edge_obs = float(G[u][v].get("obstacle_area", 0.0))
    node_obs = float(G.nodes[v].get("obstacle_area", 0.0))
    return max(edge_obs + node_obs, 0.0)


def paper_effective_density(G, u, v):
    area = paper_edge_area(G, u, v)
    obstacle_area = min(paper_obstacle_area(G, u, v), max(area - 0.1, 0.0))
    effective_area = max(area - obstacle_area, 0.1)
    people_at_v = float(G.nodes[v].get("people", 0.0)) + node_reserved_inflow(G, v)
    return max(people_at_v / effective_area, edge_runtime_density(G, u, v))


def our_effective_density(G, u, v):
    node_density = spatial_effective_density(G, v, paper_obstacle_area(G, u, v))
    return max(node_density, edge_runtime_density(G, u, v))


def paper_speed_from_density(density):
    if density <= PAPER_DENSITY_FREE:
        return PAPER_FREE_SPEED
    if density <= PAPER_DENSITY_JAM:
        return max(PAPER_FREE_SPEED - PAPER_DENSITY_SLOPE * density, 0.0)
    return 0.0


def paper_facility_speed_limit(G, u, v):
    edge_type = str(G[u][v].get("edge_type", "")).lower()
    u_type = str(G.nodes[u].get("type", "")).lower()
    v_type = str(G.nodes[v].get("type", "")).lower()
    if "stair" in edge_type or "stair" in u_type or "stair" in v_type:
        return PAPER_FACILITY_SPEED_LIMITS["stair"]
    if "escalator" in edge_type or "escalator" in u_type or "escalator" in v_type:
        return PAPER_FACILITY_SPEED_LIMITS["escalator"]
    return PAPER_FACILITY_SPEED_LIMITS["flat"]


def paper_edge_cost(G, u, v):
    length = float(G[u][v].get("length", 0.0))
    density = paper_effective_density(G, u, v)
    if density > PAPER_DENSITY_CUTOFF:
        return float("inf")
    walk_speed = min(paper_speed_from_density(density), paper_facility_speed_limit(G, u, v))
    if walk_speed <= 0.0:
        return float("inf")
    return PAPER_LENGTH_ALPHA * length + PAPER_SPEED_BETA * (1.0 / walk_speed)


def our_edge_cost_components(G, u, v, speed_fn, method=OUR_SINGLE_PATH_METHOD):
    data = G[u][v]
    length = float(data.get("length", 0.0))
    walk_time_base = length / 1.427
    weights = our_penalty_weights(method)
    zero = {
        "base_cost": 0.0,
        "gate_queue_penalty": 0.0,
        "service_penalty": 0.0,
        "source_release_penalty": 0.0,
        "downstream_release_penalty": 0.0,
        "exit_pressure_penalty": 0.0,
        "total_cost": 0.0,
    }

    if v not in G.nodes:
        return zero

    node_type = G.nodes[v].get("type", "")
    people_at_v = float(G.nodes[v].get("people", 0.0)) + node_reserved_inflow(G, v)
    source_people = float(G.nodes[u].get("people", 0.0))
    edge_capacity = max(float(data.get("capacity", 0.0)), 0.001)

    if is_capacity_service_node(G, v):
        mu = node_service_capacity(G, v)
        queue_ratio, _ = node_congestion_index(G, v)
        queue_delay = people_at_v / max(mu, 0.001)
        overload = max(queue_ratio - 1.0, 0.0)
        components = dict(zero)
        facility_speed = max(paper_facility_speed_limit(G, u, v), 0.1)
        components["base_cost"] = length / facility_speed if length > 0 else walk_time_base
        components["gate_queue_penalty"] = (
            OUR_SERVICE_WAIT_TIME_WEIGHT
            * queue_delay
            * (1.0 + OUR_GATE_OVERLOAD_FACTOR * overload)
            + OUR_GATE_QUEUE_WEIGHT * queue_ratio
        )
        components["service_penalty"] = OUR_GATE_SERVICE_RATE_WEIGHT * (1.0 / max(mu, 0.001))
        components["source_release_penalty"] = weights["source_release"] * (source_people / edge_capacity)
        components["total_cost"] = (
            components["base_cost"]
            + components["gate_queue_penalty"]
            + components["service_penalty"]
            + components["source_release_penalty"]
        )
        return components

    if "virtual" in node_type:
        mu = float(G.nodes[v].get("capacity", 1.0))
        components = dict(zero)
        components["base_cost"] = walk_time_base + 1.5 * (people_at_v / max(mu, 0.001))
        components["total_cost"] = components["base_cost"]
        return components

    density = our_effective_density(G, u, v)
    safe_speed = max(float(speed_fn(density)), 0.1)
    base_travel_time = length / safe_speed
    moderate_over = max(density - OUR_DENSITY_MODERATE_THRESHOLD, 0.0)
    severe_over = max(density - OUR_DENSITY_SEVERE_THRESHOLD, 0.0)
    density_factor = 1.0 + OUR_DENSITY_MODERATE_FACTOR * moderate_over
    density_surcharge = OUR_DENSITY_SEVERE_SURCHARGE * (severe_over ** 2)
    base_cost = base_travel_time * density_factor + density_surcharge
    components = dict(zero)
    components["base_cost"] = base_cost
    components["source_release_penalty"] = weights["source_release"] * (source_people / edge_capacity)
    components["downstream_release_penalty"] = (
        weights["downstream_release"] * (people_at_v / node_out_capacity(G, v))
    )
    components["total_cost"] = (
        components["base_cost"]
        + components["source_release_penalty"]
        + components["downstream_release_penalty"]
    )
    return components


def our_path_cost_components(G, path, speed_fn, method=OUR_SINGLE_PATH_METHOD):
    components = {
        "base_cost": 0.0,
        "gate_queue_penalty": 0.0,
        "service_penalty": 0.0,
        "source_release_penalty": 0.0,
        "downstream_release_penalty": 0.0,
        "exit_pressure_penalty": 0.0,
        "total_cost": 0.0,
    }
    if not path or len(path) <= 1:
        return components

    for u, v in zip(path, path[1:]):
        edge_components = our_edge_cost_components(G, u, v, speed_fn, method=method)
        for key in components:
            if key == "exit_pressure_penalty":
                continue
            components[key] += edge_components.get(key, 0.0)

    weights = our_penalty_weights(method)
    components["exit_pressure_penalty"] = weights["exit_pressure"] * exit_approach_pressure(G, path[-1])
    components["total_cost"] = sum(components[key] for key in components if key != "total_cost")
    return components


def edge_dynamic_cost(G, u, v, method, speed_fn):
    normalized_method = normalize_method(method)
    method = routing_base_method(normalized_method)
    data = G[u][v]
    length = float(data.get("length", 0.0))
    walk_time_base = length / 1.427

    if method == PAPER_SINGLE_PATH_METHOD:
        return paper_edge_cost(G, u, v)

    if method == ANT_COLONY_METHOD:
        return max(length, 0.001)

    if method == OUR_SINGLE_PATH_METHOD:
        return our_edge_cost_components(G, u, v, speed_fn, method=normalized_method)["total_cost"]

    return length


def _stable_seed(*parts):
    text = "|".join(str(part) for part in parts)
    seed = 0
    for idx, char in enumerate(text):
        seed = (seed + (idx + 1) * ord(char)) % (2**32)
    return seed


def _weighted_choice(items, weights, rng):
    total = sum(weights)
    if total <= 0:
        return rng.choice(items)
    threshold = rng.random() * total
    running = 0.0
    for item, weight in zip(items, weights):
        running += weight
        if running >= threshold:
            return item
    return items[-1]


def ant_colony_best_path(G, current_node, exits, weight_key="sim_weight"):
    if current_node not in G.nodes:
        return None

    finite_edges = [
        (u, v)
        for u, v, data in G.edges(data=True)
        if data.get(weight_key, float("inf")) != float("inf")
    ]
    pheromone = {edge: 1.0 for edge in finite_edges}
    if not pheromone:
        return None

    current_time = int(float(G.graph.get("_sim_time", 0.0)))
    rng = random.Random(_stable_seed(current_node, current_time, len(G.nodes), len(G.edges)))
    best_path = None
    best_cost = float("inf")
    max_steps = max(len(G.nodes), 1)

    for _ in range(ACO_ITERATIONS):
        iteration_paths = []
        for _ant in range(ACO_ANT_COUNT):
            node = current_node
            path = [node]
            visited = {node}
            cost = 0.0

            for _step in range(max_steps):
                if node in exits:
                    break

                successors = [
                    succ
                    for succ in G.successors(node)
                    if succ not in visited and G[node][succ].get(weight_key, float("inf")) != float("inf")
                ]
                if not successors:
                    break

                weights = []
                for succ in successors:
                    edge = (node, succ)
                    edge_cost = max(float(G[node][succ].get(weight_key, 1.0)), 0.001)
                    tau = pheromone.get(edge, 1.0) ** ACO_ALPHA
                    eta = (1.0 / edge_cost) ** ACO_BETA
                    weights.append(tau * eta)

                next_node = _weighted_choice(successors, weights, rng)
                cost += float(G[node][next_node].get(weight_key, 0.0))
                node = next_node
                path.append(node)
                visited.add(node)

                if node in exits:
                    break

            if path[-1] in exits:
                iteration_paths.append((path, cost))
                if cost < best_cost:
                    best_path = path
                    best_cost = cost

        for edge in list(pheromone):
            pheromone[edge] *= (1.0 - ACO_EVAPORATION)
            pheromone[edge] = max(pheromone[edge], 0.001)

        for path, cost in iteration_paths:
            deposit = ACO_DEPOSIT_Q / max(cost, 0.001)
            for i in range(len(path) - 1):
                edge = (path[i], path[i + 1])
                pheromone[edge] = pheromone.get(edge, 0.001) + deposit

    return best_path


def update_dynamic_weights(G, method, speed_fn, weight_key="sim_weight"):
    for u, v, data in G.edges(data=True):
        data[weight_key] = edge_dynamic_cost(G, u, v, method, speed_fn)

    # Integrate per-predecessor approach pressure into edge weights so that
    # A* naturally avoids approaches to already-crowded exits during search.
    if uses_predictive_single_path(method):
        weights = our_penalty_weights(method)
        ep_weight = weights.get("exit_pressure", 0.0)
        if ep_weight > 0:
            exits = [n for n, d in G.nodes(data=True) if d.get("type") == "exit"]
            for exit_node in exits:
                for pred in G.predecessors(exit_node):
                    pressure = smoothed_approach_pressure(G, pred, exit_node)
                    if pressure <= 0:
                        continue
                    extra = ep_weight * pressure
                    for pred_pred in G.predecessors(pred):
                        if G.has_edge(pred_pred, pred):
                            current = float(G[pred_pred][pred].get(weight_key, 0.0))
                            G[pred_pred][pred][weight_key] = current + extra


def enumerate_exit_paths(G, current_node, method, shortest_dists, speed_fn, weight_key="sim_weight"):
    method = normalize_method(method)
    exits = allowed_exit_nodes(G)
    if not exits:
        return []

    update_dynamic_weights(G, method, speed_fn, weight_key=weight_key)

    if uses_ant_colony(method):
        path = ant_colony_best_path(G, current_node, set(exits), weight_key=weight_key)
        if not path or len(path) <= 1:
            return []
        cost = sum(G[path[i]][path[i + 1]][weight_key] for i in range(len(path) - 1))
        return [
            {
                "target": path[-1],
                "path": path,
                "next_hop": path[1],
                "cost": cost,
            }
        ]

    candidates = []

    for target in exits:
        try:
            if uses_dynamic_a_star(method):
                path = nx.astar_path(
                    G,
                    current_node,
                    target,
                    heuristic=lambda u, v: heuristic_cost(u, v, shortest_dists, method),
                    weight=weight_key,
                )
            else:
                path = nx.shortest_path(G, current_node, target, weight=weight_key)
        except nx.NetworkXNoPath:
            continue

        if len(path) <= 1:
            continue

        cost = sum(G[path[i]][path[i + 1]][weight_key] for i in range(len(path) - 1))

        candidates.append(
            {
                "target": target,
                "path": path,
                "next_hop": path[1],
                "cost": cost,
            }
        )

    candidates.sort(key=lambda item: item["cost"])
    return candidates


def get_best_path_to_exit(G, current_node, method, shortest_dists, speed_fn):
    candidates = enumerate_exit_paths(G, current_node, method, shortest_dists, speed_fn)
    if not candidates:
        return None
    return candidates[0]["path"]


def get_best_next_node(G, current_node, method, shortest_dists, speed_fn):
    candidates = enumerate_exit_paths(G, current_node, method, shortest_dists, speed_fn)
    if not candidates:
        return None
    return candidates[0]["next_hop"]
