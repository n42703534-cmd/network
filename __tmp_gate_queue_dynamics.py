"""Monitor gate queue dynamics: does Gate_L2_N_West queue ever build up enough
to make L2_3 cheaper than L2_2 for VN_L7toL2_Hall_Arrival?"""
import sys, importlib.util, types, math

def _noop_mpl():
    if importlib.util.find_spec("matplotlib"): return
    m=types.ModuleType("matplotlib"); p=types.ModuleType("matplotlib.pyplot"); pt=types.ModuleType("matplotlib.patches")
    def _n(*a,**kw): return None
    p.figure=_n; p.subplots=lambda *a,**kw:(None,None); p.plot=_n; p.bar=_n; p.savefig=_n; p.close=_n
    p.tight_layout=_n; p.grid=_n; p.xlabel=_n; p.ylabel=_n; p.title=_n; p.legend=_n; p.suptitle=_n
    p.rcParams={}; pt.Patch=object; m.pyplot=p; m.patches=pt
    sys.modules["matplotlib"]=m; sys.modules["matplotlib.pyplot"]=p; sys.modules["matplotlib.patches"]=pt
_noop_mpl()
sys.path.insert(0,".")

import network
import single_path_routing as spr
import networkx as nx

BASE_LOADS = {
    "L2": {"platform_waiting": 236, "hall_people": 350, "transfer_people": 526},
    "L7": {"platform_waiting": 219, "hall_people": 112, "transfer_people": 169},
    "L16": {"platform_waiting": 42, "hall_people": 15, "transfer_people": 27},
    "L18": {"platform_waiting": 178, "hall_people": 125, "transfer_people": 188},
    "Maglev": {"platform_waiting": 0, "hall_people": 0, "transfer_people": 0},
}

# Build empty graph first to analyze costs
pop_empty = {}
for line in network.TRAIN_PHYSICS:
    pop_empty[line] = {"train_1": 0, "train_2": 0, "platform_waiting": 0, "hall_people": 0, "transfer_people": 0}

G_empty = network.build_graph()

# Compute gate capacities
print("=" * 80)
print("GATE CAPACITIES (people/second)")
print("=" * 80)
for gate_name in ["Gate_L2_N_West", "Gate_L2_N_East", "Gate_L2_S_West", "Gate_L2_S_East"]:
    if gate_name in G_empty.nodes:
        nd = G_empty.nodes[gate_name]
        cap = nd.get("capacity", "?")
        lanes = nd.get("width", "?")
        print(f"  {gate_name}: lanes={lanes}, capacity={cap:.3f} p/s, "
              f"(= {cap*3600:.0f} p/h)")

# Compute costs from VN_L7toL2_Hall_Arrival to L2 exits at various gate queue levels
SRC = "VN_L7toL2_Hall_Arrival"
GATE_NW = "Gate_L2_N_West"
GATE_SE = "Gate_L2_S_East"

print(f"\n{'='*80}")
print(f"COST vs QUEUE AT Gate_L2_N_West (from {SRC})")
print(f"{'='*80}")

# Get base path costs
def compute_total_cost_to_exit(G, src, exit_name, extra_queue_at_gate=0):
    """Compute our path cost with optional extra queue at a gate."""
    # Save original people values
    saved = {}
    for node in G.nodes:
        saved[node] = G.nodes[node].get("people", 0)

    # Add extra queue at Gate_L2_N_West
    if extra_queue_at_gate > 0 and GATE_NW in G.nodes:
        G.nodes[GATE_NW]["people"] = float(G.nodes[GATE_NW].get("people", 0)) + extra_queue_at_gate

    try:
        comps = spr.our_path_cost_components(G, nx.dijkstra_path(G, src, exit_name, weight="length"),
                                              lambda d: spr.PAPER_FREE_SPEED, spr.OUR_SINGLE_PATH_METHOD)
        result = comps["total_cost"]
    except:
        result = float("inf")

    # Restore
    for node in G.nodes:
        G.nodes[node]["people"] = saved[node]

    return result

L2_EXITS = ["Exit_L2_2", "Exit_L2_3", "Exit_L2_4", "Exit_L2_6"]

# Clear reserved inflow
for n in G_empty.nodes:
    G_empty.nodes[n]["_guidance_reserved_inflow"] = 0.0

print(f"\n  {'Queue@NW':>8s}", end="")
for ex in L2_EXITS:
    print(f"  {ex:>14s}", end="")
print()

for q in [0, 10, 20, 30, 40, 50, 60, 70, 75, 80, 90, 100]:
    print(f"  {q:8d}", end="")
    for ex in L2_EXITS:
        cost = compute_total_cost_to_exit(G_empty, SRC, ex, extra_queue_at_gate=q)
        marker = " *" if ex == "Exit_L2_3" and q > 0 and cost < compute_total_cost_to_exit(G_empty, SRC, "Exit_L2_2", extra_queue_at_gate=q) else ""
        print(f"  {cost:14.2f}{marker}", end="")
    print()

# Also check: what queue at N_West makes L2_3 cost <= L2_2 cost?
print(f"\nFinding breakeven point...")
prev_l2_2 = compute_total_cost_to_exit(G_empty, SRC, "Exit_L2_2")
prev_l2_3 = compute_total_cost_to_exit(G_empty, SRC, "Exit_L2_3")
for q in range(0, 200):
    cost_l2_2 = compute_total_cost_to_exit(G_empty, SRC, "Exit_L2_2", extra_queue_at_gate=q)
    cost_l2_3 = compute_total_cost_to_exit(G_empty, SRC, "Exit_L2_3")
    if cost_l2_3 <= cost_l2_2:
        print(f"  L2_3 <= L2_2 at queue={q}: L2_2={cost_l2_2:.2f}  L2_3={cost_l2_3:.2f}")
        break

# Now check inertia parameters
print(f"\n{'='*80}")
print(f"INERTIA PARAMETERS")
print(f"{'='*80}")
print(f"  OUR_GUIDANCE_MIN_HOLD_SECONDS={getattr(network, 'OUR_GUIDANCE_MIN_HOLD_SECONDS', '?')}")
print(f"  OUR_GUIDANCE_SWITCH_MARGIN={getattr(network, 'OUR_GUIDANCE_SWITCH_MARGIN', '?')}")
print(f"  OUR_GUIDANCE_FORCE_SWITCH_MARGIN={getattr(network, 'OUR_GUIDANCE_FORCE_SWITCH_MARGIN', '?')}")
print(f"  DT={getattr(network, 'DT', getattr(network, 'SIM_DT', '?'))}")

# Check gate capacity and queue ratio thresholds
mu_nw = network.calculate_gb_capacity_per_second("gate_wide", 4)
mu_se = network.calculate_gb_capacity_per_second("gate_wide", 5)
service_window = spr.SERVICE_QUEUE_HORIZON_SECONDS

print(f"\n{'='*80}")
print(f"QUEUE THRESHOLD ANALYSIS")
print(f"{'='*80}")
print(f"  Gate_L2_N_West mu={mu_nw:.3f} p/s  service_window={service_window}s  window_capacity={mu_nw*service_window:.1f}")
print(f"  Gate_L2_S_East mu={mu_se:.3f} p/s")
print(f"  Queue_ratio=1.0 requires {mu_nw*service_window:.0f} people at Gate_L2_N_West")
print(f"  Breakeven requires ~{int(32.5/0.438)} people assuming linear penalty region")

# Also check: what's the maximum possible queue at Gate_L2_N_West?
# Edge from VN_L7toL2_Hall_Arrival to Gate_L2_N_West has width=7.0
edge_cap = network.calculate_gb_capacity_per_second("passageway", 7.0)
print(f"\n  Edge VN_L7toL2 -> Gate_L2_N_West capacity: {edge_cap:.3f} p/s")
print(f"  Gate processing rate: {mu_nw:.3f} p/s")
print(f"  Max queue buildup rate: {edge_cap - mu_nw:.3f} p/s (upstream - processing)")

# Now run simulation with gate queue tracking
print(f"\n{'='*80}")
print(f"RUNNING SIMULATION WITH GATE QUEUE TRACKING")
print(f"{'='*80}")

# Monkey-patch to track gate queue
original_execute = network.execute_moves
gate_queue_log = []

def tracking_execute(G, moves, evacuated_by_line=None, exit_usage_dict=None):
    t = G.graph.get("sim_time", 0)
    for gate_name in ["Gate_L2_N_West", "Gate_L2_S_East"]:
        if gate_name in G.nodes:
            ppl = G.nodes[gate_name].get("people", 0)
            res = G.nodes[gate_name].get("_guidance_reserved_inflow", 0)
            gate_queue_log.append((t, gate_name, ppl, res))
    return original_execute(G, moves, evacuated_by_line, exit_usage_dict)

network.execute_moves = tracking_execute

# Build population
pop = {}
for line, physics in network.TRAIN_PHYSICS.items():
    base = BASE_LOADS[line]
    pop[line] = {
        "train_1": 0, "train_2": 0,
        "platform_waiting": int(base["platform_waiting"]),
        "hall_people": int(base["hall_people"]),
        "transfer_people": int(base["transfer_people"]),
    }

graph = network.build_graph()
metrics = network.run_simulation_for_metrics_timed(graph, pop, method=network.OUR_SINGLE_PATH_METHOD)

# Restore original
network.execute_moves = original_execute

# Analyze gate queue log
print(f"\nGate_L2_N_West queue stats over {len([x for x in gate_queue_log if x[1]=='Gate_L2_N_West'])} steps:")
nw_log = [(t, ppl, res) for t, name, ppl, res in gate_queue_log if name == "Gate_L2_N_West"]
se_log = [(t, ppl, res) for t, name, ppl, res in gate_queue_log if name == "Gate_L2_S_East"]

if nw_log:
    ppls = [p for _, p, _ in nw_log]
    ress = [r for _, _, r in nw_log]
    print(f"  Max people at gate: {max(ppls):.1f}")
    print(f"  Mean people at gate: {sum(ppls)/len(ppls):.2f}")
    print(f"  Max reserved inflow: {max(ress):.1f}")
    print(f"  Peak people+reserved: {max(p+r for _,p,r in nw_log):.1f}")
    # Show peak moments
    peak_idx = ppls.index(max(ppls))
    peak_t = nw_log[peak_idx][0]
    print(f"  Peak at t={peak_t:.1f}s")
    # Show first few high-queue moments
    print(f"\n  Top 10 queue moments at Gate_L2_N_West:")
    sorted_nw = sorted(nw_log, key=lambda x: -x[1])[:10]
    for t, ppl, res in sorted_nw:
        print(f"    t={t:6.1f}s  people={ppl:6.1f}  reserved={res:6.1f}  total={ppl+res:6.1f}")

if se_log:
    ppls_se = [p for _, p, _ in se_log]
    print(f"\nGate_L2_S_East queue stats:")
    print(f"  Max people at gate: {max(ppls_se):.1f}")
    print(f"  Mean people at gate: {sum(ppls_se)/len(ppls_se):.2f}")

# Final exit distribution
exit_usage = metrics.get("exit_usage", {})
print(f"\nFinal exit distribution (L2 only):")
for ex in ["Exit_L2_2", "Exit_L2_3", "Exit_L2_4", "Exit_L2_6"]:
    print(f"  {ex}: {exit_usage.get(ex, 0):.0f}")
