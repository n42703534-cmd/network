import network


def main():
    G = network.build_graph()
    exit_edges = []
    for u, v, data in G.edges(data=True):
        if G.nodes[v].get("type") == "exit":
            exit_edges.append((u, v, float(data.get("capacity", 0.0)), float(data.get("length", 0.0)), data.get("edge_type", "")))

    print("exit_edges")
    for row in sorted(exit_edges, key=lambda x: x[2], reverse=True):
        print("{} -> {} cap={:.3f}p/s len={:.1f} type={}".format(*row))
    print("total_exit_edge_capacity={:.3f}p/s".format(sum(row[2] for row in exit_edges)))

    service_nodes = []
    for node, data in G.nodes(data=True):
        if data.get("type") in {"stair", "escalator"} or "gate" in str(data.get("type", "")).lower():
            out_cap = sum(float(G[node][succ].get("capacity", 0.0)) for succ in G.successors(node))
            in_cap = sum(float(G[pred][node].get("capacity", 0.0)) for pred in G.predecessors(node))
            service_nodes.append((node, data.get("type"), float(data.get("capacity", 0.0)), in_cap, out_cap))

    print("top_service_by_capacity")
    for node, typ, cap, in_cap, out_cap in sorted(service_nodes, key=lambda x: x[2], reverse=True)[:40]:
        print("{} type={} node_cap={:.3f} in_sum={:.3f} out_sum={:.3f}".format(node, typ, cap, in_cap, out_cap))


if __name__ == "__main__":
    main()
