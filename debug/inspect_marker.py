import json
import re
from piston_core.scheduler import schedule_n_units

with open('plan.json','r',encoding='utf-8') as f:
    plan = json.load(f)

tests_info = plan['tests_info']
topo = plan['topo']
st_map = plan['st_map']

# replicate normalization from scheduler
import re as _re

def _norm(s):
    try:
        return _re.sub(r'[^0-9a-z]','',str(s).strip().casefold())
    except Exception:
        try:
            return _re.sub(r'[^0-9a-z]','',str(s).strip().lower())
        except Exception:
            return ''

# default markers
markers = ["VXG Channel", "Racer Channel"]
markers_norm = set(_norm(m) for m in markers if m and str(m).strip())
markers_norm.add(_norm('ys loading gate'))

print('markers_norm:', markers_norm)

found = []
for tid, info in tests_info.items():
    st = info.get('station','')
    if _norm(st) in markers_norm:
        found.append((tid, st, _norm(st)))

print('marker tests found:', found)

# call schedule_n_units with trace to see branch selection
mk, finishes, util, events = schedule_n_units(tests_info, topo, st_map, 10, channels_per_unit=1, trace=True)
print('makespan:', mk)
print('num events:', len(events))
# print first 20 events
for e in events[:40]:
    print(e)
