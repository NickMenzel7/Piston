# Testing Checklist for Refactored Code

**Before rebuilding the .exe, test the refactored Python code:**

---

## ✅ Quick Smoke Test

```powershell
python Piston.py
```

**Expected:** GUI launches without console errors

---

## 🧪 Feature Testing

### Core Features:
- [ ] **App launches** - No exceptions in console
- [ ] **Project dropdown** - Shows all 6 projects
- [ ] **Variant dropdown** - Shows Variant 1, 2, 3, Average
- [ ] **Stations view** - Displays all stations with counts
- [ ] **Tests view** - Displays all tests with dependencies

### Project Management:
- [ ] **Switch project** - Dropdown changes, Tests update
- [ ] **Switch variant** - Variant 1/2/3 changes data
- [ ] **Average variant** - Calculates averaged times
- [ ] **Auto-load** - VXG 54GHz loads at startup

### Calculation:
- [ ] **Time for N mode** - Set N=10, click Calculate
- [ ] **Units in T mode** - Set T=130, click Calculate
- [ ] **Smart Mode** - Activates with sufficient stations
- [ ] **Channel quantities** - Single/Dual/Quad respected
- [ ] **Spins** - Affects total time
- [ ] **Yield** - Affects completion count

### Station Editing:
- [ ] **Double-click station** - Opens inline editor
- [ ] **Edit count** - Press Enter, value updates
- [ ] **Calculate** - Uses new count

### Tools Menu:
- [ ] **Capacity Estimator** - Opens, populates ET patterns
- [ ] **View StationMap** - Shows mapping rules
- [ ] **View NonTestGroups** - Shows groups
- [ ] **Inspect Dependencies** - Shows dependency tree

### Help Menu:
- [ ] **View Debug Log** - Opens log file
- [ ] **About Piston** - Shows version info

---

## ⚠️ Known Issues to Check

### Watch For:
1. **Import errors** - Module not found
2. **AttributeError** - Missing app attributes
3. **Calculate fails** - Check console for exceptions
4. **Empty results** - Calculation returns nothing

### If Issues Found:
1. Check console output for exceptions
2. Check `piston_debug.log`
3. Report issue with stack trace
4. Can rollback using backup `dist/`

---

## ✅ If All Tests Pass:

```powershell
# Rebuild with refactored code
python -m PyInstaller --noconfirm piston.spec
```

Then test the .exe:
```powershell
.\dist\piston\piston.exe
```

---

## 🚨 If Tests Fail:

1. **Note the error** - Copy console output
2. **Check log** - Open piston_debug.log
3. **Report issue** - Provide error details
4. **Use backup** - Working dist/ from 1:07 PM

---

## Quick Test Script

Run this to test major features quickly:

```powershell
python -c "
from Piston import PlannerApp
app = PlannerApp()

# Test imports
print('✓ App created')
print(f'✓ Projects: {len(app.project_plans)}')
print(f'✓ Selected: {app.project_var.get()}')

# Quick checks
assert len(app.project_plans) >= 6, 'Missing projects'
assert hasattr(app, 'calculate'), 'Missing calculate method'
assert hasattr(app, 'st_tree'), 'Missing stations tree'
assert hasattr(app, 'tests_tree'), 'Missing tests tree'

print('✓ All quick checks passed!')
app.quit()
"
```

---

**Status:** ✅ Code compiles, ready for testing!
