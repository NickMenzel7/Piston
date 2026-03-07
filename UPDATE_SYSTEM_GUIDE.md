# Piston Auto-Update System Guide

## 🎯 Overview

Piston now checks for updates automatically on startup. No separate updater.exe needed!

**How it works:**
1. User runs `piston.exe`
2. App launches normally (instant)
3. After 2 seconds, background check queries GitHub
4. If update available → Blue banner appears at top
5. User clicks "Update Now" → Downloads and applies on restart

---

## 🚀 How to Push an Update (Your Workflow)

### **Step 1: Make Your Changes**
```powershell
# Fix bug, add feature, etc.
git add .
git commit -m "Fix: Corrected yield calculation"
```

### **Step 2: Update Version Number**
**Edit `version.txt`:**
```
1.0.1
```

(Increment: 1.0.0 → 1.0.1 for bug fixes, 1.1.0 for features, 2.0.0 for major changes)

### **Step 3: Build New .exe**
```powershell
# Build as usual
python -m PyInstaller --noconfirm piston.spec

# Result: dist/piston/piston.exe
```

### **Step 4: Create GitHub Release**

**Option A: GitHub Web UI** (easiest)
```
1. Go to: https://github.com/YOUR_USERNAME/YOUR_REPO/releases
2. Click "Draft a new release"
3. Fill in:
   - Tag: v1.0.1
   - Title: Piston v1.0.1
   - Description:
     ## What's New
     - Fixed yield calculation in parallel mode
     - Improved station validation
     
4. Upload: dist/piston/piston.exe (drag & drop)
5. Click "Publish release"
```

**Option B: Command Line** (faster)
```powershell
# Install GitHub CLI first: https://cli.github.com/
gh release create v1.0.1 `
  --title "Piston v1.0.1" `
  --notes "Fixed yield calculation bug" `
  dist/piston/piston.exe
```

**That's it!** Users get the update next time they launch.

---

## 👤 User Experience

### **When User Launches Piston:**

```
[App opens instantly]
  ↓
[2 seconds later]
  ↓
╔════════════════════════════════════════════════════════╗
║ 📦 Piston 1.0.1 is available (45.2 MB)               ║
║  [Update Now]  [What's New]                       [✕] ║
╚════════════════════════════════════════════════════════╝

User clicks "Update Now":
  ↓
[Progress bar: Downloading... 45%]
  ↓
[Dialog: "Update ready - restart now?"]
  ↓
If YES: App closes, new version launches
If NO:  Update applies next time
```

---

## ⚙️ Configuration

### **Update the GitHub URL**

**File: `piston_core/updater.py`**

```python
# Line 13 - Change this:
GITHUB_API = "https://api.github.com/repos/YOUR_ORG/YOUR_REPO/releases/latest"

# To your actual repo:
GITHUB_API = "https://api.github.com/repos/johndoe/piston/releases/latest"
```

### **Disable Update Checks** (optional)

Users can disable by setting environment variable:
```powershell
$env:PISTON_DISABLE_UPDATES = "1"
```

---

## 🧪 Testing Locally

### **Test Update Detection:**

1. Set `version.txt` to `0.9.0`
2. Build: `python -m PyInstaller --noconfirm piston.spec`
3. Run: `dist/piston/piston.exe`
4. Expected: Banner shows "1.0.0 available" (if you have a release)

### **Test Without Internet:**

1. Disconnect network
2. Run app
3. Expected: App works normally, no error messages

### **Test Download:**

1. Create a test release on GitHub with old version
2. Run app with lower version.txt
3. Click "Update Now"
4. Expected: Progress bar, then restart prompt

---

## 🔒 Security Notes

### **HTTPS Only**
- Always use `https://` for GitHub API
- Built into the code already ✓

### **File Size Check**
- Updater rejects downloads <5 MB (prevents corrupted files)
- Built into `download_update()` ✓

### **Backup on Replace**
- Old `piston.exe` → `piston.exe.old` (kept for 5 seconds)
- Automatic rollback if new version fails ✓

---

## 🐛 Troubleshooting

### **"Update banner never appears"**

Check the log: `piston_debug.log`

Look for:
```
INFO: Checking for updates (current version: 1.0.0)...
INFO: No update available
```

**Possible causes:**
1. No internet connection (expected - app still works)
2. GitHub API unreachable (rare)
3. No release found (create one first)
4. Version in version.txt matches latest release

### **"Download fails"**

Check:
1. ✅ Internet connection works
2. ✅ GitHub release has `piston.exe` asset
3. ✅ File size is reasonable (>5 MB)

### **"Update applies but app won't start"**

Rollback:
1. Find `piston.exe.old` in app directory
2. Rename: `piston.exe.old` → `piston.exe`
3. Delete bad version
4. Report bug!

---

## 📋 Quick Checklist

**Before Each Release:**
- [ ] Update `version.txt` (e.g., 1.0.1)
- [ ] Build: `python -m PyInstaller --noconfirm piston.spec`
- [ ] Test: Run `dist/piston/piston.exe` locally
- [ ] Create GitHub release with tag `v1.0.1`
- [ ] Upload `piston.exe` as asset
- [ ] Add release notes
- [ ] Publish!

**Users will see update within ~10 seconds of next launch.**

---

## 🎓 Next Steps (Future Enhancements)

### **Phase 2: Code Signing** ($300/year)
- Prevents Windows SmartScreen warnings
- Users trust "Published by: YourCompany"

### **Phase 3: Analytics** (optional)
- Track update adoption rates
- Identify users on old versions

### **Phase 4: Delta Updates** (advanced)
- Download only changed files (~5 MB vs 45 MB)
- Faster updates for frequent releases

---

## ❓ FAQ

**Q: Will this work offline?**  
A: Yes! Update check fails silently, app works normally.

**Q: Can users disable updates?**  
A: Yes, set environment variable `PISTON_DISABLE_UPDATES=1`

**Q: What if GitHub is down?**  
A: Check times out after 5 seconds, app continues normally.

**Q: Can I use a private GitHub repo?**  
A: Yes! Users with repo access can download. (Needs auth token - ask if you need this)

**Q: How do I test without pushing to production?**  
A: Create a "test" or "beta" release tag (e.g., `v1.0.1-beta`)

---

## 🎉 You're Done!

Your app now has professional auto-update capability:
- ✅ No separate updater needed
- ✅ Non-intrusive (background check)
- ✅ One-click updates
- ✅ Automatic rollback
- ✅ Release notes shown to users
- ✅ Works offline

**Total implementation time: ~20 minutes**  
**Total ongoing effort per release: ~5 minutes**
