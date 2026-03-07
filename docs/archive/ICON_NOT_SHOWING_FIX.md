# Icon Not Showing - Troubleshooting Guide

## Problem
The icon doesn't show in Windows Explorer or taskbar, even after building.

## Root Cause
Your `piston-16.ico` file (1150 bytes) likely contains only one icon size (16x16). Windows needs **multiple sizes** in a single .ico file to display properly in different contexts.

## Solution: Create a Multi-Size Icon

### Option 1: Use Online Converter (Easiest)
1. Go to: https://convertico.com/ or https://icoconvert.com/
2. Upload your source image (PNG, JPG, or current .ico)
3. Select sizes: **16x16, 32x32, 48x48, 256x256**
4. Download the generated .ico file
5. Replace `Icon/piston-16.ico` with the new file
6. Rebuild: `python -m PyInstaller --noconfirm piston.spec`

### Option 2: Use GIMP (Free Software)
1. Download GIMP: https://www.gimp.org/downloads/
2. Open your image in GIMP
3. Export as `.ico`
4. In export dialog, add multiple sizes
5. Save to `Icon/piston-16.ico`
6. Rebuild

### Option 3: Use ImageMagick (Command Line)
```bash
# Install ImageMagick first
# Then convert:
magick convert input.png -define icon:auto-resize=256,48,32,16 Icon/piston-16.ico
```

## Required Icon Sizes

| Size | Used For |
|------|----------|
| 16x16 | Small icons, list view |
| 32x32 | Medium icons, taskbar |
| 48x48 | Large icons, Explorer |
| 256x256 | Extra large, high DPI displays |

## After Creating Multi-Size Icon

### 1. Replace the icon file
```powershell
# Place new multi-size .ico at:
Icon/piston-16.ico
```

### 2. Rebuild
```powershell
python -m PyInstaller --noconfirm piston.spec
```

### 3. Clear icon cache
```powershell
.\clear_icon_cache.bat
```

### 4. Verify
Open Windows Explorer and navigate to `dist\piston\` - icon should now show!

## Quick Verification

### Check icon file size:
A proper multi-size .ico should be **10KB-100KB** (not 1KB)

```powershell
Get-Item Icon\piston-16.ico | Select-Object Name, Length
```

**Current:** 1150 bytes ❌ (too small, only one size)  
**Expected:** 10,000+ bytes ✅ (multiple sizes)

## Alternative: Use a Pre-Made Icon

If you don't have a source image to convert:

### Free Icon Resources:
- **Flaticon**: https://www.flaticon.com/ (free with attribution)
- **Icons8**: https://icons8.com/ (free PNG, convert to .ico)
- **IconArchive**: https://iconarchive.com/ (multi-size .ico files)

Download a multi-size .ico file and replace `Icon/piston-16.ico`

## Why Single-Size Icons Fail

Windows uses different icon sizes in different contexts:
- **File Explorer** - Uses 48x48 or 256x256
- **Taskbar** - Uses 32x32
- **Alt+Tab** - Uses 32x32
- **Title Bar** - Uses 16x16

If your .ico only has 16x16, Windows can't scale it properly and shows the default icon instead.

## Testing After Fix

### 1. Check file size increased
```powershell
Get-Item Icon\piston-16.ico | Select Length
# Should be 10KB+ now
```

### 2. Rebuild
```powershell
python -m PyInstaller --noconfirm piston.spec
```

### 3. Clear cache
```powershell
.\clear_icon_cache.bat
```

### 4. Navigate in Explorer
Open `dist\piston\` in Windows Explorer - icon should appear!

## Still Not Working?

### Nuclear Option: Log Out and Back In
Sometimes Windows needs a full logoff to clear icon cache completely:
1. Save your work
2. Log out of Windows
3. Log back in
4. Check `dist\piston\piston.exe` in Explorer

### Verify Icon is Embedded
Run this PowerShell to extract icon info:
```powershell
Add-Type -AssemblyName System.Drawing
$icon = [System.Drawing.Icon]::ExtractAssociatedIcon("dist\piston\piston.exe")
if ($icon) {
    Write-Host "Icon embedded: Yes"
    Write-Host "Icon size: $($icon.Width)x$($icon.Height)"
} else {
    Write-Host "Icon embedded: No"
}
```

## Summary

**Most Likely Issue:** Your .ico file only contains one size (16x16)

**Quick Fix:**
1. Create multi-size .ico (16, 32, 48, 256)
2. Replace `Icon/piston-16.ico`
3. Rebuild with PyInstaller
4. Clear icon cache

**Expected Result:** Icon shows everywhere! 🎨

---

**Need a quick fix?** Send me your source image (PNG/JPG) and I can help you create a proper multi-size .ico file.
