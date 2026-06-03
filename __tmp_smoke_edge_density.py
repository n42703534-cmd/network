import network


BASE_LOADS = {
    "L2": {"platform_waiting": 236, "hall_people": 350, "transfer_people": 526},
    "L7": {"platform_waiting": 219, "hall_people": 112, "transfer_people": 169},
    "L16": {"platform_waiting": 42, "hall_people": 15, "transfer_people": 27},
    "L18": {"platform_waiting": 178, "hall_people": 125, "transfer_people": 188},
    "Maglev": {"platform_waiting": 0, "hall_people": 0, "transfer_people": 0},
}


def scaled_mode4(scale):
    pop = {}
    for line, physics in network.TRAIN_PHYSICS.items():
        base = BASE_LOADS[line]
        train_total = int(round(network._train_total_people(physics) * scale))
        pop[line] = {
            "train_1": train_total,
            "train_2": train_total,
            "platform_waiting": int(round(base["platform_waiting"] * scale)),
            "hall_people": int(round(base["hall_people"] * scale)),
            "transfer_people": int(round(base["transfer_people"] * scale)),
        }
    return pop


def main():
    pop = scaled_mode4(0.05)
    total = sum(sum(v.values()) for v in pop.values())
    for method in [network.PAPER_SINGLE_PATH_METHOD, network.OUR_SINGLE_PATH_METHOD]:
        metrics = network.run_simulation_for_metrics_timed(network.build_graph(), pop, method=method)
        print(
            "{} total={} time={} queue={:.1f} cong={:.1f} severe={:.1f} edge_cong={:.1f} edge_severe={:.1f}".format(
                network.METHOD_DISPLAY_NAMES.get(method, method),
                total,
                metrics["time"],
                metrics["queueing_time"],
                metrics["congestion_exposure_time"],
                metrics.get("severe_congestion_exposure_time", 0.0),
                metrics.get("edge_congestion_exposure_time", 0.0),
                metrics.get("edge_severe_congestion_exposure_time", 0.0),
            )
        )


if __name__ == "__main__":
    main()
