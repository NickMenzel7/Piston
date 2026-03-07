#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test with a more realistic scenario similar to VXG 54GHz."""

import pandas as pd
from piston_core.scheduler import build_dag, schedule_n_units
from piston_ui.validation_helper import build_tests_info

def parse_time(val):
    try:
        return float(val)
    except:
        return 0.0

# Create a more realistic test plan with multiple stations and longer durations
# Simulating approximately 122 hours of total test time for 1 unit
tests_data = {
    'TestID': [f'T{i}' for i in range(1, 26)],  # 25 tests
    'TestName': [f'Test_{i}' for i in range(1, 26)],
    'Station': ['Station1', 'Station2', 'Station3', 'Station1', 'Station2',
                'Station3', 'Station1', 'Station2', 'Station3', 'Station4',
                'Station1', 'Station2', 'Station3', 'Station4', 'Station1',
                'Station2', 'Station3', 'Station4', 'Station1', 'Station2',
                'Station3', 'Station4', 'Station1', 'Station2', 'Station3'],
    'TestTimeMin': [300, 240, 360, 300, 240,  # Mix of durations: 4-6 hours per test
                    360, 300, 240, 360, 300,
                    240, 360, 300, 240, 360,
                    300, 240, 360, 300, 240,
                    360, 300, 240, 360, 300],  # Total ~7320 min = 122 hours
    'DependsOn': [''] + [f'T{i}' for i in range(1, 25)],  # Sequential chain
}
tests_df = pd.DataFrame(tests_data)

deps, succs, topo = build_dag(tests_df)
tests_info = build_tests_info(tests_df, deps, parse_time)

print("=== Realistic Test Scenario (similar to VXG 54GHz) ===")
print(f"Total tests: {len(tests_df)}")
total_time = sum(tests_df['TestTimeMin'])
print(f"Total sequential test time: {total_time/60:.1f} hours")

print("\n=== Test 1: 1 unit with minimal stations ===")
st_map_1 = {
    'Station1': {'count': 1, 'uptime': 1.0},
    'Station2': {'count': 1, 'uptime': 1.0},
    'Station3': {'count': 1, 'uptime': 1.0},
    'Station4': {'count': 1, 'uptime': 1.0},
}
mk1, finishes1, util1 = schedule_n_units(tests_info, topo, st_map_1, n_units=1)
print(f"Makespan: {mk1:.1f} hours")
print(f"Expected: ~{total_time/60:.1f} hours")

print("\n=== Test 2: 10 units with 10x stations (contended, should scale linearly) ===")
st_map_2 = {
    'Station1': {'count': 10, 'uptime': 1.0},
    'Station2': {'count': 10, 'uptime': 1.0},
    'Station3': {'count': 10, 'uptime': 1.0},
    'Station4': {'count': 10, 'uptime': 1.0},
}
mk2, finishes2, util2 = schedule_n_units(tests_info, topo, st_map_2, n_units=10)
print(f"Makespan: {mk2:.1f} hours")
print(f"Expected: ~{mk1:.1f} hours (fully dedicated -> parallel execution)")

ratio = mk2 / mk1
print(f"Speedup ratio: {ratio:.2f}x (1.0 = perfect parallel, 10.0 = fully serialized)")

if ratio < 1.5:
    print("✓ PASS: Units are running in parallel as expected!")
else:
    print(f"✗ FAIL: Makespan ratio {ratio:.2f} indicates significant serialization")
    print(f"  With 10 units and 10x stations, makespan should stay near {mk1:.1f}h, not {mk2:.1f}h")

print("\n=== Test 3: 10 units with 20x stations (over-provisioned) ===")
st_map_3 = {
    'Station1': {'count': 20, 'uptime': 1.0},
    'Station2': {'count': 20, 'uptime': 1.0},
    'Station3': {'count': 20, 'uptime': 1.0},
    'Station4': {'count': 20, 'uptime': 1.0},
}
mk3, finishes3, util3 = schedule_n_units(tests_info, topo, st_map_3, n_units=10)
print(f"Makespan: {mk3:.1f} hours")
print(f"Expected: ~{mk1:.1f} hours (over-provisioned -> still parallel)")

ratio3 = mk3 / mk1
print(f"Speedup ratio: {ratio3:.2f}x")

if ratio3 < 1.5:
    print("✓ PASS: Over-provisioned stations work correctly!")
else:
    print(f"✗ FAIL: Even with 2x over-provisioning, units are serializing")

print("\n=== Summary ===")
if ratio < 1.5 and ratio3 < 1.5:
    print("✅ SUCCESS: All parallel execution tests passed!")
    print(f"   1 unit: {mk1:.1f}h")
    print(f"   10 units (10x stations): {mk2:.1f}h (ratio: {ratio:.2f}x)")
    print(f"   10 units (20x stations): {mk3:.1f}h (ratio: {ratio3:.2f}x)")
else:
    print("❌ PROBLEM: Units are still being serialized despite adequate stations")
