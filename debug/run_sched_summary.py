import json
from piston_core.scheduler import schedule_n_units, critical_path_hours

with open('plan.json','r',encoding='utf-8') as f:
    plan = json.load(f)

n = 10
st_map = plan.get('st_map',{})
for k in list(st_map.keys()):
    st_map[k]['count'] = n

tests_info = plan['tests_info']
topo = plan.get('topo')

cp = critical_path_hours(tests_info, topo, st_map)
print('critical_path_hours:', cp)
mk, finishes, util = schedule_n_units(tests_info, topo, st_map, n, channels_per_unit=1, unit_bias=None, trace=False)
print('makespan:', mk)
print('first 10 finishes:', finishes[:10])
print('num finishes:', len(finishes))
