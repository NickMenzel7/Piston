#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick test to verify parallel scheduling works with adequate stations."""

import pandas as pd
from piston_core.scheduler import build_dag, schedule_n_units

# Create a simple test plan with 3 sequential tests
tests_data = {
    'TestID': ['T1', 'T2', 'T3'],
    'TestName': ['Test A', 'Test B', 'Test C'],
    'Station': ['Station1', 'Station2', 'Station1'],
    'TestTimeMin': [60, 60, 60],  # 1 hour each
    'DependsOn': ['', 'T1', 'T2'],  # Sequential chain: T1 -> T2 -> T3
}
tests_df = pd.DataFrame(tests_data)

# Build tests_info
def parse_time(val):
    try:
        return float(val)
    except:
        return 0.0

deps, succs, topo = build_dag(tests_df)

# Build tests_info using DAG structure (node IDs are 'r<index>')
tests_info = {}
for idx, row in tests_df.iterrows():
    nid = f"r{idx}"
    tests_info[nid] = {
        'testid': str(row['TestID']),
        'station': row['Station'],
        'time_min': parse_time(row['TestTimeMin']),
        'depends_on': deps.get(nid, []),  # Use DAG dependencies
    }

print("\n=== Test 1: Single unit (should take ~3 hours) ===")
st_map_1 = {
    'Station1': {'count': 1, 'uptime': 1.0},
    'Station2': {'count': 1, 'uptime': 1.0},
}
mk1, finishes1, util1 = schedule_n_units(tests_info, topo, st_map_1, n_units=1)
print(f"Makespan: {mk1:.2f} hours")
print(f"Expected: ~3.0 hours (tests run sequentially)")

print("\n=== Test 2: 10 units, only 2 stations total (should serialize, ~30 hours) ===")
st_map_2 = {
    'Station1': {'count': 1, 'uptime': 1.0},
    'Station2': {'count': 1, 'uptime': 1.0},
}
mk2, finishes2, util2 = schedule_n_units(tests_info, topo, st_map_2, n_units=10)
print(f"Makespan: {mk2:.2f} hours")
print(f"Expected: ~30.0 hours (units must share limited stations)")

print("\n=== Test 3: 10 units, 20 of each station (fully dedicated, should be ~3 hours) ===")
st_map_3 = {
    'Station1': {'count': 20, 'uptime': 1.0},
    'Station2': {'count': 20, 'uptime': 1.0},
}
mk3, finishes3, util3 = schedule_n_units(tests_info, topo, st_map_3, n_units=10)
print(f"Makespan: {mk3:.2f} hours")
print(f"Expected: ~3.0 hours (each unit has dedicated stations, runs in parallel)")
print(f"Status: {'✓ PASS' if mk3 < 4.0 else '✗ FAIL - units are still being serialized!'}")

print("\n=== Summary ===")
if mk3 < 4.0:
    print("SUCCESS: Parallel execution works correctly with adequate stations!")
else:
    print(f"PROBLEM: With fully dedicated stations, makespan is {mk3:.2f}h instead of ~3h")
    print("This indicates units are still being unnecessarily serialized.")
