# Capacity Estimator Redesign

## Problem
The capacity estimator was producing incorrect results (1.03 hrs total when critical path was 19.8 hrs), indicating a fundamental issue with how tests were being scheduled.

## Root Cause
1. **Skipping tests with zero counts**: The original code required both `cnt > 0` and `et_hours > 0`, causing tests to be skipped even if they had time but zero count in the UI
2. **Complex fallback logic**: Overly complex station count lookup that could result in incorrect counts
3. **Smart Mode interference**: Smart Mode detection was overriding scheduler behavior inappropriately
4. **No validation**: No check to ensure at least one station had a positive count

## Solution - Redesigned to Match Main Window

### Key Changes:

1. **Simplified Test Creation**
   - Only check `et_hours > 0` (not count)
   - Skip unmapped stations entirely (don't create placeholder stations)
   - Use ET pattern name as TestID for clarity

2. **Fixed Station Count Handling**
   - Directly use `station_link_vars` (the Count column in UI)
   - No complex fallbacks to app.st_map or stations_df
   - Added validation: error if all counts are 0

3. **Removed Smart Mode**
   - Smart Mode was causing incorrect parallel execution
   - Now uses `serialization_mode='Auto'` (same as main window)
   - Let the scheduler handle resource management naturally

4. **Improved Error Handling**
   - Added `traceback.format_exc()` for better error diagnosis
   - Clear validation messages

5. **Better Result Display**
   - Show station counts in utilization output: `"ACLR-Test (6 stations): 33.4%"`
   - Show "Critical path (1 unit)" to clarify it's per-unit time
   - Show "Tests per unit" (excluding spins) and "Total test operations" (including spins)

### How It Works Now:

1. **User sets up capacity estimator:**
   - ET patterns with Test Time (hrs) > 0
   - Count column = number of stations available for each station type

2. **Synthetic test plan created:**
   - One test per ET pattern (if time > 0 and station mapped)
   - No dependencies between tests

3. **Scheduler called:**
   - `schedule_n_units(tests_info, topo, st_map_calc, units_required, ...)`
   - Each unit goes through ALL tests sequentially
   - Multiple units run in parallel based on station availability
   - Uses Auto serialization (same as main window)

4. **Results show:**
   - Total time for N units
   - Critical path (time for 1 unit)
   - Station utilization with counts
   - Tests per unit / Total operations

### Expected Results for User's Data:

With:
- ACLR-Test: 19.8 hrs, 6 stations
- High Power Cal: 0.9 hrs, 3 stations
- PNA-X: 14.7 hrs, 5 stations
- Peanuts Phase Noise: 0.6 hrs, 1 station
- X-Mod2: 1.5 hrs, 1 station
- 10 units, 0 spins, 100% yield

Expected total: ~40-60 hours (depending on how tests overlap)
- Critical path per unit: 37.5 hrs (sum of all tests)
- Bottleneck: Peanuts and X-Mod2 (only 1 station each)
- These stations must serialize all 10 units
- Other stations can run multiple units in parallel

## Testing Recommendations:

1. **Single unit, single test**: Should equal test time
2. **10 units, 1 test, 10 stations**: Should equal test time (full parallelism)
3. **10 units, 1 test, 1 station**: Should equal test time × 10 (fully serialized)
4. **Real scenario**: Should be between critical path and critical path × units
