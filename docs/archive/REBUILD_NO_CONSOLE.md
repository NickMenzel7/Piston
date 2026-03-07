# Quick Fix: Rebuild to Remove Console Window

## The Issue
You're seeing a console window because you're likely running one of:
- `python Piston.py` (Python script directly)
- An old `.exe` built before the changes

## The Solution
Build a new `.exe` with PyInstaller using the updated `piston.spec`:

### Step 1: Verify piston.spec is Updated
Check line 39 in `piston.spec`:
```python
console=False,  # Should be False, not True
```

### Step 2: Build the Executable
```bash
# Windows PowerShell
pyinstaller --noconfirm piston.spec

# This creates: dist\piston\piston.exe
```

### Step 3: Test the Built Executable
```bash
# Navigate to the build output
cd dist\piston

# Run the .exe (NOT the .py file)
.\piston.exe
```

**Expected Result:** Only the GUI window appears, no console! ✓

## Alternative: Quick Test Build

If you want to test without the full directory structure:

```bash
# Build as a single file (takes longer but creates one .exe)
pyinstaller --noconfirm --onefile --windowed --name piston Piston.py

# This creates: dist\piston.exe
dist\piston.exe
```

## Why You Still See Console

### If running Python directly:
```bash
python Piston.py  # ❌ Always shows console (Windows behavior)
```
**Python on Windows always opens a console window when running .py files**

### If running old .exe:
```bash
dist\piston\piston.exe  # ❌ If built before console=False change
```
**Need to rebuild after updating piston.spec**

### If running new .exe:
```bash
dist\piston\piston.exe  # ✅ No console (if built with console=False)
```
**This is what you want!**

## Verification Checklist

- [ ] Updated `piston.spec` to have `console=False` on line 39
- [ ] Ran `pyinstaller --noconfirm piston.spec`
- [ ] Testing the **built .exe** from `dist\piston\piston.exe`
- [ ] **NOT** running `python Piston.py` directly

## Build Script

You can also use the build script:
```bash
.\build_windows.ps1
```

This will use `piston.spec` automatically.

## Common Mistakes

### Mistake 1: Running Python Script
```bash
python Piston.py  # ❌ Console always shows
```
**Fix:** Run the built .exe instead

### Mistake 2: Old Build
```bash
# Built before updating piston.spec
dist\piston\piston.exe  # ❌ Still has console
```
**Fix:** Delete `dist` and `build` folders, rebuild

### Mistake 3: Wrong Directory
```bash
cd dist
python ..\Piston.py  # ❌ Running .py, not .exe
```
**Fix:** `.\piston\piston.exe`

## Full Rebuild Process

If you're still seeing the console, do a clean rebuild:

```powershell
# 1. Clean old builds
Remove-Item -Recurse -Force dist, build -ErrorAction SilentlyContinue

# 2. Build with updated spec
pyinstaller --noconfirm piston.spec

# 3. Test the new exe
.\dist\piston\piston.exe
```

## Expected Output

### Building:
```
> pyinstaller --noconfirm piston.spec
...
Building EXE from EXE-00.toc completed successfully.
```

### Running:
- ✅ Only GUI window opens
- ✅ No console window
- ✅ Help → View Debug Log works
- ✅ Logs saved to `piston_debug.log`

---

**TL;DR:** You need to **rebuild with PyInstaller** and run the **built .exe**, not the Python script directly!
