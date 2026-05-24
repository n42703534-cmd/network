import copy
import csv
import network as nw

base_loads = {
    'L2': {'platform_waiting': 236, 'hall_people': 350, 'transfer_people': 526},
    'L7': {'platform_waiting': 219, 'hall_people': 112, 'transfer_people': 169},
    'L16': {'platform_waiting': 42, 'hall_people': 15, 'transfer_people': 27},
    'L18': {'platform_waiting': 178, 'hall_people': 125, 'transfer_people': 188},
    'Maglev': {'platform_waiting': 0, 'hall_people': 0, 'transfer_people': 0},
}
critical = 'Escalator_L2_up1'
rows = []
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
    dis = nw.run_simulation_for_metrics(Gd, pop, method='Improved')

    row = {
        'mode': mode,
        'total_people': total,
        'trad_time': trad['time'], 'trad_queue': trad['queueing_time'], 'trad_cong': trad['congestion_exposure_time'],
        'imp_time': imp['time'], 'imp_queue': imp['queueing_time'], 'imp_cong': imp['congestion_exposure_time'],
        'dis_time': dis['time'], 'dis_queue': dis['queueing_time'], 'dis_cong': dis['congestion_exposure_time'],
        'imp_speed': imp['avg_speed'], 'dis_speed': dis['avg_speed'],
    }
    for line in nw.ALL_LINE_IDS:
        row[f'trad_clear_{line}'] = trad['clearance_times_by_line'].get(line)
        row[f'imp_clear_{line}'] = imp['clearance_times_by_line'].get(line)
        row[f'dis_clear_{line}'] = dis['clearance_times_by_line'].get(line)
        row[f'imp_q_{line}'] = imp['queueing_time_by_line'].get(line)
        row[f'dis_q_{line}'] = dis['queueing_time_by_line'].get(line)
        row[f'imp_c_{line}'] = imp['congestion_exposure_by_line'].get(line)
        row[f'dis_c_{line}'] = dis['congestion_exposure_by_line'].get(line)
    rows.append(row)

with open('mode_summary.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

print('WROTE mode_summary.csv')
for row in rows:
    print(row['mode'], row['total_people'], row['trad_time'], row['imp_time'], row['dis_time'])
