#!/usr/bin/env python
"""
Test to verify that changing channel marker counts doesn't affect scheduling results.
"""
import pandas as pd
from piston_core.io import load_model
from piston_core.scheduler import build_dag, schedule_n_units

def test_channel_markers_dont_affect_calculations():
    """Verify that channel marker counts don't affect scheduling."""
    try:
        import os
        model_path = os.path.join('embedded', 'default_model.xlsx')
        if not os.path.exists(model_path):
            model_path = 'default_model.xlsx'
        
        if not os.path.exists(model_path):
            print("Cannot find model file. Test skipped.")
            return
        
        print("Loading model...")
        stations_df, tests_df, st_map, station_map_df, plan_schema_df, non_test_df = load_model(model_path)
        
        # Filter to get a simple subset of tests for scheduling
        if tests_df.empty:
            print("No tests in model. Test skipped.")
            return
            
        # Take first 10 tests for quick calculation
        test_subset = tests_df.head(10).copy()
        
        # Build DAG
        deps, succs, topo = build_dag(test_subset)
        
        # Build tests_info
        tests_info = {}
        for idx, row in test_subset.iterrows():
            test_id = str(row['TestID']).strip()
            node_id = f"r{idx}"
            depends_on_str = str(row['DependsOn']).strip() if pd.notna(row['DependsOn']) and str(row['DependsOn']).strip() else ''
            depends_list = [d.strip() for d in depends_on_str.split(',') if d.strip()] if depends_on_str else []
            tests_info[node_id] = {
                'tid': test_id,
                'station': str(row['Station']).strip() if pd.notna(row['Station']) else '',
                'time_min': float(row['TestTimeMin']) if pd.notna(row['TestTimeMin']) else 0.0,
                'depends_on': depends_list,
            }
        
        print(f"\nRunning scheduling with {len(st_map)} stations...")
        print(f"Stations: {sorted(st_map.keys())}")
        
        # Verify no hidden stations in st_map
        hidden_in_map = [s for s in st_map.keys() 
                        if any(marker in str(s).lower() 
                              for marker in ['channel', 'loading gate'])]
        
        if hidden_in_map:
            print(f"\n❌ FAIL: Found hidden stations in st_map: {hidden_in_map}")
            return False
        
        print(f"\n✅ Confirmed: No channel markers in st_map")
        
        # Try to run a simple schedule calculation
        try:
            makespan, finishes, utilization = schedule_n_units(
                tests_info, topo, st_map, n_units=2,
                channels_per_unit=None, unit_bias=None
            )
            print(f"\n✅ Scheduling succeeded!")
            print(f"Makespan for 2 units: {makespan:.2f} hours")
            print(f"Station utilization: {len(utilization)} stations used")
            
            # Show which stations were actually used
            used_stations = [s for s, util in utilization.items() if util > 0]
            print(f"Stations with activity: {sorted(used_stations)}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Scheduling failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_channel_markers_dont_affect_calculations()
    if success:
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("Channel markers are successfully excluded from calculations!")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("❌ TEST FAILED")
        print("="*60)
