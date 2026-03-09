# Channel Configuration Migration

## Overview

**Date**: 2025-01-XX
**Issue**: Multi-channel unit calculations were inaccurate because pre-channel testing (Align-X) tests vary between configurations
**Solution**: Move from channel multipliers to explicit per-configuration projects

## Problem Statement

Previously, Piston calculated multi-channel units by:
1. Taking a base test plan (e.g., "VXG 54GHz")  
2. Multiplying by channel quantities (Single/Dual/Quad spinboxes)
3. Applying channel multipliers in the scheduler

This approach had a **critical flaw**: 
- Pre-channel tests (Align-X, calibration, etc.) have different sequences for single vs dual vs quad channel units
- Simple multiplication doesn't account for these differences
- Results were inaccurate for multi-channel configurations

## Solution

Create **explicit project plans for each channel configuration**:
- `VXG 54GHz Single Channel` - Complete test plan with single-channel pre-tests
- `VXG 54GHz Dual Channel` - Complete test plan with dual-channel pre-tests  
- `VXG 54GHz Quad Channel` - Complete test plan with quad-channel pre-tests

This gives accurate test times because each project includes the **actual tests** that will run for that configuration.

## Code Changes

### 1. Removed UI Controls (`Piston.py`)
**Removed**:
- `self.single_var`, `self.dual_var`, `self.quad_var` (StringVar declarations)
- Channel Quantities section from Run Controls (Single/Dual/Quad spinboxes)
- Channel quantity validation in `_validate_controls()`
- Spinbox event bindings

**Why**: Channel configuration is now selected via project dropdown, not quantity spinboxes

### 2. Simplified Calculation Logic (`piston_ui/calculate.py`)
**Changed**:
- `_build_channels_spec_validated()` now always returns `1` (no multiplier)
- `_parse_n_req()` removed channel quantity fallback for `units_in_t` mode
- Removed import of `build_channels_spec` from `channels_helper`

**Why**: Each project's test plan already includes the correct channel-specific tests

### 3. Preserved for Future Use
**Kept** (but currently unused):
- `piston_ui/channels_helper.py` - May be useful for other features
- `self.channels_var` - Freeform channel spec (backwards compatibility)

## Migration Guide

### For Users
1. **Before**: Select "VXG 54GHz", enter quantities (e.g., Single=5, Dual=3)
2. **After**: Select "VXG 54GHz Dual Channel", enter N=8 units

### For Test Plan Authors  
1. Create separate plan files for each configuration:
   ```
   plans/VXG_54GHz_Single_Channel/variant1.xlsx
   plans/VXG_54GHz_Dual_Channel/variant1.xlsx
   plans/VXG_54GHz_Quad_Channel/variant1.xlsx
   ```

2. Each plan should include **all tests** for that configuration:
   - Pre-channel tests (Align-X with correct channel count)
   - Main test sequence  
   - Post-processing tests

3. Ensure `Station` assignments match the model's StationMap

## Benefits

✅ **Accuracy**: Correct test times for each channel configuration  
✅ **Flexibility**: Can model configuration-specific test differences  
✅ **Simplicity**: Cleaner UI with fewer inputs  
✅ **Maintainability**: Explicit plans are easier to validate and update

## Testing

### Verify the changes work correctly:

1. **Load Projects**:
   - Ensure new projects appear in dropdown (e.g., "VXG 54GHz Single Channel")
   - Verify old projects with channel quantities still work (legacy compatibility)

2. **Calculate Time for N**:
   ```
   Project: VXG 54GHz Dual Channel
   Mode: Time to finish N units
   N: 10
   → Should show accurate time including dual-channel pre-tests
   ```

3. **Compare Results**:
   - Run same configuration with old method (if available)
   - Verify new method accounts for pre-channel test differences

4. **Check Logs**:
   ```
   Look for: "Channel config is per-project, using channels_spec=1"
   Should NOT see: Channel multiplier warnings
   ```

## Rollback Plan

If issues occur:
1. Restore previous `Piston.py` from git history
2. Restore previous `piston_ui/calculate.py`  
3. Re-enable channel quantity spinboxes in UI

## Future Enhancements

Potential improvements:
1. Auto-detect channel configuration from project name  
2. Validation warnings if project name doesn't match test plan structure
3. UI hints showing detected channel configuration  
4. Migration tool to convert old plans to new structure

## References

- Issue: Pre-channel (Align-X) tests not factored correctly
- Solution: Per-configuration projects with explicit test plans
- Files Changed: `Piston.py`, `piston_ui/calculate.py`
- Files Preserved: `piston_ui/channels_helper.py` (for future use)
