# Quick Reference: No Console Window Launch

## Summary of Changes

### Files Modified:
1. ✅ **piston.spec** - Set `console=False` for windowed mode
2. ✅ **Piston.py** - Made console logging optional, added log viewer
3. ✅ **build_windows.ps1** - Updated to use piston.spec

## Before vs After

### Before:
```
Launch Piston → Two windows appear:
  1. Console window (with logging output)
  2. Main GUI window
```

### After:
```
Launch Piston → One window appears:
  ✓ Main GUI window only
  ✓ Logs saved to piston_debug.log
  ✓ View logs: Help → View Debug Log
```

## How to Build

### Option 1: Using piston.spec (Recommended)
```bash
pyinstaller piston.spec
```
**Result:** `dist/piston/piston.exe` - No console window ✓

### Option 2: Using build script
```bash
# Windows
.\build_windows.ps1

# Linux/Mac
./build_unix.sh
```

## How to View Logs

### In the Application:
1. Launch Piston
2. Click `Help` menu
3. Click `View Debug Log`
4. Browse logs in the built-in viewer

### Direct File Access:
- Log file: `piston_debug.log` (same directory as exe/py file)
- Open with any text editor

## Development Mode

### Enable Console Logging (Optional)
When developing and you want to see console output:

**Windows:**
```bash
set PISTON_DEBUG_CONSOLE=1
python Piston.py
```

**Linux/Mac:**
```bash
export PISTON_DEBUG_CONSOLE=1
python Piston.py
```

**Result:** Console output enabled for debugging

## Testing the Fix

### Quick Test:
1. Build: `pyinstaller piston.spec`
2. Run: `dist\piston\piston.exe`
3. **Expected:** Only GUI window appears ✓
4. Check: `Help → View Debug Log` works ✓

### Verify Logging:
1. Launch Piston
2. Load a model
3. Run a calculation
4. `Help → View Debug Log`
5. **Expected:** Log entries visible with timestamps ✓

## What Changed Technically

### Logger Behavior:
**Before:**
- FileHandler: ✓ (piston_debug.log)
- StreamHandler: ✓ (console output) ← Caused console window

**After:**
- FileHandler: ✓ (piston_debug.log)
- StreamHandler: ⚠ (only if PISTON_DEBUG_CONSOLE=1)

### PyInstaller Build:
**Before:**
```python
console=True  # Console window appears
```

**After:**
```python
console=False  # No console window
```

## Benefits

✅ Professional, clean user experience
✅ Single window launch
✅ Full logging maintained
✅ Built-in log viewer
✅ Developer debugging still available

---

**Need help?** Check `CONSOLE_WINDOW_FIX.md` for detailed documentation.
