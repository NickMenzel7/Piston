#!/usr/bin/env python
"""
Verify which version of piston.exe is being tested.
"""
import os
import datetime

def verify_build():
    print("="*70)
    print("BUILD VERIFICATION")
    print("="*70)
    
    exe_path = os.path.join('dist', 'piston', 'piston.exe')
    
    if not os.path.exists(exe_path):
        print(f"\n❌ ERROR: {exe_path} not found!")
        print("   Make sure you're in the project root directory.")
        return
    
    # Get file info
    stat = os.stat(exe_path)
    size_mb = stat.st_size / (1024 * 1024)
    mod_time = datetime.datetime.fromtimestamp(stat.st_mtime)
    
    print(f"\n📍 EXE Location: {os.path.abspath(exe_path)}")
    print(f"📅 Build Time: {mod_time.strftime('%Y-%m-%d %I:%M:%S %p')}")
    print(f"📦 Size: {size_mb:.1f} MB")
    
    # Check if build is recent (within last hour)
    now = datetime.datetime.now()
    age_minutes = (now - mod_time).total_seconds() / 60
    
    print(f"\n⏰ Build Age: {age_minutes:.0f} minutes ago")
    
    if age_minutes < 5:
        print("✅ BUILD IS VERY RECENT")
    elif age_minutes < 60:
        print("✅ BUILD IS RECENT")
    else:
        print("⚠️  BUILD IS OLD - Consider rebuilding")
    
    # Check for Capacity Estimator fix
    print("\n" + "="*70)
    print("CHECKING FOR CAPACITY ESTIMATOR FIX")
    print("="*70)
    
    manual_et_path = os.path.join('piston_ui', 'manual_et.py')
    if os.path.exists(manual_et_path):
        with open(manual_et_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if '_is_hidden_station(st)' in content:
            print("✅ Source code has the fix")
        else:
            print("❌ Source code missing the fix")
        
        # Check line 127 area
        lines = content.split('\n')
        for i, line in enumerate(lines[120:135], start=121):
            if '_is_hidden_station' in line:
                print(f"   Line {i}: {line.strip()}")
                print("   ✅ Fix is present in source")
                break
    
    print("\n" + "="*70)
    print("RECOMMENDED ACTIONS")
    print("="*70)
    
    if age_minutes > 5:
        print("\n1. ⚠️  Your build might be outdated")
        print("   Run: python -m PyInstaller --noconfirm piston.spec")
    
    print("\n2. Make sure you're running THIS exact file:")
    print(f"   {os.path.abspath(exe_path)}")
    
    print("\n3. Close any running instances of piston.exe first")
    
    print("\n4. If you're running from a different location:")
    print("   - Check that location's build time")
    print("   - Make sure it's not an older copy")
    
    print("\n" + "="*70)

if __name__ == '__main__':
    verify_build()
