"""
Trace exact shortest path from L18 C5/C6 to Exit_L18_12 and Exit_L18_17,
showing every edge and how its distance is computed.
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

if importlib.util.find_spec("matplotlib") is None:
    mpl = types.ModuleType("matplotlib")
    pyplot = types.ModuleType("matplotlib.pyplot")
    patches = types.ModuleType("matplotlib.patches")
    def _nop(*a, **kw): return None
    pyplot.figure = pyplot.subplots = _nop
    pyplot.plot = pyplot.bar = pyplot.savefig = pyplot.close = _nop
    pyplot.tight_layout = pyplot.grid = pyplot.xlabel = pyplot.ylabel = _nop
    pyplot.title = pyplot.legend = pyplot.suptitle = _nop
    pyplot.rcParams = {}
    patches.Patch = object
    mpl.pyplot = pyplot; mpl.patches = patches
    sys.modules["matplotlib"] = mpl
    sys.modules["matplotlib.pyplot"] = pyplot
    sys.modules["matplotlib.patches"] = patches

import network
import networkx as nx

def trace_path(G, origin, target):
    """Trace the shortest path and show each edge's distance computation."""
    try:
        path = nx.dijkstra_path(G, origin, target, weight="length")
    except nx.NetworkXNoPath:
        print(f"  NO PATH from {origin} to {target}")
        return

    total = 0.0
    print(f"\n  Path: {' → '.join(path)}")
    print(f"  {'─'*70}")
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        edge = G[u][v]
        length = float(edge.get("length", 0))
        edge_type = edge.get("edge_type", "?")
        width_limit = edge.get("width_limit")
        cap = edge.get("capacity", 0)

        # Get node positions
        pos_u = G.nodes[u].get("pos", (0,0))
        pos_v = G.nodes[v].get("pos", (0,0))

        # Recompute CAD distance for comparison
        if pos_u and pos_v and pos_u != (0,0) and pos_v != (0,0):
            cad_dist = ((pos_u[0]-pos_v[0])**2 + (pos_u[1]-pos_v[1])**2)**0.5 * 0.01
        else:
            cad_dist = None

        total += length
        wl_str = f"wlim={width_limit}" if width_limit else ""
        cad_str = f"CAD={cad_dist:.1f}m" if cad_dist else ""
        print(f"  {u:>45s} → {v:<45s}  len={length:>7.2f}m  [{edge_type}] {wl_str} {cad_str}")

    print(f"  {'─'*70}")
    print(f"  TOTAL: {total:.1f}m")


def main():
    G = network.build_graph()

    origins = ["Platform_L18_C5_Wait", "Platform_L18_C6_Wait",
               "Platform_L18_C4_Wait", "Platform_L18_C1_Wait"]
    targets = ["Exit_L18_12", "Exit_L18_17"]

    for origin in origins:
        for target in targets:
            node = G.nodes.get(origin)
            t = G.nodes.get(target)
            if not node or not t:
                continue
            print(f"\n{'='*80}")
            print(f"{origin} → {target}")
            if node.get("pos"):
                print(f"  Origin pos: {node['pos']}")
            if t.get("pos"):
                print(f"  Target pos: {t['pos']}")
            trace_path(G, origin, target)

    # Also show exit internal edge distances for comparison
    print(f"\n\n{'='*80}")
    print("L18 EXIT INTERNAL EDGES (gate → entrance → stair/escalator → exit)")
    print("=" * 80)
    for u, v, data in G.edges(data=True):
        if "Exit_L18_12" in str(u) or "Exit_L18_12" in str(v) or \
           "Exit_L18_17" in str(u) or "Exit_L18_17" in str(v):
            pos_u = G.nodes[u].get("pos", (0,0))
            pos_v = G.nodes[v].get("pos", (0,0))
            cad_dist = None
            if pos_u and pos_v and pos_u != (0,0) and pos_v != (0,0):
                cad_dist = ((pos_u[0]-pos_v[0])**2 + (pos_u[1]-pos_v[1])**2)**0.5 * 0.01
            print(f"  {u:>45s} → {v:<45s}  len={data.get('length',0):>7.2f}m  [{data.get('edge_type','?')}] wlim={data.get('width_limit')} CAD={cad_dist}")


if __name__ == "__main__":
    main()
