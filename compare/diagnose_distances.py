"""
Diagnose: compute shortest-path distances from key platform nodes to exits,
compare against Pathfinder's actual exit usage to find distance anomalies.
"""
from __future__ import annotations
import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
vendored = ROOT / "__vendor_site_packages"
if vendored.exists():
    sys.path.insert(0, str(vendored))

# No-op matplotlib if missing
if importlib.util.find_spec("matplotlib") is None:
    mpl = types.ModuleType("matplotlib")
    pyplot = types.ModuleType("matplotlib.pyplot")
    patches = types.ModuleType("matplotlib.patches")
    def _nop(*a, **kw): return None
    pyplot.figure = _nop
    pyplot.subplots = lambda *a, **kw: (None, None)
    pyplot.plot = pyplot.bar = pyplot.savefig = pyplot.close = _nop
    pyplot.tight_layout = pyplot.grid = pyplot.xlabel = pyplot.ylabel = _nop
    pyplot.title = pyplot.legend = pyplot.suptitle = _nop
    pyplot.rcParams = {}
    patches.Patch = object
    mpl.pyplot = pyplot
    mpl.patches = patches
    sys.modules["matplotlib"] = mpl
    sys.modules["matplotlib.pyplot"] = pyplot
    sys.modules["matplotlib.patches"] = patches

import network
import networkx as nx

# Pathfinder Mode 1 exit usage (ground truth)
PF_EXIT_USAGE = {
    "Exit_L18_12": 382,
    "Exit_L18_13": 44,
    "Exit_L18_17": 26,
    "Exit_L7_7": 394,
    "Exit_L7_8/9": 136,
    "Exit_L2_6": 111,
    "Exit_L2_2": 216,
    "Exit_L2_3": 365,
    "Exit_L2_4": 105,
    "Exit_L16_10": 53,
    "Exit_L16_11": 354,
}

TOTAL = 2187


def main():
    graph = network.build_graph()
    exits = [n for n, d in graph.nodes(data=True) if d.get("type") == "exit"]

    # Find all platform and platform_waiting_zone nodes
    platform_nodes = []
    for n, d in graph.nodes(data=True):
        t = d.get("type", "")
        if "platform" in t:
            platform_nodes.append(n)

    # Also include hall staging nodes and transfer arrival nodes
    key_origins = platform_nodes + [
        n for n, d in graph.nodes(data=True)
        if d.get("type") in ("virtual", "hall_staging")
        and any(kw in n.lower() for kw in ["hall_arrival", "hall_staging", "corner"])
    ]

    # For each exit, find nearest platform node and distance
    print("=" * 90)
    print("SHORTEST PATH DISTANCES: Platform nodes → Each Exit (our graph)")
    print("=" * 90)

    # Pre-compute all shortest path lengths
    all_dists = dict(nx.all_pairs_dijkstra_path_length(graph, weight="length"))

    for exit_name in sorted(exits):
        pf_usage = PF_EXIT_USAGE.get(exit_name, 0)
        pf_share = pf_usage / TOTAL * 100

        # Find closest platform nodes
        node_dists = []
        for node in platform_nodes:
            if node in all_dists and exit_name in all_dists[node]:
                d = all_dists[node][exit_name]
            elif exit_name in all_dists and node in all_dists[exit_name]:
                d = all_dists[exit_name][node]
            else:
                continue
            node_dists.append((node, d))

        node_dists.sort(key=lambda x: x[1])

        print(f"\n{'─' * 80}")
        print(f"  {exit_name}  |  Pathfinder usage: {pf_usage}人 ({pf_share:.1f}%)")
        print(f"{'─' * 80}")
        print(f"  {'Origin node':<50s} {'Distance (m)':>12s}")
        print(f"  {'─' * 50} {'─' * 12}")
        for node, dist in node_dists[:8]:
            node_type = graph.nodes[node].get("type", "")
            print(f"  {node:<50s} {dist:>10.1f}m  [{node_type}]")

    # Now for L2 specifically: find which exit is closest for each L2 origin
    print(f"\n\n{'=' * 90}")
    print("L2 ORIGINS → NEAREST EXIT (by our graph distance)")
    print("=" * 90)

    l2_origins = [n for n in platform_nodes if "L2" in n or "Line2" in n]
    l2_exits = [e for e in exits if "L2" in e]

    for origin in sorted(l2_origins):
        dists = []
        for e in l2_exits:
            if origin in all_dists and e in all_dists[origin]:
                dists.append((e, all_dists[origin][e]))
            elif e in all_dists and origin in all_dists[e]:
                dists.append((e, all_dists[e][origin]))
        dists.sort(key=lambda x: x[1])
        if dists:
            nearest = dists[0]
            print(f"\n  {origin}")
            print(f"  {'─' * 50}")
            for e, d in dists:
                marker = " ← NEAREST" if (e, d) == (nearest[0], nearest[1]) else ""
                pf_u = PF_EXIT_USAGE.get(e, 0)
                print(f"    {e:<25s} {d:>8.1f}m  (PF: {pf_u}人){marker}")

    # L18 origins
    print(f"\n\n{'=' * 90}")
    print("L18 ORIGINS → NEAREST EXIT (by our graph distance)")
    print("=" * 90)

    l18_origins = [n for n in platform_nodes if "L18" in n or "Line18" in n]
    l18_exits = [e for e in exits if "L18" in e]

    for origin in sorted(l18_origins):
        dists = []
        for e in l18_exits:
            if origin in all_dists and e in all_dists[origin]:
                dists.append((e, all_dists[origin][e]))
            elif e in all_dists and origin in all_dists[e]:
                dists.append((e, all_dists[e][origin]))
        dists.sort(key=lambda x: x[1])
        if dists:
            nearest = dists[0]
            print(f"\n  {origin}")
            print(f"  {'─' * 50}")
            for e, d in dists:
                marker = " ← NEAREST" if (e, d) == (nearest[0], nearest[1]) else ""
                pf_u = PF_EXIT_USAGE.get(e, 0)
                print(f"    {e:<25s} {d:>8.1f}m  (PF: {pf_u}人){marker}")

    # L16 origins
    print(f"\n\n{'=' * 90}")
    print("L16 ORIGINS → NEAREST EXIT (by our graph distance)")
    print("=" * 90)

    l16_origins = [n for n in platform_nodes if "L16" in n or "Line16" in n]
    l16_exits = [e for e in exits if "L16" in e]

    for origin in sorted(l16_origins):
        dists = []
        for e in l16_exits:
            if origin in all_dists and e in all_dists[origin]:
                dists.append((e, all_dists[origin][e]))
            elif e in all_dists and origin in all_dists[e]:
                dists.append((e, all_dists[e][origin]))
        dists.sort(key=lambda x: x[1])
        if dists:
            nearest = dists[0]
            print(f"\n  {origin}")
            print(f"  {'─' * 50}")
            for e, d in dists:
                marker = " ← NEAREST" if (e, d) == (nearest[0], nearest[1]) else ""
                pf_u = PF_EXIT_USAGE.get(e, 0)
                print(f"    {e:<25s} {d:>8.1f}m  (PF: {pf_u}人){marker}")

    # Key finding: compute how many platform nodes have each exit as nearest
    print(f"\n\n{'=' * 90}")
    print("EXIT COVERAGE: How many platform/waiting/hall nodes have each exit as nearest")
    print("=" * 90)

    exit_counts = {e: 0 for e in exits}
    for origin in platform_nodes + [
        n for n, d in graph.nodes(data=True)
        if d.get("type") in ("hall_staging",)
    ]:
        best_exit = None
        best_dist = float("inf")
        for e in exits:
            if origin in all_dists and e in all_dists[origin]:
                d = all_dists[origin][e]
            elif e in all_dists and origin in all_dists[e]:
                d = all_dists[e][origin]
            else:
                continue
            if d < best_dist:
                best_dist = d
                best_exit = e
        if best_exit:
            exit_counts[best_exit] += 1

    for e in sorted(exits):
        pf_u = PF_EXIT_USAGE.get(e, 0)
        print(f"  {e:<25s}  nearest for {exit_counts[e]:>3d} origins  |  PF usage: {pf_u:>4d}人 ({pf_u/TOTAL*100:.1f}%)")


if __name__ == "__main__":
    main()
