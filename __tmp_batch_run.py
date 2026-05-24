import copy, json
import network as nw

base_loads = {
    'L2': {'platform_waiting': 236, 'hall_people': 350, 'transfer_people': 526},
    'L7': {'platform_waiting': 219, 'hall_people': 112, 'transfer_people': 169},
    'L16': {'platform_waiting': 42, 'hall_people': 15, 'transfer_people': 27},
    'L18': {'platform_waiting': 178, 'hall_people': 125, 'transfer_people': 188},
    'Maglev': {'platform_waiting': 0, 'hall_people': 0, 'transfer_people': 0},
}
critical = 'Escalator_L2_up1'
results = {}
for mode in [1,2,3,4]:
    G = nw.build_graph()
    pop = {}
    total = 0
    for line, physics in nw.TRAIN_PHYSICS.items():
        base = base_loads[line]
        train_total = int(round(nw._train_total_people(physics)))
        if mode == 1:
            t1, t2 = 0, 0
        elif mode == 2:
            t1, t2 = train_total, 0
        elif mode == 3:
            t1, t2 = 0, train_total
        else:
            t1, t2 = train_total, train_total
        pop[line] = {
            'train_1': t1,
            'train_2': t2,
            'platform_waiting': base['platform_waiting'],
            'hall_people': base['hall_people'],
            'transfer_people': base['transfer_people'],
        }
        total += t1 + t2 + base['platform_waiting'] + base['hall_people'] + base['transfer_people']

    trad = nw.run_simulation_for_metrics(G, pop, method='Traditional')
    imp = nw.run_simulation_for_metrics(G, pop, method='Improved')

    Gd = copy.deepcopy(G)
    nw._apply_node_disruption(Gd, critical, factor=0.0)
    imp_dis = nw.run_simulation_for_metrics(Gd, pop, method='Improved')

    results[mode] = {
        'total_people': total,
        'traditional': {
            'time': trad['time'],
            'queue': trad['queueing_time'],
            'cong': trad['congestion_exposure_time'],
            'avg_speed': trad['avg_speed'],
        },
        'improved': {
            'time': imp['time'],
            'queue': imp['queueing_time'],
            'cong': imp['congestion_exposure_time'],
            'avg_speed': imp['avg_speed'],
        },
        'disrupted': {
            'time': imp_dis['time'],
            'queue': imp_dis['queueing_time'],
            'cong': imp_dis['congestion_exposure_time'],
            'avg_speed': imp_dis['avg_speed'],
        }
    }

print(json.dumps(results, ensure_ascii=False, indent=2))
