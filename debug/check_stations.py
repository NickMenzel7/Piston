import json
import sys
from pprint import pprint

PLAN = 'plan.json'

try:
    with open(PLAN, 'r') as f:
        plan = json.load(f)
except FileNotFoundError:
    print(f"Plan file '{PLAN}' not found in repo root.\nPlease create '{PLAN}' (copy plan_template.json) or run this script with plan data embedded.")
    sys.exit(2)

tests_info = plan.get('tests_info')
st_map = plan.get('st_map')
n_units = plan.get('n_units', 10)

if tests_info is None or st_map is None:
    print("plan.json must contain 'tests_info' and 'st_map' keys.\nSee plan_template.json for format.")
    sys.exit(2)

stations_in_tests = sorted({info.get('station') for info in tests_info.values() if info.get('station')})
print('Detected stations used by tests (stations_in_tests):')
for s in stations_in_tests:
    print(' -', repr(s))

print('\nStation map keys (st_map):')
for k in sorted(st_map.keys()):
    print(' -', repr(k))

print(f'\nChecking counts against n_units={n_units}:')
for s in stations_in_tests:
    sm = st_map.get(s)
    if sm is None:
        print(f"Station {s!r} is used by tests but missing from st_map")
    else:
        try:
            cnt = int(sm.get('count', 0))
        except Exception:
            cnt = 0
        print(f"Station {s!r}: st_map entry={sm}, count={cnt}, count>=n_units? {cnt >= n_units}")

print('\nIf any station is missing or has count < n_units, fix station name or count in plan.json or in your station map input to the scheduler.')
