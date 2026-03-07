#!/usr/bin/env python
"""
Test script to verify hidden stations are filtered out from calculations.
"""
import pandas as pd
from piston_core.io import load_model

def test_hidden_stations_filtered():
    """Test that hidden stations are excluded from st_map."""
    try:
        # Load the default model
        import os
        model_path = os.path.join('embedded', 'default_model.xlsx')
        if not os.path.exists(model_path):
            print(f"Model not found at {model_path}, trying alternate location...")
            model_path = 'default_model.xlsx'
        
        if not os.path.exists(model_path):
            print("Cannot find model file. Test skipped.")
            return
        
        print(f"Loading model from: {model_path}")
        stations_df, tests_df, st_map, station_map_df, plan_schema_df, non_test_df = load_model(model_path)
        
        print(f"\nTotal stations in Stations sheet: {len(stations_df)}")
        print(f"Total stations in st_map: {len(st_map)}")
        
        # Check if hidden stations are in the dataframe
        hidden_stations_in_df = []
        for station in stations_df['Station']:
            station_lower = str(station).strip().lower()
            if any(hidden in station_lower for hidden in ['channel', 'loading gate']):
                hidden_stations_in_df.append(station)
        
        print(f"\nChannel markers found in Stations sheet: {hidden_stations_in_df}")
        
        # Check if hidden stations are in st_map (they should NOT be)
        hidden_in_map = []
        for station in st_map.keys():
            station_lower = str(station).strip().lower()
            if any(hidden in station_lower for hidden in ['channel', 'loading gate']):
                hidden_in_map.append(station)
        
        print(f"Channel markers found in st_map: {hidden_in_map}")
        
        if hidden_in_map:
            print("\n❌ FAIL: Hidden stations are still in st_map!")
            print("These stations should be filtered out:")
            for station in hidden_in_map:
                print(f"  - {station}: count={st_map[station]}")
        else:
            print("\n✅ SUCCESS: All channel markers are filtered out from st_map!")
            
        # Show what's actually in st_map
        print(f"\nStations in st_map (used for calculations):")
        for station, info in sorted(st_map.items()):
            count = info.get('count', 0) if isinstance(info, dict) else info
            print(f"  - {station}: {count}")
            
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_hidden_stations_filtered()
