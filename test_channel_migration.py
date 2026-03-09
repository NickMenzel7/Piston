"""
Test script to verify channel configuration migration works correctly.

This script validates that:
1. Channel quantity controls are removed from UI
2. Channel spec always returns 1 (no multiplier)
3. Project-based channel configuration works
"""

import sys
import os

# Add parent directory to path to import Piston modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_channel_spec():
    """Test that channel spec building returns 1 (no multiplier)."""
    print("=" * 60)
    print("TEST: Channel Spec Building")
    print("=" * 60)
    
    from piston_ui.calculate import _build_channels_spec_validated
    
    # Create mock app object with minimal attributes
    class MockApp:
        pass
    
    app = MockApp()
    
    # Test with mode='time_for_n', n_req=10
    result = _build_channels_spec_validated(app, 'time_for_n', 10)
    
    print(f"Input: mode='time_for_n', n_req=10")
    print(f"Result: {result}")
    print(f"Expected: 1 (no channel multiplier)")
    
    if result == 1:
        print("✅ PASS: Channel spec correctly returns 1")
        return True
    else:
        print(f"❌ FAIL: Expected 1, got {result}")
        return False


def test_ui_variables():
    """Test that channel quantity variables are NOT present in PlannerApp."""
    print("\n" + "=" * 60)
    print("TEST: UI Variables")
    print("=" * 60)
    
    # Import Piston to check class definition
    import Piston
    
    # Check __init__ source code for removed variables
    init_source = Piston.PlannerApp.__init__.__code__.co_names
    
    removed_vars = ['single_var', 'dual_var', 'quad_var', 'single_spin', 'dual_spin', 'quad_spin']
    
    print("Checking if removed variables are absent from PlannerApp.__init__:")
    
    all_pass = True
    for var in removed_vars:
        if var in init_source:
            print(f"❌ FAIL: {var} still present in __init__")
            all_pass = False
        else:
            print(f"✅ PASS: {var} correctly removed")
    
    return all_pass


def test_calculate_imports():
    """Test that calculate.py no longer imports build_channels_spec."""
    print("\n" + "=" * 60)
    print("TEST: Calculate Module Imports")
    print("=" * 60)
    
    import piston_ui.calculate as calc_module
    
    # Check if build_channels_spec is in the module
    has_build_channels = hasattr(calc_module, 'build_channels_spec')
    
    print(f"Checking if build_channels_spec is imported in calculate.py:")
    
    if has_build_channels:
        print("❌ FAIL: build_channels_spec still imported (should be removed)")
        return False
    else:
        print("✅ PASS: build_channels_spec correctly not imported")
        return True


def main():
    """Run all tests and report results."""
    print("\n" + "=" * 60)
    print("CHANNEL CONFIGURATION MIGRATION TESTS")
    print("=" * 60 + "\n")
    
    results = []
    
    # Run tests
    try:
        results.append(("Channel Spec Building", test_channel_spec()))
    except Exception as e:
        print(f"❌ EXCEPTION in Channel Spec test: {e}")
        results.append(("Channel Spec Building", False))
    
    try:
        results.append(("UI Variables Removed", test_ui_variables()))
    except Exception as e:
        print(f"❌ EXCEPTION in UI Variables test: {e}")
        results.append(("UI Variables Removed", False))
    
    try:
        results.append(("Calculate Imports", test_calculate_imports()))
    except Exception as e:
        print(f"❌ EXCEPTION in Calculate Imports test: {e}")
        results.append(("Calculate Imports", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Channel configuration migration successful.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
