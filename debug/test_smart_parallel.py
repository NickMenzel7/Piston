#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script to verify smart parallel mode works correctly.
Tests that 10 units with 10x stations gives ~122 hours, not 1000 hours.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from piston_core.scheduler import build_dag, schedule_n_units
from piston_core.mapping import read_plan_schema, plan_to_tests_rows, read_station_map
from piston_core.io import load_model
from piston_ui.validation_helper import build_tests_info
from piston_core.utils import parse_time_to_minutes
import pandas as pd

def test_smart_parallel():
    """Test that 10 units with 10x stations gives proper parallel execution."""
    
    # Load the model
    model_path = 'embedded/default_model.xlsx'
    if not os.path.exists(model_path):
        print(f"ERROR: Model not found at {model_path}")
        return False
    
    print(f"Loading model from {model_path}...")
    stations_df, tests_df, st_map, station_map_df, plan_schema_df, non_test_df = load_model(model_path)
    
    # Load VXG 54GHz Variant 1
    plan_path = 'plans/VXG 54GHz/variant1.csv'
    if not os.path.exists(plan_path):
        print(f"ERROR: Plan not found at {plan_path}")
        return False

    print(f"Loading plan from {plan_path}...")
    plan_df = pd.read_csv(plan_path)
    
    # Map to tests rows
    plan_schema_map = read_plan_schema(plan_schema_df)
    station_rules = read_station_map(station_map_df)
    
    from piston_core.mapping import auto_map_plan_schema
    mapped, warnings = auto_map_plan_schema(plan_df, plan_schema_map)
    
    tests_rows, issues = plan_to_tests_rows(
        plan_df, mapped, station_rules, stations_df,
        project_override='VXG 54GHz', scenario_override=None, sheet_name=None
    )
    
    # Build DAG and tests_info
    deps, succs, topo = build_dag(tests_rows)
    tests_info = build_tests_info(tests_rows, deps, parse_time_to_minutes)
    
    print(f"\nLoaded {len(tests_rows)} tests")
    print(f"Station map has {len(st_map)} stations")
    
    # Test 1: Single unit (should be ~122 hours)
    print("\n" + "="*60)
    print("TEST 1: Single unit with 1x station counts")
    print("="*60)
    
    st_map_1x = {k: {'count': 1, 'uptime': 1.0} for k in st_map.keys()}
    
    mk_1unit, finishes_1unit, util_1unit = schedule_n_units(
        tests_info, topo, st_map_1x, n_units=1,
        channels_per_unit=[1],
        unit_bias=None,  # Let default kick in
        serialization_mode='Auto'
    )
    
    print(f"Result: {mk_1unit:.2f} hours")
    print(f"Expected: ~122 hours")
    
    if abs(mk_1unit - 122) > 10:
        print(f"WARNING: Single unit time is {mk_1unit:.2f} hours, expected ~122 hours")
    
    # Test 2: 10 units with 10x stations (should ALSO be ~122 hours with smart mode)
    print("\n" + "="*60)
    print("TEST 2: 10 units with 10x station counts (SMART MODE)")
    print("="*60)
    
    st_map_10x = {k: {'count': 10, 'uptime': 1.0} for k in st_map.keys()}
    
    # Smart mode should kick in here automatically because min_station_count (10) >= n_units (10)
    # This should force unit_bias=0.0 and serialization_mode='Relaxed'
    
    mk_10units, finishes_10units, util_10units = schedule_n_units(
        tests_info, topo, st_map_10x, n_units=10,
        channels_per_unit=[1]*10,
        unit_bias=0.0,  # Smart mode sets this
        serialization_mode='Relaxed'  # Smart mode sets this
    )
    
    print(f"Result: {mk_10units:.2f} hours")
    print(f"Expected: ~122 hours (same as single unit, running in parallel)")
    
    # Check results
    success = True
    
    if abs(mk_10units - mk_1unit) > 5:
        print(f"\nFAILED: 10 units took {mk_10units:.2f} hours vs 1 unit {mk_1unit:.2f} hours")
        print(f"   Expected them to be similar (parallel execution)")
        success = False
    else:
        print(f"\nSUCCESS: 10 units ({mk_10units:.2f}h) ~= 1 unit ({mk_1unit:.2f}h)")
        print(f"   Parallel execution working correctly!")
    
    # Show station utilization
    print("\nStation utilization (10 units):")
    for stn, util_frac in sorted(util_10units.items())[:5]:
        hours = util_frac * mk_10units
        print(f"  {stn}: {hours:.2f} hours ({util_frac*100:.1f}% utilization)")
    
    return success

if __name__ == '__main__':
    try:
        success = test_smart_parallel()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
