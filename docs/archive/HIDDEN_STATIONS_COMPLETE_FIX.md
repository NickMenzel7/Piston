# Hidden Stations Fix - Complete Summary

## The Error You Were Seeing

```
Schedule computation failed: Tests reference unknown stations: ["VXG Channel", "YS Loading Gate"]. 
Example TestIDs: r20, r21
```

## What Was Happening

Your Tests sheet had rows with "VXG Channel" or "YS Loading Gate" in the Station column. These are channel markers (flow indicators), not actual test stations. When the scheduler tried to run:

1. ✅ Hidden stations were filtered from `st_map` (so scheduler didn't know about them)
2. ❌ But tests still had these stations assigned
3. ❌ Scheduler validation failed: "unknown stations"

## The Complete Fix

We added filtering at **every point** where hidden stations could enter the system:

### Files Modified:

1. **piston_core/io.py** (`load_model`)
   - Filters hidden stations when creating st_map

2. **piston_core/mapping.py** (`plan_to_tests_rows`, `load_manual_et`)
   - Filters hidden stations from stations_set
   - Tests mapped from plans won't get hidden stations

3. **piston_ui/validation_helper.py** (`build_tests_info`, `find_invalid_tests`) - **CRITICAL FIX**
   - `build_tests_info()`: Sets Station=None for tests that reference hidden stations
   - `find_invalid_tests()`: Doesn't flag hidden stations as errors
   - **This fixes your error!** Tests from the Tests sheet are now properly filtered

4. **Piston.py**
   - Removed duplicate HIDDEN_STATIONS definition
   - Already had filtering in calculate() and view_stationmap()

## What Happens Now

### For Tests in Tests Sheet:
- If a test has Station = "VXG Channel" → Station is changed to None
- If a test has Station = "YS Loading Gate" → Station is changed to None
- These tests won't cause validation errors
- They're treated as unmapped tests (no station assigned)

### For New Plan Imports:
- Resources mapped to hidden stations → Station = None
- No validation errors

### In the UI:
- Hidden stations don't appear in Stations list
- Hidden stations don't appear in Station Map view
- Hidden stations are excluded from all calculations

### Result:
✅ **No more "unknown station" errors**
✅ **Calculations only use real test stations (14 out of 18)**
✅ **Changing hidden station counts has no effect**

## How to Verify

Run the test:
```bash
python test_validation_filters_hidden.py
```

Expected output:
```
✅ TEST PASSED
• 5 tests in input
• 3 tests with real stations
• 2 tests with hidden stations (filtered to None)
• Hidden stations successfully excluded from tests_info ✓
```

## Tests in Your Model

Based on the error (r20, r21), you have at least 2 tests in your Tests sheet that reference hidden stations. These tests will now:
- Have their Station set to None internally
- Not cause validation errors
- Be skipped during scheduling (since they have no valid station)

This is the correct behavior - these tests are flow markers, not actual test operations.
