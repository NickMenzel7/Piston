# Menu Bar Redesign - Capacity Estimator Separation

## Summary

The Capacity Estimator has been moved from the main toolbar to a dedicated **Tools** menu to clearly separate it from the main window's test plan workflow.

## Problem Solved

**Before:**
- "Capacity Estimator" button was in the main toolbar alongside "View StationMap", "View NonTestGroups", etc.
- Made it seem like part of the main window's workflow
- Confusing because Capacity Estimator is for users **without a test plan yet**

**After:**
- Capacity Estimator moved to **Tools → Capacity Estimator** menu
- Main toolbar now only contains "View" buttons related to the test plan workflow
- Clear separation: menu = standalone tools, toolbar = main workflow actions

## New Menu Bar Structure

```
┌─────────────────────────────────────────────┐
│ Tools   Help                                 │  ← New menu bar
├─────────────────────────────────────────────┤
│ [View StationMap] [View NonTestGroups] ...  │  ← Existing toolbar (Capacity Estimator removed)
│ [VXG 54GHz ▼] [Variant 1 ▼]                 │
├─────────────────────────────────────────────┤
│ Run Controls                                 │
│ ...                                          │
└─────────────────────────────────────────────┘
```

### Tools Menu
- **Capacity Estimator** - Opens standalone capacity estimation window (no test plan required)

### Help Menu
- **About Piston** - Shows version and description

## Visual Design

The menu bar uses dark theme styling to match the rest of the application:
- **Background**: `#252526` (medium dark grey)
- **Text**: `#d4d4d4` (light grey)
- **Active/Hover**: `#094771` (blue highlight)
- **Flat relief**: Modern, clean appearance

## User Workflow

### Main Window (Test Plan-Based)
1. Select project from dropdown
2. Select variant
3. Set channel quantities and mode
4. Click **Calculate**
5. View results

**Supporting actions (toolbar):**
- View StationMap
- View NonTestGroups
- Inspect Dependencies

### Capacity Estimator (No Test Plan Required)
1. Go to **Tools → Capacity Estimator**
2. Opens separate window
3. Set ET pattern counts and test times
4. Enter number of units
5. Click **Calculate**

## Benefits

✅ **Clear separation**: Menu items = standalone tools, toolbar = workflow actions  
✅ **No confusion**: Capacity Estimator is clearly "separate" from main window  
✅ **Professional**: Standard menu bar pattern everyone understands  
✅ **Scalable**: Easy to add more tools or help items later  
✅ **Clean layout**: Doesn't clutter the main canvas  

## Future Enhancements

The menu structure allows easy addition of:

**Tools Menu:**
- Export Results to CSV
- Import/Export Configurations
- Additional planning utilities

**Help Menu:**
- User Guide
- Smart Mode Documentation
- Keyboard Shortcuts
- Check for Updates

## Files Changed

- **Piston.py** (lines ~748-787):
  - Added menu bar creation with dark theme styling
  - Created Tools menu with Capacity Estimator command
  - Created Help menu with About dialog
  - Removed "Capacity Estimator" button from toolbar
  - Updated comments to reflect new structure

## Code Details

### Menu Bar Creation
```python
menubar = tk.Menu(self, bg='#252526', fg='#d4d4d4', 
                 activebackground='#094771', activeforeground='#ffffff',
                 relief='flat', borderwidth=0)

# Tools menu for standalone utilities
tools_menu = tk.Menu(menubar, tearoff=0, 
                    bg='#252526', fg='#d4d4d4',
                    activebackground='#094771', activeforeground='#ffffff',
                    relief='flat', borderwidth=1)
tools_menu.add_command(label="Capacity Estimator", 
                      command=lambda: open_manual_et_allocator(self))
menubar.add_cascade(label="Tools", menu=tools_menu)

self.config(menu=menubar)
```

### Updated Toolbar (Capacity Estimator Removed)
```python
toolbar = ttk.Frame(header)
toolbar.grid(row=0, column=0, sticky='w')
ttk.Button(toolbar, text="View StationMap", command=lambda: self._safe_call('view_stationmap')).pack(side='left', padx=(0,4))
ttk.Button(toolbar, text="View NonTestGroups", command=lambda: self._safe_call('view_nontest')).pack(side='left', padx=4)
ttk.Button(toolbar, text="Inspect Dependencies", command=lambda: self._safe_call('view_dependency_debug')).pack(side='left', padx=4)
```

## Testing

Verify:
1. **Menu bar appears** at the top of the window
2. **Tools menu** contains "Capacity Estimator"
3. **Help menu** contains "About Piston"
4. **Capacity Estimator button** is removed from toolbar
5. **Menu styling** matches dark theme
6. **Clicking Tools → Capacity Estimator** opens the window
7. **About dialog** shows correct information

## User Communication

When releasing this change, communicate:
- **Where to find Capacity Estimator**: "Moved to Tools menu for clarity"
- **Why**: "Capacity Estimator is a standalone tool for early-stage planning (no test plan required)"
- **Workflow**: "Use main window for test plan-based calculations, use Tools → Capacity Estimator for preliminary capacity estimates"
