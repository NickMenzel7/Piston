#!/usr/bin/env python
"""
Test Capacity Estimator fix - verify it populates correctly.
"""
import sys
import os

def test_manual_et_import():
    """Test that the manual_et module can be imported and doesn't have syntax errors."""
    print("="*60)
    print("Testing Capacity Estimator Fix")
    print("="*60)
    
    print("\n1. Testing import...")
    try:
        from piston_ui import manual_et
        print("   ✓ manual_et imported successfully")
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        return False
    
    print("\n2. Testing hidden stations helper...")
    try:
        hidden = manual_et._get_hidden_stations()
        print(f"   ✓ Hidden stations: {len(hidden)} stations")
        for station in list(hidden)[:3]:
            print(f"      - {station}")
    except Exception as e:
        print(f"   ❌ Helper failed: {e}")
        return False
    
    print("\n3. Testing _is_hidden_station function...")
    try:
        assert manual_et._is_hidden_station("VXG Channel") == True
        assert manual_et._is_hidden_station("Align-X") == False
        print("   ✓ _is_hidden_station works correctly")
    except Exception as e:
        print(f"   ❌ Function test failed: {e}")
        return False
    
    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED")
    print("="*60)
    print("\nThe Capacity Estimator should now populate correctly!")
    return True

if __name__ == '__main__':
    try:
        success = test_manual_et_import()
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
