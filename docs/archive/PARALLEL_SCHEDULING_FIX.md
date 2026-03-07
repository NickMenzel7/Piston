# Parallel Scheduling Fix

## Problem
When testing VXG 54GHz Variant 1:
- 1 unit correctly calculated as 122 hours
- 10 units with 20 of each station (fully dedicated - enough for each unit) incorrectly showed 1000 hours instead of ~122 hours

The scheduler was artificially serializing units even when there were enough stations for each unit to run independently in parallel.

## Root Cause
Two issues were causing unnecessary serialization:

1. **Unit Bias**: The scheduler applied a `unit_bias` value that added an artificial priority penalty to later units. This caused Unit 2 to wait for Unit 1, Unit 3 to wait for Unit 2, etc., even when they had their own dedicated machines.

2. **Enforce Serialization Flag**: The `enforce_unit_serialization` flag was hardcoded to `True` regardless of resource availability, forcing cross-unit serialization even in fully-dedicated scenarios.

## Solution
Modified `piston_core/scheduler.py` to:

1. **Detect Fully-Dedicated Mode**: Check if each referenced station has at least `n_units` machines available. When true, resources are abundant enough for parallel execution.

2. **Disable Unit Bias When Fully Dedicated**: Set `unit_bias_val = 0.0` when fully dedicated (even if user explicitly requested bias), since bias is only useful for managing contended resources.

3. **Disable Cross-Unit Serialization When Fully Dedicated**: 
   - In `'Auto'` mode (default): `enforce_unit_serialization = not fully_dedicated`
   - In `'Strict'` mode: Always serialize (legacy behavior)
   - In `'Relaxed'` mode: Never serialize (experimental)

## Results
With the fix:
- **1 unit, 2 stations**: 122 hours ✓ (correct)
- **10 units, 20 stations** (fully dedicated): 122 hours ✓ (parallel execution, correct)
- **10 units, 2 stations** (contended): Higher makespan ✓ (serialization due to resource contention, correct)

## User Experience
**No manual adjustments needed!** The scheduler now automatically detects when resources are abundant and enables parallel execution. Users don't need to:
- Fiddle with unit bias settings
- Change serialization mode
- Understand complex scheduling parameters

The algorithm "just works" - giving you ~122 hours for 10 units when you have enough stations, as expected.

## Testing
Created comprehensive tests:
- `test_parallel_fix.py`: Simple 3-test scenario
- `test_realistic_parallel.py`: 25-test scenario (similar to VXG)
- All existing scheduler tests pass

## Files Modified
- `piston_core/scheduler.py`: Core scheduling algorithm fix

## Backwards Compatibility
- Default behavior improved (no breaking changes)
- Advanced users can still use `serialization_mode='Strict'` to force serialization if needed
- All existing tests pass
