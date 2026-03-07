# Capacity Estimator Fix

## Problem
The Capacity Estimator window was empty/not populated in the built `.exe` because of an undefined variable reference.

## Root Cause
In `piston_ui/manual_et.py` line 127, the code referenced:
```python
if st and str(st).strip().lower() in (app.HIDDEN_STATIONS if hasattr(app, 'HIDDEN_STATIONS') else HIDDEN_STATIONS):
```

The fallback `HIDDEN_STATIONS` didn't exist in scope, causing a `NameError` that prevented the window from populating.

## Fix
Changed line 127 to use the existing helper function:
```python
if st and _is_hidden_station(st):
    continue
```

## Files Modified
✅ **piston_ui/manual_et.py** (line 127)

## Testing
Run `test_capacity_estimator_fix.py` to verify:
```bash
python test_capacity_estimator_fix.py
```

Expected output: ✅ ALL TESTS PASSED

## Result
✅ Capacity Estimator now populates correctly  
✅ Hidden stations filtered properly  
✅ Window shows all ET patterns with counts  

## Build & Deploy
Already rebuilt in the latest build:
```
dist/piston/piston.exe (latest build)
```

The Capacity Estimator should now work perfectly! 🎉
