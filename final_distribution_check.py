#!/usr/bin/env python
"""
Final Pre-Distribution Verification
Checks all fixes and ensures the build is ready to share.
"""
import os
import sys
import datetime

def final_verification():
    print("="*70)
    print("FINAL PRE-DISTRIBUTION VERIFICATION")
    print("="*70)
    
    issues = []
    warnings = []
    
    # 1. Check build exists and is recent
    print("\n1. Checking build status...")
    exe_path = os.path.join('dist', 'piston', 'piston.exe')
    
    if not os.path.exists(exe_path):
        issues.append("❌ piston.exe not found at dist/piston/")
        print("   ❌ CRITICAL: Build not found")
        return False
    
    stat = os.stat(exe_path)
    size_mb = stat.st_size / (1024 * 1024)
    mod_time = datetime.datetime.fromtimestamp(stat.st_mtime)
    age_minutes = (datetime.datetime.now() - mod_time).total_seconds() / 60
    
    print(f"   ✓ Build found: {mod_time.strftime('%I:%M:%S %p')}")
    print(f"   ✓ Size: {size_mb:.1f} MB")
    print(f"   ✓ Age: {age_minutes:.0f} minutes")
    
    # 2. Check for all fixes in source code
    print("\n2. Verifying source code fixes...")
    
    # Check hidden stations fix
    fixes_verified = 0
    
    # a. Capacity Estimator fix
    manual_et_path = 'piston_ui/manual_et.py'
    if os.path.exists(manual_et_path):
        with open(manual_et_path, 'r', encoding='utf-8') as f:
            if '_is_hidden_station(st)' in f.read():
                print("   ✓ Capacity Estimator fix present")
                fixes_verified += 1
            else:
                issues.append("❌ Capacity Estimator fix missing")
    
    # b. Console window fix
    spec_path = 'piston.spec'
    if os.path.exists(spec_path):
        with open(spec_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'console=False' in content:
                print("   ✓ Console window disabled")
                fixes_verified += 1
            else:
                issues.append("❌ Console window not disabled")
    
    # c. Icon fix
    if os.path.exists(spec_path):
        with open(spec_path, 'r', encoding='utf-8') as f:
            if "'Icon/piston.ico'" in f.read():
                print("   ✓ Icon configured")
                fixes_verified += 1
            else:
                warnings.append("⚠ Icon might not be configured")
    
    # d. Icon helper fix
    icon_helper_path = 'piston_ui/icon_helper.py'
    if os.path.exists(icon_helper_path):
        with open(icon_helper_path, 'r', encoding='utf-8') as f:
            if 'sys._MEIPASS' in f.read():
                print("   ✓ Icon helper PyInstaller-ready")
                fixes_verified += 1
            else:
                warnings.append("⚠ Icon helper might not work in .exe")
    
    # e. Validation helper fix
    val_helper_path = 'piston_ui/validation_helper.py'
    if os.path.exists(val_helper_path):
        with open(val_helper_path, 'r', encoding='utf-8') as f:
            if '_get_hidden_stations()' in f.read():
                print("   ✓ Validation helper filters hidden stations")
                fixes_verified += 1
            else:
                warnings.append("⚠ Validation helper might not filter hidden stations")
    
    print(f"\n   Total fixes verified: {fixes_verified}/5")
    
    # 3. Check required bundled files
    print("\n3. Checking bundled files...")
    
    required_files = [
        ('_internal', 'dir', 'Dependencies directory'),
        ('_internal/embedded', 'dir', 'Embedded resources'),
        ('_internal/embedded/default_model.xlsx', 'file', 'Default model'),
        ('_internal/Icon', 'dir', 'Icon directory'),
        ('_internal/Icon/piston.ico', 'file', 'Application icon'),
    ]
    
    missing_files = []
    for item, item_type, description in required_files:
        path = os.path.join('dist', 'piston', item)
        if item_type == 'dir':
            exists = os.path.isdir(path)
        else:
            exists = os.path.isfile(path)
        
        if exists:
            print(f"   ✓ {description}")
        else:
            missing_files.append(f"❌ Missing: {description} ({item})")
            print(f"   ❌ Missing: {description}")
    
    if missing_files:
        issues.extend(missing_files)
    
    # 4. Check icon file quality
    print("\n4. Checking icon quality...")
    
    icon_source = 'Icon/piston.ico'
    if os.path.exists(icon_source):
        icon_size = os.path.getsize(icon_source)
        icon_kb = icon_size / 1024
        print(f"   ✓ Source icon: {icon_kb:.1f} KB")
        
        if icon_kb > 10:
            print("   ✓ Icon is multi-size (good quality)")
        else:
            warnings.append(f"⚠ Icon might be single-size ({icon_kb:.1f} KB)")
    else:
        warnings.append("⚠ Source icon not found")
    
    # 5. Check README for users
    print("\n5. Checking user documentation...")
    
    readme_path = os.path.join('dist', 'piston', 'README_USERS.md')
    if os.path.exists(readme_path):
        print("   ✓ User README present")
    else:
        warnings.append("⚠ User README missing (recommended)")
    
    # 6. Check for running processes
    print("\n6. Checking for running instances...")
    try:
        import subprocess
        result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq piston.exe'],
                              capture_output=True, text=True)
        if 'piston.exe' in result.stdout:
            warnings.append("⚠ piston.exe is currently running - close before packaging")
            print("   ⚠ piston.exe is running - should close before ZIP")
        else:
            print("   ✓ No instances running")
    except Exception:
        print("   ⚠ Could not check running processes")
    
    # 7. Final size check
    print("\n7. Checking distribution size...")
    
    total_size = 0
    for root, dirs, files in os.walk('dist/piston'):
        for file in files:
            total_size += os.path.getsize(os.path.join(root, file))
    
    total_mb = total_size / (1024 * 1024)
    print(f"   ✓ Total size: {total_mb:.1f} MB")
    
    if total_mb > 500:
        warnings.append(f"⚠ Large distribution size: {total_mb:.1f} MB")
    
    # SUMMARY
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)
    
    if issues:
        print("\n❌ CRITICAL ISSUES FOUND:")
        for issue in issues:
            print(f"   {issue}")
        print("\n⚠️  DO NOT DISTRIBUTE - Fix issues first")
        return False
    
    if warnings:
        print("\n⚠️  WARNINGS (non-critical):")
        for warning in warnings:
            print(f"   {warning}")
        print("\n✓ Can proceed but review warnings")
    
    if not issues and not warnings:
        print("\n✅ ALL CHECKS PASSED - READY TO DISTRIBUTE!")
    
    print("\n" + "="*70)
    print("DISTRIBUTION INSTRUCTIONS")
    print("="*70)
    
    print("\n1. Create ZIP:")
    print("   - Navigate to dist\\ in File Explorer")
    print("   - Right-click 'piston' folder")
    print("   - Send to → Compressed (zipped) folder")
    print("   - Rename to: Piston_v1.0.zip")
    
    print("\n2. Test ZIP before sharing:")
    print("   - Extract to a test location")
    print("   - Run piston.exe from extracted location")
    print("   - Verify all features work")
    
    print("\n3. Share:")
    print("   - Share the ZIP file")
    print("   - Include README_USERS.md for instructions")
    
    print("\n" + "="*70)
    
    return len(issues) == 0

if __name__ == '__main__':
    try:
        success = final_verification()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Verification failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
