# Smart Mode - Automatic Parallel Execution

## What is Smart Mode?

Smart Mode is an **automatic** feature that detects when you have sufficient stations to run all units in parallel, and automatically disables serialization bias to give you the correct parallel execution time.

## How It Works

### Without Smart Mode (Old Behavior)
- **Problem**: 10 units with 10x stations → 1000 hours ❌
- Units were being artificially serialized even when sufficient resources existed

### With Smart Mode (New Behavior)
- **Solution**: 10 units with 10x stations → ~122 hours ✅
- Automatically detects: `min_station_count >= n_units`
- When detected, automatically sets:
  - `unit_bias = 0.0` (no serialization pressure)
  - `serialization_mode = 'Relaxed'` (true parallel)

## When Does Smart Mode Activate?

Smart Mode activates automatically when:

1. **Mode**: Time to finish N units
2. **Condition**: Minimum station count ≥ number of units
3. **User Settings**: Unit bias is empty (not manually overridden) AND Serialization = Auto

### Example Scenarios

| Units | Min Station Count | Smart Mode Active? | Expected Result |
|-------|-------------------|-------------------|-----------------|
| 1     | 1                | No (not needed)    | ~122 hrs        |
| 10    | 10               | ✅ Yes             | ~122 hrs        |
| 10    | 5                | No                 | Partial overlap |
| 20    | 10               | No                 | Partial overlap |

## Visual Indicator

When Smart Mode is active, you'll see this in the Calculation Results:

```
🚀 SMART MODE: Parallel execution enabled (sufficient stations detected)

Total test time for qty of selected units (hours): 122.5
...
```

## Manual Override

If you need different behavior, you can override Smart Mode by:

1. **Setting a manual unit bias** (e.g., 0.01) - Smart Mode won't override
2. **Changing Serialization mode** to "Strict" - Forces sequential execution
3. **Using "No pref" preset** - Clears all bias settings and uses scheduler defaults

## Advanced Controls

The advanced controls are still available if you need fine-tuning:

- **Unit bias (hrs)**: Manual serialization pressure (empty = Auto)
- **Max bias %**: Cap on bias influence (default 5%)
- **Bias window**: Temporal range for bias (default 1.0)
- **Serialization**: Auto | Strict | Relaxed

### When to Use Manual Controls

- **Strict mode**: Force sequential testing (quality gates, resource constraints)
- **Custom bias**: Fine-tune unit ordering for specific production scenarios
- **Testing "what-if"**: Simulate different resource allocation strategies

## FAQ

**Q: Will Smart Mode work for "Units completed in T hours" mode?**  
A: Yes! Smart Mode also works in that mode when it detects high station counts (≥5 per station type).

**Q: What if I have different station counts for different types?**  
A: Smart Mode uses the **minimum** station count across all active stations. If your bottleneck station has 10 units available for 10 units under test, Smart Mode activates.

**Q: Can I disable Smart Mode?**  
A: Yes, set any manual unit bias value (even 0.0) or change Serialization to "Strict" or "Relaxed".

**Q: Does Smart Mode affect station utilization?**  
A: No - station utilization still shows actual usage. Smart Mode only affects the timing/scheduling logic.

## Technical Details

Smart Mode works by:

1. **Pre-calculation detection**: Before scheduling, checks `min(all_station_counts) >= n_units`
2. **Automatic parameter override**: Sets bias=0.0, serialization='Relaxed'
3. **True parallel execution**: All units can start tests immediately without artificial delays
4. **User transparency**: Shows indicator in results + logs decision

This ensures you get the **expected** behavior (parallel = same time as 1 unit) without requiring manual parameter tuning.
