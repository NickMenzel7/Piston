# Hidden Stations (Channel Markers) Fix

## Problem
The application had "channel markers" in the Stations sheet that were not actual test stations:
- Racer Channel
- VXG Channel
- Transfer EI (YS loading) / Transfer El (YS loading)
- YS Loading Gate / YS loading gate

These markers were causing multiple issues:
1. Appearing in the Stations list in the UI (cluttering the display)
2. Affecting capacity calculations (changing their count changed results)
3. Visible in the Station Map Window
4. **Causing validation errors** when tests (from Tests sheet) referenced them: 
   - Error: "Tests reference unknown stations: ['VXG Channel', 'YS Loading Gate']"

## Root Cause
Tests in the Tests sheet had "VXG Channel" or "YS Loading Gate" as their Station value. When these tests were loaded for scheduling:
1. The hidden stations were filtered out of `st_map` (so scheduler didn't know about them)
2. But tests still referenced them
3. Scheduler validation failed: "unknown stations"

## Solution
Implemented comprehensive filtering of hidden stations at **all** points where they might enter the system:

### 1. Centralized Hidden Stations List (Piston.py)
- Defined `HIDDEN_STATIONS` set with all channel marker variations
- Created `is_hidden_station()` helper function for consistent filtering
- Removed duplicate/incomplete definition

### 2. Core Data Loading (piston_core/io.py)
- **load_model()**: Filter hidden stations when creating `st_map`
  - st_map is the primary data structure used for calculations
  - Hidden stations are excluded from st_map entirely
  - This ensures they never affect capacity calculations

### 3. Plan to Tests Mapping (piston_core/mapping.py)
- **plan_to_tests_rows()**: Filter hidden stations from `stations_set`
  - Tests that reference hidden stations (e.g., "VXG Channel") will get `None` for their Station
  - This prevents validation errors when importing plans that reference channel markers
  - These tests are effectively treated as unmapped/invalid

### 4. Manual ET Handling (piston_core/mapping.py)
- **load_manual_et()**: Filter hidden stations from:
  - stations_set (used for mapping)
  - st_counts (station count dictionary)
  - Final st_map output

### 5. **Tests Info Building (piston_ui/validation_helper.py)** - **KEY FIX**
- **build_tests_info()**: Filter hidden stations when building scheduler inputs
  - Tests that reference hidden stations get `Station = None`
  - This fixes the validation error for tests loaded from Tests sheet
  - These tests won't cause "unknown station" errors in the scheduler

### 6. Validation (piston_ui/validation_helper.py)
- **find_invalid_tests()**: Don't flag hidden stations as validation errors
  - Tests referencing hidden stations are skipped (not flagged as errors)
  - They're treated as having unmapped stations

### 7. UI Display (piston_ui/stations_view.py)
- Already had filtering in place via `_is_hidden_station()` helper
- Station list tree view filters out hidden stations
- Manual ET overrides skip hidden stations

### 8. Station Map View (Piston.py)
- **view_stationmap()**: Filters hidden stations before displaying
- Users won't see channel markers in the Station Map dialog

### 9. Calculations (Piston.py)
- **calculate()**: Already filtering hidden stations when building displayed_map
- Ensures channel markers don't participate in scheduling

## Result
✅ Channel markers are now completely hidden from:
- Station list in UI
- Station Map Window
- All capacity calculations and scheduling
- Plan-to-Tests mapping (treated as unmapped)
- **Tests sheet processing** (filtered out before scheduling)

✅ **No more "unknown station" validation errors** when tests reference hidden stations

✅ Changing their count in the Excel file will have no effect on calculations

✅ Tests that reference hidden stations will have `Station = None` and won't cause errors

✅ Test verification shows:
- 18 stations in Stations sheet
- 14 stations in st_map (4 channel markers filtered out)
- All calculations use only the 14 real test stations
- Tests referencing "VXG Channel" or "YS Loading Gate" get Station=None (no errors)

## Testing
Run these test scripts to verify the filtering is working correctly:
- `test_hidden_stations.py` - Verifies st_map filtering
- `test_channel_exclusion.py` - Verifies scheduling calculations
- `test_plan_mapping_filters_hidden.py` - Verifies plan-to-tests mapping
- `test_validation_filters_hidden.py` - **Verifies Tests sheet filtering (key test for the fix)**
- `test_integration_hidden_stations.py` - Full integration test
