from piston_core.io import load_model
import json

MODEL_PATH = 'embedded/default_model.xlsx'
OUT_PLAN = 'plan.json'

stations_df, tests_df, st_map, station_map, plan_schema, non_test = load_model(MODEL_PATH)

# Build tests_info mapping
tests_info = {}
topo = []
for idx, row in tests_df.iterrows():
    tid = str(row.get('TestID') or f'r{idx}').strip()
    topo.append(tid)
    depends_raw = str(row.get('DependsOn') or '').strip()
    depends = [d.strip() for d in depends_raw.split(',') if d and d.strip() and d.strip().lower() not in ('nan','none')]
    station = str(row.get('Station') or '').strip()
    time_min = float(row.get('TestTimeMin') or 0.0)
    tests_info[tid] = {'depends_on': depends, 'station': station, 'time_min': time_min, 'testid': tid}

plan = {
    'n_units': 10,
    'channels_per_unit': 1,
    'tests_info': tests_info,
    'topo': topo,
    'st_map': st_map,
    'biases': {'weak': 0.01, 'strong': 0.05}
}

with open(OUT_PLAN, 'w') as f:
    json.dump(plan, f, indent=2)

print(f'Wrote {OUT_PLAN} with {len(tests_info)} tests and {len(st_map)} stations')
