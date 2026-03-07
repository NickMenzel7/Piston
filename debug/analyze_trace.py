import json
from collections import defaultdict

with open('trace_dedicated.json','r',encoding='utf-8') as f:
    data = json.load(f)

mk = data.get('makespan')
finishes = data.get('finishes', [])
events = data.get('events_sample') or []

# if events_sample is partial, try to load full events if present
try:
    # maybe trace file contained 'events' full list; try that
    if 'events' in data:
        events = data['events']
except Exception:
    pass

station_busy = defaultdict(float)
unit_last = defaultdict(float)
unit_events = defaultdict(list)

for e in events:
    if e.get('event') == 'assign':
        st = e.get('station')
        dur = e.get('dur') or 0.0
        # some station keys are normalized or may be None
        station_busy[st] += dur
        unit = e.get('unit')
        finish = e.get('finish') or 0.0
        try:
            if unit is not None:
                unit_last[unit] = max(unit_last.get(unit, 0.0), finish)
                unit_events[unit].append(e)
        except Exception:
            pass

print(f"makespan: {mk}")
print("first 10 finishes:", finishes[:10])

print('\nTop stations by busy hours (from events_sample):')
for s, b in sorted(station_busy.items(), key=lambda x: -x[1])[:20]:
    print(f"  {s}: {b:.3f} hrs")

print('\nPer-unit last finish times (sample up to 10):')
for u, t in sorted(unit_last.items(), key=lambda x: x[0])[:20]:
    print(f"  unit {u}: {t:.3f} hrs")

# Show last few assign events for unit 0..3 if present
for u in range(4):
    evs = unit_events.get(u, [])
    if not evs:
        continue
    print(f"\nLast events for unit {u} (up to 10):")
    for e in sorted(evs, key=lambda x: x.get('finish',0.0))[-10:]:
        print(e)

# If events_sample was partial, warn
if len(events) < 1000:
    print('\nNote: events_sample may be truncated; run a full traced schedule to get complete events list.')
