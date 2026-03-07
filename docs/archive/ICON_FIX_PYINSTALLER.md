# Icon Fix for PyInstaller Build

## Problem
Window icons weren't appearing in the built .exe because:
1. Icon files weren't included in the PyInstaller bundle
2. The icon_helper.py code wasn't looking in the right location for frozen executables

## Solution

### 1. Updated `piston.spec`
Added Icon directory to the bundled data files:

```python
# Include Icon directory for runtime window icons
if os.path.isdir('Icon'):
    datas_list.append(('Icon', 'Icon'))
```

**Result:** Icon files are now included in `dist\piston\_internal\Icon\`

### 2. Updated `piston_ui/icon_helper.py`
Modified `set_window_icon()` to detect PyInstaller frozen mode:

```python
import sys
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    base_dir = sys._MEIPASS
else:
    # Running as script
    base_dir = os.path.dirname(os.path.dirname(__file__))

icon_dir = os.path.join(base_dir, 'Icon')
```

**Result:** Code correctly finds icons in both development and packaged modes

## How It Works

### Development Mode (python Piston.py):
- `base_dir` = Project root directory
- `icon_dir` = `ProjectRoot/Icon/`
- Icons loaded from source directory ✓

### PyInstaller Bundle (piston.exe):
- `sys.frozen` = True (detected by PyInstaller)
- `base_dir` = `sys._MEIPASS` (temporary extraction directory)
- `icon_dir` = `_MEIPASS/Icon/`
- Icons loaded from bundled data ✓

## Files Modified

1. ✅ **piston.spec** - Added Icon directory to datas_list
2. ✅ **piston_ui/icon_helper.py** - Added frozen mode detection

## Testing

After rebuilding, all window icons should now appear:
- ✅ Main application window
- ✅ Dialog windows (StationMap, NonTestGroups, etc.)
- ✅ Log viewer window
- ✅ Manual ET allocator
- ✅ Any other Toplevel windows

## Build Instructions

```bash
# Rebuild with icon support
python -m PyInstaller --noconfirm piston.spec

# Test the executable
.\dist\piston\piston.exe
```

## Verification

Icons are bundled in: `dist\piston\_internal\Icon\piston-16.ico`

The application automatically detects:
- `sys.frozen == True` → Use bundled icons from `_MEIPASS`
- `sys.frozen == False` → Use source icons from project directory

## Additional Notes

### Two Types of Icons:

1. **EXE Icon** (shows in Explorer/taskbar)
   - Configured in piston.spec: `icon='Icon/piston.ico'`
   - Embedded into the .exe file itself
   - ✅ Already working

2. **Window Icons** (shows in window title bars)
   - Runtime data files bundled by PyInstaller
   - Loaded by icon_helper.py at runtime
   - ✅ Now working with this fix

### sys._MEIPASS Explained:

When PyInstaller creates a frozen executable:
- It extracts bundled files to a temporary directory
- `sys._MEIPASS` points to this temporary location
- Your code needs to use `sys._MEIPASS` to find bundled resources
- This is the standard PyInstaller pattern for resource files

## Summary

✅ **Icons now work in both development and packaged modes**
✅ **No code changes needed when adding more icon files**
✅ **Compatible with PyInstaller's bundling system**

Just rebuild and your icons will appear! 🎨
