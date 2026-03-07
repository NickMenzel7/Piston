#!/usr/bin/env python
"""
Test that plan_to_tests_rows filters out hidden stations.
"""
import pandas as pd
from piston_core.mapping import plan_to_tests_rows, read_station_map

def test_plan_mapping_excludes_hidden_stations():
    """Verify that tests referencing hidden stations get None for their station."""
    
    # Mock stations_df with both real and hidden stations
    stations_df = pd.DataFrame({
        'Station': ['Align-X', 'VXG Channel', 'Hi Pot', 'YS Loading Gate', 'Racer Channel'],
        'StationCount': [2, 1, 1, 1, 1]
    })
    
    # Mock plan with tests referencing both real and hidden stations
    plan_df = pd.DataFrame({
        'Proc #': ['1', '2', '3', '4'],
        'Step Name': ['Test Align', 'Channel Marker', 'Test HiPot', 'Gate Marker'],
        'Duration (min)': [10, 0, 5, 0],
        'Station': ['Align-X', 'VXG Channel', 'Hi Pot', 'YS Loading Gate']
    })
    
    # Mock plan schema
    plan_schema_map = {
        'StepID': 'Proc #',
        'StepName': 'Step Name',
        'DurationMin': 'Duration (min)',
        'StationResource': 'Station',
        'Predecessors': '',
        'Project': '',
        'Scenario': ''
    }
    
    # Mock station rules (empty for this test)
    station_rules = []
    
    # Call plan_to_tests_rows
    result_df, issues = plan_to_tests_rows(
        plan_df, plan_schema_map, station_rules, stations_df
    )
    
    print("Result DataFrame:")
    print(result_df[['TestID', 'TestName', 'Station']])
    print()
    
    # Check results
    test1 = result_df.iloc[0]
    test2 = result_df.iloc[1]
    test3 = result_df.iloc[2]
    test4 = result_df.iloc[3]
    
    print(f"Test 1 (Align-X): Station = {test1['Station']}")
    print(f"Test 2 (VXG Channel): Station = {test2['Station']}")
    print(f"Test 3 (Hi Pot): Station = {test3['Station']}")
    print(f"Test 4 (YS Loading Gate): Station = {test4['Station']}")
    print()
    
    # Verify real stations are mapped
    assert test1['Station'] == 'Align-X', f"Expected 'Align-X', got {test1['Station']}"
    assert test3['Station'] == 'Hi Pot', f"Expected 'Hi Pot', got {test3['Station']}"
    
    # Verify hidden stations are NOT mapped (should be None)
    assert test2['Station'] is None, f"Expected None for VXG Channel, got {test2['Station']}"
    assert test4['Station'] is None, f"Expected None for YS Loading Gate, got {test4['Station']}"
    
    print("✅ SUCCESS: Hidden stations are filtered out during plan mapping!")
    print("   - Real stations (Align-X, Hi Pot) are mapped correctly")
    print("   - Hidden stations (VXG Channel, YS Loading Gate) result in None")
    return True

if __name__ == '__main__':
    try:
        success = test_plan_mapping_excludes_hidden_stations()
        if success:
            print("\n" + "="*60)
            print("✅ ALL TESTS PASSED")
            print("="*60)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
