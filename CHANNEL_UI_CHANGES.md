# Channel Configuration UI Changes - Visual Guide

## Before (Channel Multiplier Approach)

### UI Layout
```
┌─────────────────────────────────────────────────────────────┐
│ Run Controls                                                │
├─────────────────────────────────────────────────────────────┤
│  Channel Quantities  │  Mode & Inputs  │  Actions          │
│  ┌──────────────┐    │                 │                   │
│  │ Single │ 5   │    │ ○ Time for N    │  [Calculate]      │
│  │ Dual   │ 3   │    │ ○ Units in T    │                   │
│  │ Quad   │ 2   │    │                 │                   │
│  └──────────────┘    │ N: [10]         │                   │
│                      │ T: [24]         │                   │
└─────────────────────────────────────────────────────────────┘
```

### User Workflow
1. Select base project: **"VXG 54GHz"**
2. Enter channel quantities: Single=5, Dual=3, Quad=2
3. Enter N=10 units
4. Click Calculate

### Issues
- ❌ Multiplier doesn't account for pre-channel test differences
- ❌ Align-X calibration varies by channel configuration  
- ❌ Inaccurate results for multi-channel units
- ❌ Confusing: "Why are there 10 boxes if I entered 10 units?"

---

## After (Per-Configuration Projects)

### UI Layout
```
┌─────────────────────────────────────────────────────────────┐
│ Run Controls                                                │
├─────────────────────────────────────────────────────────────┤
│  Mode & Inputs                      │  Actions              │
│                                     │                       │
│  ○ Time to finish N units           │  [Calculate]          │
│  ○ Units completed in T hours       │                       │
│                                     │                       │
│  N: [10]    T: [24]                 │                       │
│  Spins: [0]  Yield %: [100]         │                       │
│                                     │                       │
└─────────────────────────────────────────────────────────────┘

Project: [VXG 54GHz Dual Channel ▼]  Plan: [Variant 1 ▼]
```

### User Workflow
1. Select configuration-specific project: **"VXG 54GHz Dual Channel"**
2. Enter N=10 units  
3. Click Calculate

### Benefits
- ✅ Accurate: Each project has correct pre-channel tests
- ✅ Simpler UI: Fewer input boxes
- ✅ Clearer: Project name indicates configuration
- ✅ Flexible: Can model config-specific test variations

---

## Calculation Comparison

### Before (Multiplier)
```python
# Base test plan: "VXG 54GHz"
# Tests: [Test1, Test2, Test3, ...]
# Time: 60 minutes per unit

# User enters: Dual=5 units
# Calculation: 
#   - Take base plan (60 min)
#   - Multiply by 2 channels → 120 min per unit
#   - Multiply by 5 units → 600 min total

# Problem: Doesn't account for dual-channel Align-X 
# which adds 15 extra minutes per unit!
# Actual time needed: 675 minutes (not 600)
```

### After (Explicit Plans)
```python
# Selected project: "VXG 54GHz Dual Channel"
# Tests: [AlignX_Dual, Test1, Test2, Test3, ...]
# Time: 75 minutes per unit (includes dual Align-X)

# User enters: N=5 units
# Calculation:
#   - Use explicit plan (75 min per unit)
#   - Multiply by 5 units → 375 min total

# Result: Accurate! Includes all dual-channel tests.
```

---

## Project Naming Convention

### Recommended Structure
```
plans/
├── VXG_54GHz_Single_Channel/
│   ├── variant1.xlsx
│   ├── variant2.xlsx
│   └── variant3.xlsx
├── VXG_54GHz_Dual_Channel/
│   ├── variant1.xlsx
│   ├── variant2.xlsx
│   └── variant3.xlsx
└── VXG_54GHz_Quad_Channel/
    ├── variant1.xlsx
    ├── variant2.xlsx
    └── variant3.xlsx
```

### File Contents
Each variant file should include:
- **All pre-channel tests** (Align-X with correct channel count)
- **Main test sequence**  
- **Post-processing tests**
- **Correct Station assignments** matching model's StationMap

---

## Migration Checklist

### For Development Team
- [x] Remove channel quantity UI controls (Single/Dual/Quad spinboxes)
- [x] Simplify channel spec logic (always return 1)
- [x] Update calculation logic (no multiplier)  
- [x] Create migration documentation
- [x] Create test script
- [ ] Create per-configuration project plans
- [ ] Test with real project data
- [ ] Update user documentation

### For Test Plan Authors
- [ ] Create single-channel project plans
- [ ] Create dual-channel project plans
- [ ] Create quad-channel project plans  
- [ ] Verify Station assignments match model
- [ ] Validate test times are accurate
- [ ] Test calculations with each configuration

### For QA
- [ ] Verify UI loads without errors
- [ ] Confirm channel controls removed
- [ ] Test calculations with new projects
- [ ] Compare results with expected values
- [ ] Verify backward compatibility (if needed)

---

## FAQ

### Q: Can I still use old plans with channel quantities?
**A**: Old plans should work but won't have accurate multi-channel timing. Migrate to per-configuration projects for accuracy.

### Q: What happens to the channels_helper.py module?
**A**: It's preserved for potential future use but currently unused. Always returns channels=1.

### Q: Do I need separate projects for every channel count?
**A**: Only for configurations you actually use. If you only run dual-channel, you only need the dual-channel project.

### Q: How do I know which project to select?
**A**: Project name should indicate configuration (e.g., "VXG 54GHz Dual Channel"). Select the one matching your test setup.

### Q: What if I need to test multiple configurations?
**A**: Run separate calculations for each configuration. This ensures accurate results for each.

---

## Technical Details

### Files Modified
- **Piston.py**: Removed channel quantity controls, updated UI layout
- **piston_ui/calculate.py**: Simplified channel spec logic, removed multiplier

### Files Preserved  
- **piston_ui/channels_helper.py**: Kept for future use (currently unused)

### Breaking Changes
- Channel quantity spinboxes removed from UI
- `build_channels_spec()` no longer used in calculations
- `single_var`, `dual_var`, `quad_var` removed from PlannerApp

### Backward Compatibility
- Old projects without channel suffix still work
- Legacy `channels_var` preserved (unused)
- No database schema changes needed
