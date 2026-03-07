"""Quick debug helper: load a plan.json, force all station counts to a chosen value,
run schedule_n_units (trace=True) and print a concise summary and first assignment events.

Usage: python debug_dedicated.py [plan.json] [n_units]
"""
import json
import sys
from piston_core.scheduler import schedule_n_units, critical_path_hours

PLAN = sys.argv[1] if len(sys.argv) > 1 else 'plan.json'
N_UNITS = int(sys.argv[2]) if len(sys.argv) > 2 else 10

with open(PLAN, 'r', encoding='utf-8') as f:
    plan = json.load(f)

tests_info = plan['tests_info']
topo = plan.get('topo')
st_map = plan.get('st_map', {})

# Force all referenced stations to have count = N_UNITS
for k in list(st_map.keys()):
    try:
        st_map[k]['count'] = N_UNITS
    except Exception:
        st_map[k] = {'count': N_UNITS, 'uptime': 1.0}

print(f"Running with all station counts = {N_UNITS}")
cp = critical_path_hours(tests_info, topo, st_map)
print(f"Critical path per-unit (hrs): {cp:.6f}")

mk, finishes, util, events = schedule_n_units(tests_info, topo, st_map, N_UNITS, channels_per_unit=1, unit_bias=None, trace=True)
print(f"Makespan (hrs): {mk}")
print(f"Per-unit finishes (first 10): {finishes[:10]}")
print("Station utilizations (sample):")
for s, v in list(util.items())[:10]:
    print(f"  {s}: {v:.6f}")

print('\nFirst 40 assignment events:')
c = 0
for e in events:
    if e.get('event') == 'assign':
        print(e)
        c += 1
        if c >= 40:
            break
