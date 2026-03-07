#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Diagnose why GUI shows 700 hours instead of expected ~122 hours
"""

import pandas as pd
from piston_core.scheduler import schedule_n_units
from piston_core.mapping import read_plan_schema, plan_to_tests_rows, read_station_map, auto_map_plan_schema
from piston_core.io import load_model
from piston_ui.validation_helper import build_tests_info
from piston_core.utils import parse_time_to_minutes
from piston_core.scheduler import build_dag

# Load model
model_path = 'embedded/default_model.xlsx'
stations_df, tests_df, st_map, station_map_df, plan_schema_df, non_test_df = load_model(model_path)

# Load plan
plan_path = 'plans/VXG 54GHz/variant1.csv'
plan_df = pd.read_csv(plan_path)

# Map to tests
plan_schema_map = read_plan_schema(plan_schema_df)
station_rules = read_station_map(station_map_df)
mapped, warnings = auto_map_plan_schema(plan_df, plan_schema_map)
tests_rows, issues = plan_to_tests_rows(
    plan_df, mapped, station_rules, stations_df,
    project_override='VXG 54GHz', scenario_override=None, sheet_name=None
)

# Build DAG
deps, succs, topo = build_dag(tests_rows)
tests_info = build_tests_info(tests_rows, deps, parse_time_to_minutes)

print("=" * 80)
print("DIAGNOSING GUI ISSUE: Why 700 hours instead of 122?")
print("=" * 80)

# Scenario 1: What user THINKS they're doing
print("\n[Scenario 1] What you probably entered:")
print("  N=10, Single=10, Dual=0, Quad=0, Stations=10 each")
st_map_10x = {k: {'count': 10, 'uptime': 1.0} for k in st_map.keys()}

# Try different channel specs to see which gives 700 hours
print("\n[Test A] channels_per_unit=[1]*10 (10 single-channel units)")
mk_a, fin_a, util_a = schedule_n_units(
    tests_info, topo, st_map_10x, n_units=10,
    channels_per_unit=[1]*10, unit_bias=None,
    serialization_mode='Auto'
)
print(f"  Result: {mk_a:.2f} hours")

print("\n[Test B] channels_per_unit=1 (uniform single channel)")
mk_b, fin_b, util_b = schedule_n_units(
    tests_info, topo, st_map_10x, n_units=10,
    channels_per_unit=1, unit_bias=None,
    serialization_mode='Auto'
)
print(f"  Result: {mk_b:.2f} hours")

print("\n[Test C] channels_per_unit=[2]*10 (10 dual-channel units)")
mk_c, fin_c, util_c = schedule_n_units(
    tests_info, topo, st_map_10x, n_units=10,
    channels_per_unit=[2]*10, unit_bias=None,
    serialization_mode='Auto'
)
print(f"  Result: {mk_c:.2f} hours")

print("\n[Test D] channels_per_unit=[4]*10 (10 quad-channel units)")
mk_d, fin_d, util_d = schedule_n_units(
    tests_info, topo, st_map_10x, n_units=10,
    channels_per_unit=[4]*10, unit_bias=None,
    serialization_mode='Auto'
)
print(f"  Result: {mk_d:.2f} hours")

# Check if any match 700 hours
print("\n" + "=" * 80)
print("WHICH SCENARIO MATCHES YOUR 700 HOURS?")
print("=" * 80)
results = {
    'A (list [1]*10)': mk_a,
    'B (int 1)': mk_b,
    'C (list [2]*10)': mk_c,
    'D (list [4]*10)': mk_d
}

for name, mk in results.items():
    diff = abs(mk - 700)
    if diff < 50:
        print(f"*** {name}: {mk:.2f} hours ← CLOSEST TO 700! ***")
    else:
        print(f"    {name}: {mk:.2f} hours")

# Also test with explicit bias (Smart Mode disabled)
print("\n" + "=" * 80)
print("TESTING WITH BIAS (Smart Mode disabled)")
print("=" * 80)

print("\n[Test E] With unit_bias=0.01 (Smart Mode OFF)")
mk_e, fin_e, util_e = schedule_n_units(
    tests_info, topo, st_map_10x, n_units=10,
    channels_per_unit=[1]*10, unit_bias=0.01,
    serialization_mode='Auto'
)
print(f"  Result: {mk_e:.2f} hours")

print("\n[Test F] With serialization_mode='Strict'")
mk_f, fin_f, util_f = schedule_n_units(
    tests_info, topo, st_map_10x, n_units=10,
    channels_per_unit=[1]*10, unit_bias=None,
    serialization_mode='Strict'
)
print(f"  Result: {mk_f:.2f} hours")

if abs(mk_e - 700) < 50 or abs(mk_f - 700) < 50:
    print("\n⚠️  FOUND IT! Smart Mode is being disabled!")
    print("    Check if you have a value in 'Unit bias' field")
    print("    Or if Serialization is set to 'Strict'")
