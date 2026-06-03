"""Diagnose L2 exit path costs for each source group."""
import importlib.util, sys, types, math
import networkx as nx

def _install_noop_matplotlib():
    if importlib.util.find_spec("matplotlib") is not None:
        return
    m = types.ModuleType("matplotlib")
    p = types.ModuleType("matplotlib.pyplot")
    pt = types.ModuleType("matplotlib.patches")
    def _n(*a,**kw): return None
    p.figure=_n; p.subplots=lambda *a,**kw:(None,None); p.plot=_n; p.bar=_n; p.savefig=_n
    p.close=_n; p.tight_layout=_n; p.grid=_n; p.xlabel=_n; p.ylabel=_n; p.title=_n
    p.legend=_n; p.suptitle=_n; p.rcParams={}; pt.Patch=object
    m.pyplot=p; m.patches=pt
    sys.modules["matplotlib"]=m; sys.modules["matplotlib.pyplot"]=p; sys.modules["matplotlib.patches"]=pt

_install_noop_matplotlib()
sys.path.insert(0, ".")

import network
import single_path_routing as spr

# Build empty population to get a clean graph
pop = {}
for line in network.TRAIN_PHYSICS:
    pop[line] = {"train_1": 0, "train_2": 0, "platform_waiting": 0, "hall_people": 0, "transfer_people": 0}

graph = network.build_graph()

# Now trace paths from L2 platform zones and L2 hall to each L2 exit
L2_SOURCES = [
    "Platform_L2_Z1_Wait", "Platform_L2_Z2_Wait", "Platform_L2_Z3_Wait", "Platform_L2_Z4_Wait",
]

# Find hall and transfer arrival nodes by searching for relevant names
EXTRA_SOURCES = []
for node in sorted(graph.nodes()):
    nl = node.lower()
    if ("l2" in nl or "l2" in node) and ("hall" in nl or "hall" in node):
        EXTRA_SOURCES.append(node)
    if "l7to" in nl and "hall" in nl:
        EXTRA_SOURCES.append(node)
    if "maglev_to_l2" in nl and "arriv" in nl:
        EXTRA_SOURCES.append(node)

print(f"Extra sources found: {EXTRA_SOURCES}")
L2_SOURCES.extend(EXTRA_SOURCES)

L2_EXITS = ["Exit_L2_2", "Exit_L2_3", "Exit_L2_4", "Exit_L2_6"]

def speed_fn(d):
    if d <= spr.PAPER_DENSITY_FREE: return spr.PAPER_FREE_SPEED
    if d <= spr.PAPER_DENSITY_JAM: return max(spr.PAPER_FREE_SPEED - spr.PAPER_DENSITY_SLOPE * d, 0.0)
    return 0.0

print("=" * 80)
print("L2 EXIT PATH COST ANALYSIS (clean graph, no load)")
print("=" * 80)

# No precompute - use Dijkstra directly to avoid A* heuristic requirements

# Print L2 gate capacities
print("\nL2 Gate Configuration:")
for gate_name in ["Gate_L2_N_West", "Gate_L2_N_East", "Gate_L2_S_West", "Gate_L2_S_East"]:
    if gate_name in graph.nodes:
        nd = graph.nodes[gate_name]
        cap = nd.get("capacity", "?")
        ntype = nd.get("type", "?")
        width_info = ""
        # Find connected exit
        for succ in graph.successors(gate_name):
            if graph.nodes[succ].get("type") == "exit":
                exit_w = graph[gate_name][succ].get("width_limit", "?")
                width_info = f" -> {succ} (width={exit_w})"
        print(f"  {gate_name}: type={ntype}, capacity={cap:.1f}{width_info}")

print(f"\nL2 Gate -> Exit edges:")
for gate_name in ["Gate_L2_N_West", "Gate_L2_N_East", "Gate_L2_S_West", "Gate_L2_S_East"]:
    for succ in graph.successors(gate_name):
        edge_data = graph[gate_name][succ]
        wl = edge_data.get("width_limit", "?")
        length = edge_data.get("length", "?")
        cap = edge_data.get("capacity", "?")
        print(f"  {gate_name} -> {succ}: width_limit={wl}, length={length}, capacity={cap}")

# For each source, compute paths to each exit using Dijkstra
for source in L2_SOURCES:
    if source not in graph.nodes:
        continue
    print(f"\n{'─'*70}")
    print(f"Source: {source}")
    if source in graph.nodes:
        src_data = graph.nodes[source]
        print(f"  area={src_data.get('area','?')}, capacity={src_data.get('capacity','?')}")

    for exit_name in L2_EXITS:
        try:
            path = nx.dijkstra_path(graph, source, exit_name, weight="length")
        except nx.NetworkXNoPath:
            print(f"  {exit_name}: NO PATH")
            continue

        # Compute cost breakdown
        comps = spr.our_path_cost_components(graph, path, speed_fn, spr.OUR_SINGLE_PATH_METHOD)

        # Show gates on path
        gates_on_path = [n for n in path if n in graph.nodes and
                        ("gate" in str(graph.nodes[n].get("type","")).lower())]

        # Print each segment
        print(f"  {exit_name}: total_cost={comps['total_cost']:.2f}  (path: {' → '.join(gates_on_path + [exit_name])})")
        print(f"    base={comps['base_cost']:.2f}  queue={comps['gate_queue_penalty']:.2f}  "
              f"service={comps['service_penalty']:.2f}  src_release={comps['source_release_penalty']:.2f}  "
              f"ds_release={comps['downstream_release_penalty']:.2f}  exit_pressure={comps['exit_pressure_penalty']:.2f}")

print("\n" + "=" * 80)
print("DISTANCES summary (Dijkstra path length in meters)")
print("=" * 80)
print(f"{'Source':<30s}", end="")
for exit_name in L2_EXITS:
    print(f"  {exit_name:>12s}", end="")
print()
for source in L2_SOURCES:
    if source not in graph.nodes:
        continue
    print(f"{source:<30s}", end="")
    for exit_name in L2_EXITS:
        try:
            path = nx.dijkstra_path(graph, source, exit_name, weight="length")
            d = sum(graph[path[i]][path[i+1]].get("length", 0) for i in range(len(path)-1))
            print(f"  {d:12.1f}", end="")
        except:
            print(f"  {'N/A':>12s}", end="")
    print()

# Also show the gates each L2 source can reach
print("\n" + "=" * 80)
print("L2 Exit widths vs Gate lane counts")
print("=" * 80)
for exit_name in L2_EXITS:
    if exit_name in graph.nodes:
        exit_data = graph.nodes[exit_name]
        print(f"  {exit_name}: width={exit_data.get('width','?')}")
        # Find predecessor gate
        for pred in graph.predecessors(exit_name):
            gate_data = graph.nodes[pred]
            lanes = gate_data.get("lane_count", "?")
            cap = gate_data.get("capacity", "?")
            print(f"    <- {pred}: type={gate_data.get('type','?')}, capacity={cap}")
