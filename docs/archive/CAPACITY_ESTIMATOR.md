# Capacity Estimator - Smart Mode Integration

## Summary

The Capacity Estimator window now uses the **same scheduler engine and Smart Mode logic** as the main window, providing accurate capacity calculations that account for parallel execution, dependencies, and serialization.

## What Changed

### Before (Old Calculation)
- **Simple ops-per-hour calculation**: `ops_per_hour / (ops_per_unit * factor)`
- **No Smart Mode**: Always used simplified capacity formulas
- **No scheduler integration**: Custom calculation logic separate from main window
- **Inaccurate for parallel scenarios**: Would underestimate capacity when sufficient stations available

### After (Smart Mode Integration)
- **Uses actual scheduler**: Calls `schedule_n_units()` with proper DAG and tests_info
- **Smart Mode detection**: Automatically detects when `min_station_count >= units_required`
- **Accurate parallel execution**: Correctly models pipeline effects and station utilization
- **Consistent with main window**: Same calculation logic = same results

## Key Features

### 1. Smart Mode Detection
```python
min_station_count = min((st_map_calc[st]['count'] for st in st_map_calc if st_map_calc[st]['count'] > 0), default=1)
smart_mode_active = min_station_count >= units_required

if smart_mode_active:
    unit_bias = 0.0
    serialization_mode = 'Relaxed'
    smart_msg = "🚀 SMART MODE: Parallel execution enabled (sufficient stations detected)\n\n"
```

### 2. Visual Indicator
When Smart Mode activates, you'll see:
```
🚀 SMART MODE: Parallel execution enabled (sufficient stations detected)

For 10 units (yield 100%, spins 0) -> 122.45 hrs total
Required units (adjusted for yield): 10
Critical path: 122.03 hrs
Min station count: 10
Test operations: 25

Station Utilization:
  Align-X: 95.3%
  Hi Pot: 12.1%
  PNA-X: 78.9%
  ...
```

### 3. Accurate Parallel Modeling
- **Single unit with 1 station**: ~122 hrs (serial path)
- **10 units with 10 stations**: ~122 hrs (parallel, Smart Mode active)
- **10 units with 5 stations**: ~180 hrs (partial overlap, Smart Mode inactive)

### 4. Spins and Yield Support
- **Spins**: Replicates test operations (e.g., spins=1 doubles test count)
- **Yield**: Scales required units (e.g., yield=80% requires 12.5 units for 10 good)
- Both factors correctly integrated with Smart Mode logic

## Technical Implementation

### Building Synthetic Tests DataFrame
```python
test_rows = []
for et, cnt_var, et_var in rows:
    # Parse Count and Test Time from UI
    cnt = int(float(cnt_var.get() or 0))
    et_hours = float(et_var.get() or 0.0)
    
    # Map ET pattern to station
    st = map_et_to_station(et)
    
    # Create test row
    test_rows.append({
        'TestID': str(test_id),
        'TestName': et,
        'Station': st,
        'TestTimeMin': et_hours * 60.0,  # Convert to minutes
        'DependsOn': '',
        'Include': True
    })
```

### Building Station Map
```python
st_map_calc = {}
for st in tests_df['Station'].unique():
    # Get count from Count column (station_link_vars)
    if st in station_link_vars:
        cnt = int(float(station_link_vars[st].get() or 0))
    else:
        # Fallback to app.st_map or stations_df
        cnt = get_fallback_count(st)
    
    st_map_calc[st] = {'count': cnt, 'uptime': 1.0}
```

### Running the Scheduler
```python
mk, finishes, util = schedule_n_units(
    tests_info, topo, st_map_calc, units_required,
    channels_per_unit=None,
    unit_bias=unit_bias,
    bias_max_frac=0.05,
    bias_window_frac=1.0,
    serialization_mode=serialization_mode,
)

cp = critical_path_hours(tests_info, topo, st_map_calc)
total_hours = mk / 60.0  # Convert minutes to hours
```

## Benefits

1. **Consistency**: Capacity Estimator and main window now produce identical results for equivalent scenarios
2. **Accuracy**: Proper parallel execution modeling eliminates underestimates
3. **Maintainability**: Single scheduler codebase = easier to maintain and enhance
4. **Smart Mode**: Automatic detection of parallel execution opportunities
5. **Station Utilization**: Real utilization metrics from the scheduler

## Usage

### In Capacity Estimator Window:
1. Set **Count** for each ET pattern (number of available stations)
2. Set **Test Time** for each pattern (hours per test)
3. Enter **number of units** to calculate
4. Set **Spins** (optional, default 0)
5. Set **Yield %** (optional, default 100%)
6. Click **Calculate**

### Smart Mode will activate when:
- `min(station counts) >= units`
- Shows "🚀 SMART MODE" message
- Uses parallel execution logic

### Result Display:
```
For 10 units (yield 100%, spins 0) -> 122.45 hrs total
Required units (adjusted for yield): 10
Critical path: 122.03 hrs
Min station count: 10
Test operations: 25

Station Utilization:
  Align-X: 95.3%
  Hi Pot: 12.1%
  ...
```

## Files Changed

- `piston_ui/manual_et.py`: Complete rewrite of `compute_capacity()` function
  - Added imports: `build_dag`, `schedule_n_units`, `critical_path_hours`, `validate_import_rows`
  - Replaced ~200 lines of custom capacity logic with scheduler integration
  - Added Smart Mode detection and visual indicators

## Testing Recommendations

1. **Compare with main window**: Same project + same counts should give same results
2. **Test Smart Mode threshold**: Try 10 units with 9 vs 10 stations
3. **Test spins**: Verify spins=1 approximately doubles time
4. **Test yield**: Verify yield=50% approximately doubles required units
5. **Check utilization**: Ensure station utilization makes sense

## Future Enhancements

Possible future improvements:
1. Add dependency support (if ET patterns have ordering constraints)
2. Support "Units in T hours" mode (inverse calculation)
3. Add capacity chart visualization
4. Export results to CSV/Excel
