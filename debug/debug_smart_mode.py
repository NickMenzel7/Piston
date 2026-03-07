#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Debug script to understand why 10 units with 10x stations gives 69 hours vs 122 hours for 1 unit.
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from piston_core.scheduler import build_dag, schedule_n_units
from piston_core.mapping import read_plan_schema, plan_to_tests_rows, read_station_map
from piston_core.io import load_model
from piston_ui.validation_helper import build_tests_info
from piston_core.utils import parse_time_to_minutes

def analyze_schedule():
    """Analyze what's happening with single unit vs parallel units."""
    
    # Load model and plan
    model_path = 'embedded/default_model.xlsx'
    stations_df, tests_df, st_map, station_map_df, plan_schema_df, non_test_df = load_model(model_path)
    
    plan_path = 'plans/VXG 54GHz/variant1.csv'
    plan_df = pd.read_csv(plan_path)
    
    # Map to tests
    plan_schema_map = read_plan_schema(plan_schema_df)
    station_rules = read_station_map(station_map_df)
    from piston_core.mapping import auto_map_plan_schema
    mapped, warnings = auto_map_plan_schema(plan_df, plan_schema_map)
    tests_rows, issues = plan_to_tests_rows(
        plan_df, mapped, station_rules, stations_df,
        project_override='VXG 54GHz', scenario_override=None, sheet_name=None
    )
    
    # Build DAG
    deps, succs, topo = build_dag(tests_rows)
    tests_info = build_tests_info(tests_rows, deps, parse_time_to_minutes)
    
    print("="*80)
    print("ANALYSIS: Single Unit vs Multiple Units")
    print("="*80)
    
    # Test 1: Single unit, single set of stations
    print("\n[1] SINGLE UNIT, 1x STATIONS")
    print("-" * 80)
    st_map_1x = {k: {'count': 1, 'uptime': 1.0} for k in st_map.keys()}
    
    mk_1unit, finishes_1unit, util_1unit, events_1unit = schedule_n_units(
        tests_info, topo, st_map_1x, n_units=1,
        channels_per_unit=[1],
        unit_bias=0.0,
        serialization_mode='Relaxed',
        trace=True
    )
    
    print(f"Makespan: {mk_1unit:.2f} hours")
    
    # Analyze how many tests ran in parallel
    print("\nChecking for parallel execution within single unit:")
    time_slices = {}
    for event in events_1unit:
        if event.get('event') == 'assign':
            start = event['start']
            finish = event['finish']
            tid = event.get('tid', '')
            
            # Check what's running at this test's start time
            if start not in time_slices:
                time_slices[start] = []
            time_slices[start].append({
                'tid': tid,
                'station': event.get('station', ''),
                'duration': finish - start
            })
    
    # Find times where multiple tests were running
    parallel_moments = []
    for t in sorted(time_slices.keys()):
        running_at_t = []
        for start_time, tests in time_slices.items():
            for test in tests:
                if start_time <= t < (start_time + test['duration']):
                    running_at_t.append(test)
        
        if len(running_at_t) > 1:
            parallel_moments.append((t, running_at_t))
    
    if parallel_moments:
        print(f"\n[!] FOUND {len(parallel_moments)} moments with parallel execution!")
        print("\nFirst 5 parallel moments:")
        for t, tests in parallel_moments[:5]:
            print(f"\nTime {t:.2f}hrs:")
            for test in tests:
                print(f"  - {test['tid']} on {test['station']}")
    else:
        print("\n[OK] No parallel execution found (tests ran sequentially)")
    
    # Test 2: 10 units, 10x stations
    print("\n\n[2] 10 UNITS, 10x STATIONS")
    print("-" * 80)
    st_map_10x = {k: {'count': 10, 'uptime': 1.0} for k in st_map.keys()}
    
    mk_10units, finishes_10units, util_10units, events_10units = schedule_n_units(
        tests_info, topo, st_map_10x, n_units=10,
        channels_per_unit=[1]*10,
        unit_bias=0.0,
        serialization_mode='Relaxed',
        trace=True
    )
    
    print(f"Makespan: {mk_10units:.2f} hours")
    
    # Analyze per-unit completion times
    unit_finishes = {}
    for event in events_10units:
        if event.get('event') == 'complete':
            flow = event.get('flow', '')
            finish_time = event.get('finish', 0)
            if flow not in unit_finishes:
                unit_finishes[flow] = finish_time
            else:
                unit_finishes[flow] = max(unit_finishes[flow], finish_time)
    
    print(f"\nPer-unit completion times:")
    for unit in sorted(unit_finishes.keys()):
        print(f"  {unit}: {unit_finishes[unit]:.2f} hours")
    
    # Key question: Does each individual unit take ~122 hours?
    avg_unit_time = sum(unit_finishes.values()) / len(unit_finishes) if unit_finishes else 0
    print(f"\nAverage unit completion time: {avg_unit_time:.2f} hours")
    
    # Compare
    print("\n" + "="*80)
    print("COMPARISON")
    print("="*80)
    print(f"Single unit time:        {mk_1unit:.2f} hours")
    print(f"10 units makespan:       {mk_10units:.2f} hours")
    print(f"Average unit time (10x): {avg_unit_time:.2f} hours")
    print(f"\nRatio (10x/1x):         {mk_10units/mk_1unit:.2f}x")
    
    if mk_10units < mk_1unit * 0.95:
        print("\n[!] WARNING: Makespan for 10 units is significantly less than single unit!")
        print("   This suggests intra-unit parallelism (multiple tests per unit running simultaneously)")
        print("   Question: Is this realistic for your test setup?")
        
        # Show evidence
        print("\n   Analyzing Unit 1's test schedule in 10-unit scenario:")
        unit1_tests = [e for e in events_10units if e.get('flow') == 'u0' and e.get('event') == 'assign']
        
        if unit1_tests:
            # Check for overlaps
            overlaps = []
            for i, test1 in enumerate(unit1_tests):
                for test2 in unit1_tests[i+1:]:
                    # Check if they overlap
                    start1, end1 = test1['start'], test1['finish']
                    start2, end2 = test2['start'], test2['finish']
                    
                    if not (end1 <= start2 or end2 <= start1):
                        overlaps.append((test1, test2))
            
            if overlaps:
                print(f"\n   Found {len(overlaps)} overlapping tests for Unit 1!")
                print("   First 3 examples:")
                for test1, test2 in overlaps[:3]:
                    print(f"     {test1.get('tid')} [{test1['start']:.1f}-{test1['finish']:.1f}] overlaps with")
                    print(f"     {test2.get('tid')} [{test2['start']:.1f}-{test2['finish']:.1f}]")
    else:
        print("\n[OK] Makespan scales as expected (units don't speed up individual test time)")
    
    return mk_1unit, mk_10units, avg_unit_time

if __name__ == '__main__':
    try:
        single_time, parallel_time, avg_time = analyze_schedule()
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        print(f"Single unit:  {single_time:.2f} hours")
        print(f"10 units:     {parallel_time:.2f} hours (avg per unit: {avg_time:.2f} hours)")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
