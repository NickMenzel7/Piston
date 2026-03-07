#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick test to verify Option A (dedicated lines) is working correctly.
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
print("OPTION A (DEDICATED LINES) VERIFICATION")
print("=" * 80)

# Test 1: 1 unit, 1x stations
print("\n[Test 1] 1 unit, 1x stations")
st_map_1x = {k: {'count': 1, 'uptime': 1.0} for k in st_map.keys()}
mk1, finishes1, util1 = schedule_n_units(
    tests_info, topo, st_map_1x, n_units=1,
    channels_per_unit=[1], unit_bias=None,
    serialization_mode='Auto'
)
print(f"  Makespan: {mk1:.2f} hours")

# Test 2: 10 units, 10x stations (should be same as 1 unit!)
print("\n[Test 2] 10 units, 10x stations (DEDICATED)")
st_map_10x = {k: {'count': 10, 'uptime': 1.0} for k in st_map.keys()}
mk10, finishes10, util10 = schedule_n_units(
    tests_info, topo, st_map_10x, n_units=10,
    channels_per_unit=[1]*10, unit_bias=None,
    serialization_mode='Auto'
)
print(f"  Makespan: {mk10:.2f} hours")

# Test 3: 10 units, 5x stations (shared pool - should be longer)
print("\n[Test 3] 10 units, 5x stations (SHARED POOL)")
st_map_5x = {k: {'count': 5, 'uptime': 1.0} for k in st_map.keys()}
mk5, finishes5, util5 = schedule_n_units(
    tests_info, topo, st_map_5x, n_units=10,
    channels_per_unit=[1]*10, unit_bias=None,
    serialization_mode='Auto'
)
print(f"  Makespan: {mk5:.2f} hours")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"1 unit, 1x stations:       {mk1:.2f} hours")
print(f"10 units, 10x stations:    {mk10:.2f} hours (ratio: {mk10/mk1:.2f}x)")
print(f"10 units, 5x stations:     {mk5:.2f} hours (ratio: {mk5/mk1:.2f}x)")

if abs(mk10 - mk1) < 0.1:
    print("\n✓ PASS: 10x dedicated stations = same time as 1 unit (Option A working!)")
else:
    print(f"\n✗ FAIL: Expected ~{mk1:.2f} hours, got {mk10:.2f} hours")

if mk5 > mk10:
    print("✓ PASS: 5x shared pool > 10x dedicated (contention working!)")
else:
    print("✗ FAIL: Expected 5x shared pool to be slower than 10x dedicated")
