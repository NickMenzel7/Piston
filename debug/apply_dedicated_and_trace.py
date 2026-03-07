"""Set all station counts referenced by the plan to the requested n_units,
run schedule_n_units(trace=True) and write a JSON trace output.
Usage: python apply_dedicated_and_trace.py [plan.json] [n_units]
"""
import json
import sys
from piston_core.scheduler import schedule_n_units, critical_path_hours

plan_file = sys.argv[1] if len(sys.argv) > 1 else 'plan.json'
n_units = int(sys.argv[2]) if len(sys.argv) > 2 else 10

with open(plan_file, 'r', encoding='utf-8') as f:
    plan = json.load(f)

tests_info = plan.get('tests_info', {})
topo = plan.get('topo')
st_map = plan.get('st_map', {})

# Set all referenced station counts to n_units
for k in list(st_map.keys()):
    try:
        st_map[k]['count'] = n_units
    except Exception:
        st_map[k] = {'count': n_units, 'uptime': 1.0}

# Also ensure any station names referenced in tests but missing in st_map are added
refs = set()
for tid, info in tests_info.items():
    st = info.get('station')
    if st and str(st).strip():
        refs.add(st)

# simple normalization key: casefolded strip
for r in refs:
    found = False
    for k in list(st_map.keys()):
        if str(k).strip().casefold() == str(r).strip().casefold():
            found = True
            break
    if not found:
        st_map[r] = {'count': n_units, 'uptime': 1.0}

# run schedule traced
mk, finishes, util, events = schedule_n_units(tests_info, topo, st_map, n_units, channels_per_unit=1, unit_bias=None, trace=True)

out = {
    'makespan': mk,
    'finishes': finishes,
    'util': util,
    'events_sample': events[:200]
}
with open('trace_dedicated.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2)

print('Wrote trace_dedicated.json')
print('makespan:', mk)
print('first 10 finishes:', finishes[:10])
print('num events written:', len(events))
