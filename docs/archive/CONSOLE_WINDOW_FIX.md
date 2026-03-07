# Console Window Removal - Complete Guide

## Problem
When launching Piston, a console window (command window) appears showing all the logging output. This creates a cluttered user experience with two windows instead of one.

## Solution
We've implemented a comprehensive fix that:
1. ✅ Removes the console window entirely (windowed mode)
2. ✅ Keeps logging to file for debugging
3. ✅ Adds an in-app log viewer (Help → View Debug Log)
4. ✅ Makes console logging optional for development

## Changes Made

### 1. PyInstaller Spec File (`piston.spec`)
**Changed:**
```python
console=False,  # Was: console=True
```
**Added icon support:**
```python
icon='Icon/piston.ico' if os.path.exists('Icon/piston.ico') else None,
```

**Effect:** When building with PyInstaller, no console window will appear. Only the GUI window shows.

### 2. Logger Configuration (`Piston.py`)
**Changed:** Made console logging optional (environment variable controlled)

**Before:**
- Always logged to both file AND console (caused console window clutter)

**After:**
- Always logs to file: `piston_debug.log`
- Console logging only enabled if `PISTON_DEBUG_CONSOLE=1` environment variable is set

**Benefits:**
- Clean launch (no console window)
- Full debug logging still captured in file
- Developers can enable console output when needed

### 3. In-App Log Viewer (`Piston.py`)
**Added:** `Help → View Debug Log` menu item

**Features:**
- Shows last 10,000 lines of log file in a readable dialog
- Syntax-highlighted console font (Consolas)
- Dark theme matching the app
- "Open in Notepad" button for full file access
- "Refresh" button to reload log content
- Read-only text view (prevents accidental edits)

## Usage

### For End Users:
1. Launch Piston → Only the main window appears ✓
2. Logs are automatically saved to `piston_debug.log` in the app directory
3. View logs: `Help → View Debug Log`

### For Developers:
**Enable console logging during development:**
```bash
# Windows
set PISTON_DEBUG_CONSOLE=1
python Piston.py

# Linux/Mac
export PISTON_DEBUG_CONSOLE=1
python Piston.py
```

**Build without console window:**
```bash
pyinstaller piston.spec
```

## File Locations

### Debug Log Location:
- **Development:** Same directory as `Piston.py`
- **Packaged:** Same directory as `piston.exe`

**Example paths:**
- `C:\Program Files\Piston\piston_debug.log`
- `C:\Users\YourName\Piston\piston_debug.log`

## Testing

### Test 1: Verify Console is Hidden
```bash
# Build the application
pyinstaller piston.spec

# Run the .exe from dist/piston/
dist/piston/piston.exe
```
**Expected:** Only the GUI window appears, no console window ✓

### Test 2: Verify Logging Still Works
1. Launch Piston
2. Perform some actions (load model, run calculation)
3. `Help → View Debug Log`
4. **Expected:** Log content is visible with timestamps and messages ✓

### Test 3: Verify Console Logging (Development)
```bash
set PISTON_DEBUG_CONSOLE=1
python Piston.py
```
**Expected:** Console output appears (for debugging) ✓

## Troubleshooting

### Console Window Still Appears
**Cause:** Running the Python script directly
**Solution:** Build with PyInstaller: `pyinstaller piston.spec`

### Can't Find Log File
**Solution:** Use `Help → View Debug Log` menu - shows the exact path

### Log Viewer is Empty
**Cause:** No logging has occurred yet, or file doesn't exist
**Solution:** Perform some actions in the app (load model, calculate, etc.)

## Benefits

✅ **Clean user experience** - Only one window (the main app)
✅ **Professional appearance** - No console clutter
✅ **Full debugging capability** - All logs saved to file
✅ **Easy log access** - Built-in log viewer
✅ **Developer-friendly** - Optional console output for debugging

## Summary

The console window is now completely hidden for end users, while still maintaining full logging capability. Users can view logs through the built-in log viewer (`Help → View Debug Log`), and developers can enable console output when needed with an environment variable.

This creates a much cleaner, more professional user experience! 🎉
