# Distribution Checklist

## ✅ Ready to Share: YES

### What to Distribute:

**Option 1: ZIP File (Recommended)**
```
Piston_v1.0.zip
└── Contains: dist\piston\ folder with all contents
```

**Option 2: Network Share**
```
\\server\apps\Piston\
└── Copy entire dist\piston\ folder
```

### Files Included:

✅ **piston.exe** (8.3 MB) - Main executable  
✅ **_internal/** - All dependencies (~200 MB)  
✅ **_internal/embedded/default_model.xlsx** - Default data  
✅ **_internal/Icon/piston.ico** - Application icon  
✅ **README_USERS.md** - User documentation  

### Features Verified:

✅ No console window (windowed mode)  
✅ Multi-size icon embedded  
✅ Debug log viewer (Help menu)  
✅ Hidden stations filtered  
✅ All core functionality working  

## Distribution Steps:

### 1. Create ZIP (Manual):
```powershell
# In File Explorer:
1. Navigate to C:\Users\Nichmenz\Piston\dist\
2. Right-click the "piston" folder
3. Send to → Compressed (zipped) folder
4. Rename to: Piston_v1.0.zip
```

### 2. Or Use 7-Zip/WinRAR (Better):
- Creates smaller archives
- Better compression
- Recommended for distribution

### 3. Test the ZIP:
1. Extract to a new location (e.g., Desktop\Test\)
2. Run piston.exe
3. Verify it works

### 4. Share:
- Email (if < 25MB after compression)
- Network share
- Cloud storage (OneDrive, Google Drive, etc.)
- Internal file server

## User Instructions:

**Send users this simple message:**

```
Piston v1.0 Installation:

1. Extract the ZIP file to your desired location
   (e.g., C:\Program Files\Piston\)

2. Double-click piston.exe to run

3. No installation needed - it's portable!

4. See README_USERS.md for detailed instructions

Note: Keep the _internal folder - don't delete it!
```

## Important Notes:

### DO Include:
- ✅ Entire `dist\piston\` folder
- ✅ README_USERS.md
- ✅ All files in `_internal\`

### DON'T Include:
- ❌ Source code (.py files) - not needed
- ❌ build folder - build artifacts only
- ❌ test files - not needed by users
- ❌ .git folder - version control
- ❌ Development dependencies

## Testing Before Distribution:

### Quick Test:
```powershell
# Copy to a test location
Copy-Item "dist\piston" "C:\Temp\PistonTest" -Recurse

# Run from test location
cd C:\Temp\PistonTest
.\piston.exe
```

### Verify:
- ✅ Application launches
- ✅ No console window
- ✅ Icon appears
- ✅ Default model loads
- ✅ Can run calculations
- ✅ Help → View Debug Log works

## Security Notes:

### Antivirus:
- PyInstaller executables may trigger false positives
- This is normal for packed Python applications
- If flagged, submit to antivirus company as false positive
- Or have IT whitelist the application

### Code Signing (Optional but Recommended):
For professional distribution, consider code signing:
- Prevents "Unknown Publisher" warnings
- Requires a code signing certificate (~$200-500/year)
- Tools: SignTool.exe (Windows SDK)

## Version Control:

**Current Version:** 1.0  
**Build Date:** March 6, 2026  
**Last Build:** 6:51 PM  

**For Future Updates:**
1. Update version in README_USERS.md
2. Rebuild: `pyinstaller --noconfirm piston.spec`
3. Create new ZIP: `Piston_vX.X.zip`
4. Distribute update

## Summary:

🎉 **Your application is READY TO SHARE!**

**What users need:**
- The `dist\piston\` folder (zipped)
- README_USERS.md for instructions

**What they do:**
1. Extract ZIP
2. Run piston.exe
3. Start using!

**No installation, no dependencies, no hassle!** ✅
