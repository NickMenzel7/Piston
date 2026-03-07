#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test the yield bug: effective_tests breaks fully_dedicated detection
"""

import pandas as pd
import math
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
print("YIELD BUG TEST")
print("=" * 80)

# Simulate what GUI does
n_req = 10
yield_pct = 17.5  # Try different yields
yfrac = yield_pct / 100.0

effective_tests = max(1, math.ceil(n_req / yfrac))
print(f"\nUser wants: {n_req} good units")
print(f"Yield: {yield_pct}%")
print(f"Effective tests needed: {effective_tests}")

st_map_10x = {k: {'count': 10, 'uptime': 1.0} for k in st_map.keys()}

print(f"\nScheduling with n_units={effective_tests} (CURRENT BUGGY BEHAVIOR)")
mk_bug, fin_bug, util_bug = schedule_n_units(
    tests_info, topo, st_map_10x, n_units=effective_tests,
    channels_per_unit=[1]*effective_tests, unit_bias=None,
    serialization_mode='Auto'
)
print(f"  Result: {mk_bug:.2f} hours")
print(f"  fully_dedicated would check: 10 >= {effective_tests}? {10 >= effective_tests}")

print(f"\nScheduling with n_units={n_req} (CORRECT BEHAVIOR)")
mk_correct, fin_correct, util_correct = schedule_n_units(
    tests_info, topo, st_map_10x, n_units=n_req,
    channels_per_unit=[1]*n_req, unit_bias=None,
    serialization_mode='Auto'
)
print(f"  Result: {mk_correct:.2f} hours")
print(f"  fully_dedicated would check: 10 >= {n_req}? {10 >= n_req}")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
if abs(mk_bug - 700) < 50:
    print(f"✓ REPRODUCED BUG: {mk_bug:.2f} hours ≈ 700 hours")
    print("  Cause: Passing effective_tests to scheduler breaks fully_dedicated check")
else:
    print(f"  Couldn't reproduce 700 hours (got {mk_bug:.2f})")

print(f"\nCorrect result should be: {mk_correct:.2f} hours")
print("Fix: Handle yield OUTSIDE scheduler, pass n_req not effective_tests")
